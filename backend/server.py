#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/server.py (Servidor HTTP/REST API v3.0 com CRM SQLite & Multi-IA)
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  3.0.0
================================================================================
"""

import json
import mimetypes
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from backend.auth import (
    login_admin,
    login_subscriber,
    login_trial,
    get_session_info,
    consume_trial_scan,
    generate_subscription_key,
    load_config,
    save_config,
    hash_pin,
    AUTHOR_WHATSAPP,
    AUTHOR_WHATSAPP_URL,
)
from backend.collectors.hardware import collect_hardware_info
from backend.collectors.os_info import collect_os_info
from backend.collectors.drivers_bios import (
    collect_drivers_and_bios,
    scan_and_install_windows_driver_updates,
)
from backend.collectors.software import (
    collect_installed_software,
    run_winget_action,
    remove_bloatware,
)
from backend.services.maintenance import run_maintenance_task
from backend.services.network_tools import (
    collect_network_diagnostics,
    apply_dns_preset,
    recover_wifi_passwords,
    run_download_speedtest,
)
from backend.services.gaming_dll import (
    audit_gaming_and_dlls,
    run_gaming_optimization,
)
from backend.services.compatibility import analyze_hardware_compatibility
from backend.services.admin_crm import (
    FAIR_PRICING_CATALOG,
    list_crm_clients,
    delete_crm_client,
    save_client_and_generate_report,
)
from backend.services.gemini_ai import check_internet_connection, query_gemini_ai
from backend.services.html_reporter import generate_html_report

SESSION_STATE = {
    "base_dir": Path("."),
    "last_snapshot": {},
    "last_ai_analysis": "",
    "action_logs": [],
}


def log_action(action_name: str, summary: str) -> None:
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action_name,
        "summary": summary,
    }
    SESSION_STATE["action_logs"].append(entry)


class AegisPulseRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data: dict, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _get_token(self) -> str | None:
        return self.headers.get("X-Operator-Token")

    def _require_auth(self, require_admin: bool = False) -> dict | None:
        base_dir = SESSION_STATE["base_dir"]
        sess = get_session_info(base_dir, self._get_token())
        if not sess:
            self._send_json(
                {
                    "error": "unauthorized",
                    "message": f"Sessão não iniciada. Escolha Modo Trial (4 Análises Grátis), Assinatura PRO ou fale com Adriano Barboza no WhatsApp {AUTHOR_WHATSAPP}.",
                    "whatsapp": AUTHOR_WHATSAPP,
                    "whatsapp_url": AUTHOR_WHATSAPP_URL,
                },
                status=401,
            )
            return None
        if require_admin and sess.get("role") != "admin":
            self._send_json(
                {
                    "error": "forbidden",
                    "message": "Acesso exclusivo ao Administrador Master (Adriano Barboza).",
                },
                status=403,
            )
            return None
        return sess

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)
        base_dir = SESSION_STATE["base_dir"]

        if route == "/api/auth/status":
            cfg = load_config(base_dir)
            sess = get_session_info(base_dir, self._get_token())
            self._send_json({
                "require_pin": True,
                "authorized": sess is not None,
                "session": sess,
                "trial_used": int(cfg.get("trial_scans_used", 0)),
                "trial_limit": int(cfg.get("trial_limit", 4)),
                "activated_license_key": cfg.get("activated_license_key", ""),
                "author": "Adriano Barboza",
                "whatsapp": AUTHOR_WHATSAPP,
                "whatsapp_url": AUTHOR_WHATSAPP_URL,
                "online": check_internet_connection(),
                "has_gemini_key": bool(
                    cfg.get("gemini_api_key")
                    and cfg.get("gemini_api_key") != "COLE_SUA_GEMINI_API_KEY_AQUI"
                ),
            })
            return

        if route == "/api/scan/full":
            sess = self._require_auth()
            if not sess:
                return
            allowed, msg = consume_trial_scan(base_dir, self._get_token())
            if not allowed:
                self._send_json(
                    {
                        "error": "trial_exhausted",
                        "message": msg,
                        "whatsapp": AUTHOR_WHATSAPP,
                        "whatsapp_url": AUTHOR_WHATSAPP_URL,
                        "session": get_session_info(base_dir, self._get_token()),
                    },
                    status=402,
                )
                return

            hw = collect_hardware_info()
            os_data = collect_os_info()
            drv_bios = collect_drivers_and_bios()
            sw = collect_installed_software()
            net = collect_network_diagnostics()
            gaming = audit_gaming_and_dlls(hardware=hw)
            compat = analyze_hardware_compatibility(hardware=hw, os_info=os_data)

            updated_sess = get_session_info(base_dir, self._get_token())
            snapshot = {
                "collected_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "author": "Adriano Barboza",
                "whatsapp": AUTHOR_WHATSAPP,
                "whatsapp_url": AUTHOR_WHATSAPP_URL,
                "online": check_internet_connection(),
                "session": updated_sess,
                "hardware": hw,
                "os": os_data,
                "drivers_bios": drv_bios,
                "software": sw,
                "network": net,
                "gaming": gaming,
                "compatibility": compat,
                "pricing_catalog": FAIR_PRICING_CATALOG if updated_sess.get("role") == "admin" else [],
                "action_logs": SESSION_STATE["action_logs"],
            }
            SESSION_STATE["last_snapshot"] = snapshot
            log_action(
                f"Diagnóstico v3.0 ({updated_sess.get('role', 'user').upper()})",
                f"Varredura executada em {hw.get('hostname')} ({msg})",
            )
            self._send_json(snapshot)
            return

        if route == "/api/admin/crm/list":
            if not self._require_auth(require_admin=True):
                return
            q = (qs.get("q") or [""])[0]
            clients = list_crm_clients(base_dir, search_query=q)
            self._send_json({
                "success": True,
                "clients": clients,
                "pricing_catalog": FAIR_PRICING_CATALOG,
            })
            return

        if route == "/api/logs":
            if not self._require_auth():
                return
            self._send_json({"action_logs": SESSION_STATE["action_logs"]})
            return

        if route.startswith("/reports/"):
            rel_name = route.replace("/reports/", "", 1)
            target = (base_dir / "reports" / rel_name).resolve()
            if target.exists() and target.is_file():
                content = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        frontend_dir = base_dir / "frontend"
        if route == "/" or route == "/index.html":
            file_path = frontend_dir / "index.html"
        else:
            file_path = (frontend_dir / route.lstrip("/")).resolve()

        if file_path.exists() and file_path.is_file():
            ctype, _ = mimetypes.guess_type(str(file_path))
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{ctype or 'text/plain'}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self._send_json({"error": "not_found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        route = parsed.path
        base_dir = SESSION_STATE["base_dir"]

        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length > 0:
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                body = {}

        if route == "/api/auth/login":
            mode = str(body.get("mode", "admin"))
            if mode == "admin":
                pin = str(body.get("pin", ""))
                res = login_admin(base_dir, pin)
                if res.get("success"):
                    log_action("Login Master ADM", "Sessão Master desbloqueada por Adriano Barboza.")
                    self._send_json(res)
                else:
                    self._send_json(res, status=403)
                return

            if mode == "subscriber":
                lkey = str(body.get("license_key", ""))
                res = login_subscriber(base_dir, lkey)
                if res.get("success"):
                    log_action("Ativação de Assinatura PRO", res.get("message", ""))
                    self._send_json(res)
                else:
                    self._send_json(res, status=403)
                return

            if mode == "trial":
                res = login_trial(base_dir)
                if res.get("success"):
                    log_action("Início de Sessão Trial", res.get("role_label", ""))
                    self._send_json(res)
                else:
                    self._send_json(res, status=402)
                return

        if route == "/api/admin/generate-key":
            if not self._require_auth(require_admin=True):
                return
            client_name = str(body.get("client_name", "Cliente PRO"))
            days = int(body.get("days_valid", 365))
            key_data = generate_subscription_key(client_name=client_name, days_valid=days)
            log_action("ADM Keygen", f"Chave gerada para {client_name} ({days} dias): {key_data['license_key']}")
            key_data["success"] = True
            key_data["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(key_data)
            return

        if route == "/api/admin/reset-trial":
            if not self._require_auth(require_admin=True):
                return
            save_config(base_dir, {"trial_scans_used": 0})
            log_action("ADM Reset Trial", "Contador de análises Trial zerado (0/4) pelo Administrador.")
            self._send_json({
                "success": True,
                "message": "Contador Trial desta máquina foi zerado (0 de 4 análises usadas).",
                "action_logs": SESSION_STATE["action_logs"],
            })
            return

        if route == "/api/admin/crm/save-and-quote":
            if not self._require_auth(require_admin=True):
                return
            snapshot = SESSION_STATE.get("last_snapshot") or {
                "hardware": collect_hardware_info(),
                "os": collect_os_info(),
            }
            res = save_client_and_generate_report(base_dir, snapshot, body)
            log_action("CRM SQLite & Orçamento Cliente", res.get("message", ""))
            res["clients"] = list_crm_clients(base_dir)
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/admin/crm/delete":
            if not self._require_auth(require_admin=True):
                return
            cid = int(body.get("client_id", 0))
            delete_crm_client(base_dir, cid)
            log_action("CRM SQLite", f"Registro de cliente #{cid} removido.")
            self._send_json({
                "success": True,
                "clients": list_crm_clients(base_dir),
                "action_logs": SESSION_STATE["action_logs"],
            })
            return

        sess = self._require_auth()
        if not sess:
            return

        if route == "/api/software/winget":
            action = str(body.get("action", ""))
            pkg_id = str(body.get("package_id", ""))
            app_name = str(body.get("app_name", ""))
            res = run_winget_action(action=action, package_id=pkg_id, app_name=app_name)
            log_action(f"Winget ({action})", f"Alvo: {pkg_id or app_name or 'Todos'} -> {res.get('message')}")
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/software/debloat":
            packages = body.get("packages") or []
            res = remove_bloatware(packages)
            log_action("Remoção de Bloatware", res.get("message", ""))
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/drivers/windows-update":
            install_flag = bool(body.get("install", False))
            res = scan_and_install_windows_driver_updates(install=install_flag)
            log_action("Windows Update Drivers", res.get("message", ""))
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/network/action":
            sub_action = str(body.get("action", ""))
            if sub_action == "set_dns":
                preset = str(body.get("preset", "cloudflare"))
                res = apply_dns_preset(preset)
                log_action("Configuração de DNS", res.get("message", ""))
            elif sub_action == "wifi_passwords":
                res = recover_wifi_passwords()
                log_action("Auditoria Wi-Fi", res.get("message", ""))
            elif sub_action == "speedtest":
                res = run_download_speedtest()
                log_action("Teste de Velocidade", res.get("message", ""))
            else:
                res = {"success": False, "message": "Ação de rede inválida."}
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/gaming/action":
            opt_action = str(body.get("action", ""))
            res = run_gaming_optimization(opt_action)
            log_action(f"Otimização Gamer ({opt_action})", res.get("message", ""))
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/maintenance/run":
            task_id = str(body.get("task_id", ""))
            res = run_maintenance_task(task_id)
            log_action(res.get("task", task_id), res.get("summary", ""))
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/gemini/analyze":
            cfg = load_config(base_dir)
            provider = str(body.get("provider") or "local")
            api_key = str(body.get("api_key") or cfg.get("gemini_api_key") or "")
            grok_key = str(body.get("grok_api_key") or cfg.get("grok_api_key") or "")
            prompt = str(body.get("prompt") or "")

            updates = {}
            if body.get("api_key"):
                updates["gemini_api_key"] = api_key.strip()
            if body.get("grok_api_key"):
                updates["grok_api_key"] = grok_key.strip()
            if updates:
                save_config(base_dir, updates)

            snapshot = SESSION_STATE.get("last_snapshot")
            if not snapshot:
                hw = collect_hardware_info()
                snapshot = {
                    "hardware": hw,
                    "os": collect_os_info(),
                    "drivers_bios": collect_drivers_and_bios(),
                    "software": collect_installed_software(),
                    "gaming": audit_gaming_and_dlls(hardware=hw),
                }

            res = query_gemini_ai(
                api_key=api_key,
                snapshot=snapshot,
                user_prompt=prompt,
                provider=provider,
                user_role=sess.get("role", "trial"),
                grok_api_key=grok_key,
            )
            if res.get("success") and not res.get("requires_subscription"):
                SESSION_STATE["last_ai_analysis"] = res.get("response_text", "")
                log_action(f"Análise IA ({res.get('model_used', provider)})", "Diagnóstico inteligente gerado.")
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/report/generate":
            snapshot = SESSION_STATE.get("last_snapshot")
            if not snapshot:
                hw = collect_hardware_info()
                os_d = collect_os_info()
                snapshot = {
                    "hardware": hw,
                    "os": os_d,
                    "drivers_bios": collect_drivers_and_bios(),
                    "software": collect_installed_software(),
                    "gaming": audit_gaming_and_dlls(hardware=hw),
                    "compatibility": analyze_hardware_compatibility(hw, os_d),
                }
                SESSION_STATE["last_snapshot"] = snapshot

            res = generate_html_report(
                snapshot=snapshot,
                base_dir=base_dir,
                ai_analysis=SESSION_STATE.get("last_ai_analysis", ""),
                action_logs=SESSION_STATE["action_logs"],
            )
            log_action("Exportação de Laudo HTML", f"Arquivo gerado: {res.get('filename')}")
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/config/update":
            updates = {}
            if "gemini_api_key" in body and body["gemini_api_key"]:
                updates["gemini_api_key"] = str(body["gemini_api_key"]).strip()
            if "grok_api_key" in body and body["grok_api_key"]:
                updates["grok_api_key"] = str(body["grok_api_key"]).strip()
            if "new_pin" in body and body["new_pin"]:
                if sess.get("role") != "admin":
                    self._send_json({"success": False, "message": "Apenas o Administrador pode alterar a senha Master."}, status=403)
                    return
                updates["operator_pin_sha256"] = hash_pin(str(body["new_pin"]))
            ok = save_config(base_dir, updates)
            log_action("Atualização de Configuração", "Parâmetros locais atualizados em config.json.")
            self._send_json({"success": ok, "message": "Configurações salvas com sucesso.", "action_logs": SESSION_STATE["action_logs"]})
            return

        self._send_json({"error": "invalid_endpoint"}, status=404)


def start_AegisPulse_server(host: str, port: int, base_dir: Path) -> None:
    SESSION_STATE["base_dir"] = base_dir
    server = ThreadingHTTPServer((host, port), AegisPulseRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Encerrando servidor AegisPulse...")
        server.server_close()
