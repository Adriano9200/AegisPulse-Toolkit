#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/server.py (Servidor HTTP/REST API Modular)
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
================================================================================
Descrição:
Servidor HTTP local que serve a interface gráfica (Frontend SPA) e expõe os
endpoints REST JSON para diagnóstico de hardware, SO, BIOS/Drivers, Softwares,
manutenção segura, integração Gemini AI e geração de relatórios HTML.
"""

import json
import mimetypes
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from backend.auth import (
    verify_operator_pin,
    is_authorized,
    load_config,
    save_config,
    hash_pin,
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
)
from backend.services.maintenance import run_maintenance_task
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
        # Silencia logs repetitivos de arquivos estáticos no terminal
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

    def _require_auth(self) -> bool:
        base_dir = SESSION_STATE["base_dir"]
        if not is_authorized(base_dir, self._get_token()):
            self._send_json(
                {
                    "error": "unauthorized",
                    "message": "Acesso restrito ao autor/operador autorizado (Adriano Barboza). Insira seu PIN de Técnico.",
                },
                status=401,
            )
            return False
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        base_dir = SESSION_STATE["base_dir"]

        if route == "/api/auth/status":
            cfg = load_config(base_dir)
            authorized = is_authorized(base_dir, self._get_token())
            self._send_json({
                "require_pin": bool(cfg.get("require_operator_pin", True)),
                "authorized": authorized,
                "author": "Adriano Barboza",
                "online": check_internet_connection(),
                "has_gemini_key": bool(
                    cfg.get("gemini_api_key")
                    and cfg.get("gemini_api_key") != "COLE_SUA_GEMINI_API_KEY_AQUI"
                ),
            })
            return

        if route == "/api/scan/full":
            if not self._require_auth():
                return
            hw = collect_hardware_info()
            os_data = collect_os_info()
            drv_bios = collect_drivers_and_bios()
            sw = collect_installed_software()
            snapshot = {
                "collected_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "author": "Adriano Barboza",
                "online": check_internet_connection(),
                "hardware": hw,
                "os": os_data,
                "drivers_bios": drv_bios,
                "software": sw,
                "action_logs": SESSION_STATE["action_logs"],
            }
            SESSION_STATE["last_snapshot"] = snapshot
            log_action("Diagnóstico Completo", f"Varredura executada em {hw.get('hostname')}")
            self._send_json(snapshot)
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

        # Servir arquivos estáticos do Frontend
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
            pin = str(body.get("pin", ""))
            token = verify_operator_pin(base_dir, pin)
            if token:
                log_action("Autenticação de Operador", "Sessão desbloqueada pelo operador autorizado.")
                self._send_json({"success": True, "token": token})
            else:
                self._send_json({"success": False, "message": "PIN de Operador incorreto."}, status=403)
            return

        if not self._require_auth():
            return

        if route == "/api/software/winget":
            action = str(body.get("action", ""))
            pkg_id = str(body.get("package_id", ""))
            res = run_winget_action(action=action, package_id=pkg_id)
            log_action(f"Winget ({action})", f"Pacote: {pkg_id or 'Todos'} -> {res.get('message')}")
            self._send_json(res)
            return

        if route == "/api/drivers/windows-update":
            install_flag = bool(body.get("install", False))
            res = scan_and_install_windows_driver_updates(install=install_flag)
            log_action("Windows Update Drivers", res.get("message", ""))
            self._send_json(res)
            return

        if route == "/api/maintenance/run":
            task_id = str(body.get("task_id", ""))
            res = run_maintenance_task(task_id)
            log_action(res.get("task", task_id), res.get("summary", ""))
            self._send_json(res)
            return

        if route == "/api/gemini/analyze":
            cfg = load_config(base_dir)
            api_key = str(body.get("api_key") or cfg.get("gemini_api_key") or "")
            prompt = str(body.get("prompt") or "")
            if body.get("api_key"):
                save_config(base_dir, {"gemini_api_key": api_key.strip()})

            snapshot = SESSION_STATE.get("last_snapshot") or {
                "hardware": collect_hardware_info(),
                "os": collect_os_info(),
                "drivers_bios": collect_drivers_and_bios(),
                "software": collect_installed_software(),
            }
            res = query_gemini_ai(api_key=api_key, snapshot=snapshot, user_prompt=prompt)
            if res.get("success"):
                SESSION_STATE["last_ai_analysis"] = res.get("response_text", "")
                log_action("Consulta Gemini AI", "Diagnóstico inteligente gerado com sucesso.")
            self._send_json(res)
            return

        if route == "/api/report/generate":
            snapshot = SESSION_STATE.get("last_snapshot")
            if not snapshot:
                snapshot = {
                    "hardware": collect_hardware_info(),
                    "os": collect_os_info(),
                    "drivers_bios": collect_drivers_and_bios(),
                    "software": collect_installed_software(),
                }
                SESSION_STATE["last_snapshot"] = snapshot

            res = generate_html_report(
                snapshot=snapshot,
                base_dir=base_dir,
                ai_analysis=SESSION_STATE.get("last_ai_analysis", ""),
                action_logs=SESSION_STATE["action_logs"],
            )
            log_action("Exportação de Laudo HTML", f"Arquivo gerado: {res.get('filename')}")
            self._send_json(res)
            return

        if route == "/api/config/update":
            updates = {}
            if "gemini_api_key" in body and body["gemini_api_key"]:
                updates["gemini_api_key"] = str(body["gemini_api_key"]).strip()
            if "new_pin" in body and body["new_pin"]:
                updates["operator_pin_sha256"] = hash_pin(str(body["new_pin"]))
            if "require_operator_pin" in body:
                updates["require_operator_pin"] = bool(body["require_operator_pin"])
            ok = save_config(base_dir, updates)
            log_action("Atualização de Configuração", "Parâmetros locais atualizados em config.json.")
            self._send_json({"success": ok, "message": "Configurações salvas com sucesso."})
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
