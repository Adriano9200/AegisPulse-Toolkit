#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/server.py (Servidor HTTP/REST API v5.5 com Crash Investigator & PDF/HTML)
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  5.5.0
================================================================================
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, unquote, urlparse

from backend.auth import (
    AUTHOR_WHATSAPP,
    AUTHOR_WHATSAPP_URL,
    consume_trial_scan,
    generate_subscription_key,
    get_session_info,
    hash_pin,
    load_config,
    login_admin,
    login_subscriber,
    login_trial,
    save_config,
)
from backend.collectors.drivers_bios import (
    collect_drivers_and_bios,
    scan_and_install_windows_driver_updates,
)
from backend.collectors.hardware import collect_hardware_info
from backend.collectors.os_info import collect_os_info
from backend.collectors.software import (
    collect_installed_software,
    remove_bloatware,
    run_winget_action,
)
from backend.services.admin_crm import (
    FAIR_PRICING_CATALOG,
    delete_crm_client,
    list_crm_clients,
    save_client_and_generate_report,
)
from backend.services.compatibility import analyze_hardware_compatibility
from backend.services.crash_investigator import (
    SAFE_CRASH_ACTIONS_CATALOG,
    compare_crash_investigations,
    execute_authorized_crash_action,
    list_crash_investigations,
    run_full_crash_investigation,
)
from backend.services.gaming_dll import (
    audit_gaming_and_dlls,
    run_gaming_optimization,
)
from backend.services.gemini_ai import check_internet_connection, query_gemini_ai
from backend.services.health_score import (
    compare_health_evaluations,
    compute_health_score,
    get_latest_health_score,
    list_health_score_history,
)
from backend.services.html_reporter import generate_html_report
from backend.services.maintenance import run_maintenance_task
from backend.services.network_tools import (
    apply_dns_preset,
    collect_network_diagnostics,
    recover_wifi_passwords,
    run_download_speedtest,
)
from backend.services.storage_diagnostics import run_storage_integrity_test
from backend.services.storage_health import (
    build_complete_storage_suite_payload,
    list_storage_operations_log,
)
from backend.services.storage_recovery import (
    assign_or_change_drive_letter,
    cancel_active_clone_job,
    create_bootable_usb_drive,
    create_or_resume_disk_image,
    execute_diskpart_action,
    execute_logical_repair,
    force_unlock_and_revive_disk,
    format_and_partition_disk,
    inspect_and_recover_partitions,
    recover_files_assisted,
)

SESSION_STATE = {
    "base_dir": Path("."),
    "last_snapshot": {},
    "last_ai_analysis": "",
    "last_crash_investigation": {},
    "action_logs": [],
}


def _safe_call(fn, *args, default=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        print(f"[AVISO] Coletor {getattr(fn, '__name__', 'fn')} falhou parcialmente: {exc}")
        return default if default is not None else {}


def log_action(action_name: str, summary: str) -> None:
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action_name,
        "summary": summary,
    }
    SESSION_STATE["action_logs"].append(entry)


def _resolve_storage_device_strict(disk_number: int | None = None, device_uid: str = "") -> tuple[dict | None, dict]:
    """
    Resolve de forma estrita e não-ambígua o dispositivo selecionado:
    - NUNCA faz fallback silencioso para devs[0] (impedindo redirecionamento acidental para o disco do Windows).
    """
    snap = SESSION_STATE.get("last_snapshot") or {}
    st = snap.get("storage_suite") or {}
    devs = st.get("devices") or []
    if not devs and SESSION_STATE.get("base_dir"):
        st = build_complete_storage_suite_payload(SESSION_STATE["base_dir"])
        devs = st.get("devices") or []

    uid_clean = (device_uid or "").strip()
    if uid_clean:
        for d in devs:
            if str(d.get("device_uid") or "") == uid_clean:
                return d, st
    if disk_number is not None:
        for d in devs:
            if int(d.get("disk_number", -999)) == int(disk_number):
                return d, st
    return None, st


def _find_device_in_snapshot(disk_number: int = 0, device_uid: str = "") -> dict:
    dev, _ = _resolve_storage_device_strict(disk_number=disk_number, device_uid=device_uid)
    if dev:
        return dev
    return {
        "device_uid": "",
        "disk_number": disk_number,
        "model": "Unknown",
        "serial_number": "UNKNOWN",
        "drive_letters": [],
        "capacity": {"bytes": 0},
        "is_ambiguous_identity": True,
    }


class AegisPulseRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data: dict, status: int = 200) -> None:
        raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Operator-Token")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Operator-Token")
        self.send_header("Content-Length", "0")
        self.end_headers()

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
        try:
            self._handle_get()
        except Exception as exc:
            self._send_json(
                {
                    "success": False,
                    "error": "internal_server_error",
                    "error_stage": "http_get_handler",
                    "message": f"Erro interno no servidor (GET): {exc}",
                },
                status=500,
            )

    def _handle_get(self):
        parsed = urlparse(self.path)
        route = parsed.path
        qs = parse_qs(parsed.query)
        base_dir = SESSION_STATE["base_dir"]

        if route == "/api/auth/status":
            cfg = load_config(base_dir)
            sess = get_session_info(base_dir, self._get_token())
            self._send_json(
                {
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
                }
            )
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

            with ThreadPoolExecutor(max_workers=6) as pool:
                f_hw = pool.submit(_safe_call, collect_hardware_info, default={})
                f_os = pool.submit(_safe_call, collect_os_info, default={})
                f_drv = pool.submit(_safe_call, collect_drivers_and_bios, default={})
                f_sw = pool.submit(_safe_call, collect_installed_software, default={})
                f_net = pool.submit(_safe_call, collect_network_diagnostics, default={})
                f_st = pool.submit(_safe_call, build_complete_storage_suite_payload, base_dir, default={})
                hw = f_hw.result()
                os_data = f_os.result()
                drv_bios = f_drv.result()
                sw = f_sw.result()
                net = f_net.result()
                storage_suite = f_st.result()
            gaming = _safe_call(audit_gaming_and_dlls, hardware=hw, default={})
            compat = _safe_call(analyze_hardware_compatibility, hardware=hw, os_info=os_data, default={})
            health_eval = compute_health_score(
                {
                    "hardware": hw,
                    "os": os_data,
                    "drivers_bios": drv_bios,
                    "software": sw,
                    "gaming": gaming,
                    "storage_suite": storage_suite,
                },
                base_dir=base_dir,
            )

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
                "storage_suite": storage_suite,
                "health_score": health_eval,
                "crash_investigation": SESSION_STATE.get("last_crash_investigation") or {},
                "pricing_catalog": FAIR_PRICING_CATALOG if updated_sess.get("role") == "admin" else [],
                "action_logs": SESSION_STATE["action_logs"],
            }
            SESSION_STATE["last_snapshot"] = snapshot
            log_action(
                f"Diagnóstico Completo & Health Score v5.5 ({updated_sess.get('role', 'user').upper()})",
                f"Varredura executada em {hw.get('hostname')} ({storage_suite.get('total_physical_disks', 1)} disco(s) auditado(s) | {msg})",
            )
            self._send_json(snapshot)
            return

        if route == "/api/health-score/latest":
            if not self._require_auth():
                return
            latest = get_latest_health_score(base_dir)
            if not latest:
                snap = SESSION_STATE.get("last_snapshot") or {}
                if not snap:
                    hw = collect_hardware_info()
                    os_data = collect_os_info()
                    st = build_complete_storage_suite_payload(base_dir)
                    snap = {
                        "hardware": hw,
                        "os": os_data,
                        "drivers_bios": collect_drivers_and_bios(),
                        "software": collect_installed_software(),
                        "gaming": audit_gaming_and_dlls(hw),
                        "storage_suite": st,
                    }
                latest = compute_health_score(snap, base_dir=base_dir)
            self._send_json({"success": True, "health_score": latest})
            return

        if route == "/api/health-score/history":
            if not self._require_auth():
                return
            limit = int((qs.get("limit") or [20])[0])
            offset = int((qs.get("offset") or [0])[0])
            hist = list_health_score_history(base_dir, limit=limit, offset=offset)
            self._send_json({"success": True, **hist})
            return

        if route == "/api/health-score/compare":
            if not self._require_auth():
                return
            older_id = (qs.get("older_id") or [None])[0]
            newer_id = (qs.get("newer_id") or [None])[0]
            hist = list_health_score_history(base_dir, limit=10)
            items = hist.get("items") or []

            if not older_id or not newer_id:
                if len(items) >= 2:
                    eval_newer = items[0]
                    eval_older = items[1]
                elif len(items) == 1:
                    eval_newer = items[0]
                    eval_older = items[0]
                else:
                    self._send_json(
                        {"success": False, "message": "Histórico insuficiente para comparação (mínimo de 1 avaliação)."},
                        status=400,
                    )
                    return
            else:
                eval_older = next((it for it in items if str(it.get("id")) == str(older_id)), None)
                eval_newer = next((it for it in items if str(it.get("id")) == str(newer_id)), None)
                if not eval_older or not eval_newer:
                    self._send_json(
                        {"success": False, "message": "Uma das avaliações solicitadas não foi encontrada no histórico."},
                        status=404,
                    )
                    return

            diff = compare_health_evaluations(eval_older, eval_newer)
            self._send_json({"success": True, "comparison": diff})
            return

        # ==================== ROTAS GET: AEGISPULSE CRASH INVESTIGATOR (v5.5) ====================
        if route == "/api/crash-investigator/run":
            sess = self._require_auth()
            if not sess:
                return
            period_days = int((qs.get("period_days") or [7])[0])
            period_hours = int((qs.get("period_hours") or [period_days * 24])[0])
            category = str((qs.get("category") or ["ALL"])[0])
            severity = str((qs.get("severity") or ["ALL"])[0])
            source = str((qs.get("source") or [""])[0])
            equipment = str((qs.get("equipment") or [""])[0])
            event_id_raw = (qs.get("event_id") or [""])[0]
            event_id = int(event_id_raw) if str(event_id_raw).strip().isdigit() else None
            ai_provider = str((qs.get("ai_provider") or ["local"])[0])

            cfg = load_config(base_dir)
            snap = SESSION_STATE.get("last_snapshot") or {}
            res = run_full_crash_investigation(
                base_dir=base_dir,
                period_hours=period_hours,
                severity_filter=severity,
                category_filter=category,
                source_filter=source,
                event_id_filter=event_id,
                equipment_filter=equipment,
                snapshot=snap,
                use_ai=ai_provider.lower() in ("gemini", "grok"),
                ai_provider=ai_provider,
                api_key=str(cfg.get("gemini_api_key") or ""),
                grok_api_key=str(cfg.get("grok_api_key") or ""),
                user_role=sess.get("role", "trial"),
            )
            SESSION_STATE["last_crash_investigation"] = res
            if SESSION_STATE.get("last_snapshot"):
                SESSION_STATE["last_snapshot"]["crash_investigation"] = res
            inc_sum = res.get("incident_summary") or {}
            log_action(
                f"Crash Investigator ({period_hours}h | {category})",
                f"{inc_sum.get('total_events_collected', 0)} evento(s), {inc_sum.get('bugcheck_count', 0)} BSOD(s), Severidade: {inc_sum.get('overall_severity')}",
            )
            self._send_json(
                {
                    "success": True,
                    "crash_investigation": res,
                    "safe_actions_catalog": SAFE_CRASH_ACTIONS_CATALOG,
                    "action_logs": SESSION_STATE["action_logs"],
                }
            )
            return

        if route == "/api/crash-investigator/history":
            if not self._require_auth():
                return
            limit = int((qs.get("limit") or [20])[0])
            offset = int((qs.get("offset") or [0])[0])
            ph_raw = (qs.get("period_hours") or [None])[0]
            period_hours_f = int(ph_raw) if ph_raw and str(ph_raw).isdigit() else None
            sev_f = str((qs.get("severity") or [""])[0])

            hist = list_crash_investigations(
                base_dir=base_dir,
                limit=limit,
                offset=offset,
                period_hours_filter=period_hours_f,
                severity_filter=sev_f,
            )
            self._send_json(hist)
            return

        if route == "/api/crash-investigator/compare":
            if not self._require_auth():
                return
            older_id = (qs.get("older_id") or [None])[0]
            newer_id = (qs.get("newer_id") or [None])[0]
            hist = list_crash_investigations(base_dir=base_dir, limit=25)
            items = hist.get("items") or []
            if not items:
                self._send_json({"success": False, "message": "Histórico insuficiente no SQLite para comparar períodos."}, status=400)
                return
            if older_id and newer_id:
                eval_older = next((it for it in items if str(it.get("id")) == str(older_id)), None)
                eval_newer = next((it for it in items if str(it.get("id")) == str(newer_id)), None)
                if not eval_older or not eval_newer:
                    self._send_json({"success": False, "message": "Investigações solicitadas não encontradas no SQLite."}, status=404)
                    return
            elif len(items) >= 2:
                eval_newer = items[0]
                eval_older = items[1]
            else:
                eval_newer = items[0]
                eval_older = items[0]

            comp = compare_crash_investigations(eval_older, eval_newer)
            self._send_json({"success": True, "comparison": comp, **comp})
            return

        if route == "/api/storage/scan":
            if not self._require_auth():
                return
            importance = (qs.get("importance") or ["alta"])[0]
            storage_suite = build_complete_storage_suite_payload(base_dir=base_dir, data_importance=importance)
            if SESSION_STATE.get("last_snapshot"):
                SESSION_STATE["last_snapshot"]["storage_suite"] = storage_suite
            log_action("Auditoria Forense de Discos & SMART", f"{storage_suite.get('total_physical_disks', 0)} dispositivo(s) analisado(s).")
            self._send_json({"success": True, "storage_suite": storage_suite, "action_logs": SESSION_STATE["action_logs"]})
            return

        if route == "/api/admin/crm/list":
            if not self._require_auth(require_admin=True):
                return
            q = (qs.get("q") or [""])[0]
            clients = list_crm_clients(base_dir, search_query=q)
            self._send_json(
                {
                    "success": True,
                    "clients": clients,
                    "pricing_catalog": FAIR_PRICING_CATALOG,
                }
            )
            return

        if route == "/api/logs":
            if not self._require_auth():
                return
            self._send_json({"action_logs": SESSION_STATE["action_logs"]})
            return

        if route.startswith("/reports/"):
            rel_name = os.path.basename(unquote(route.replace("/reports/", "", 1)))
            reports_root = (base_dir / "reports").resolve()
            target = (reports_root / rel_name).resolve()
            if target.parent == reports_root and target.exists() and target.is_file():
                content = target.read_bytes()
                is_pdf = target.suffix.lower() == ".pdf"
                is_dl = (qs.get("download") or ["0"])[0] in ("1", "true", "yes")
                ctype = "application/pdf" if is_pdf else "text/html; charset=utf-8"
                disp = "attachment" if is_dl else "inline"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Content-Disposition", f'{disp}; filename="{target.name}"')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
                return
            self._send_json(
                {
                    "success": False,
                    "error": "report_file_not_found",
                    "error_stage": "file_delivery",
                    "message": f"O arquivo de relatório solicitado ('{rel_name}') não foi encontrado em {reports_root}.",
                },
                status=404,
            )
            return

        frontend_dir = base_dir / "frontend"
        if not frontend_dir.exists() and getattr(sys, "_MEIPASS", None):
            frontend_dir = Path(sys._MEIPASS) / "frontend"
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
        try:
            self._handle_post()
        except Exception as exc:
            self._send_json(
                {
                    "success": False,
                    "error": "internal_server_error",
                    "error_stage": "http_post_handler",
                    "message": f"Erro interno no servidor (POST): {exc}",
                },
                status=500,
            )

    def _handle_post(self):
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
            self._send_json(
                {
                    "success": True,
                    "message": "Contador Trial desta máquina foi zerado (0 de 4 análises usadas).",
                    "action_logs": SESSION_STATE["action_logs"],
                }
            )
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
            self._send_json(
                {
                    "success": True,
                    "clients": list_crm_clients(base_dir),
                    "action_logs": SESSION_STATE["action_logs"],
                }
            )
            return

        sess = self._require_auth()
        if not sess:
            return

        # ==================== ROTAS POST: AEGISPULSE CRASH INVESTIGATOR (v5.5) ====================
        if route == "/api/crash-investigator/run":
            period_days = int(body.get("period_days", 7) or 7)
            period_hours = int(body.get("period_hours") or (period_days * 24))
            category = str(body.get("category", "ALL") or "ALL")
            severity = str(body.get("severity", "ALL") or "ALL")
            source = str(body.get("source", "") or "")
            equipment = str(body.get("equipment", "") or "")
            event_id_raw = body.get("event_id")
            event_id = int(event_id_raw) if event_id_raw is not None and str(event_id_raw).strip().isdigit() else None
            ai_provider = str(body.get("ai_provider", "local") or "local")

            cfg = load_config(base_dir)
            api_key = str(body.get("api_key") or cfg.get("gemini_api_key") or "")
            grok_key = str(body.get("grok_api_key") or cfg.get("grok_api_key") or "")
            raw_override = body.get("raw_override") or body.get("mock_evidence")
            if not isinstance(raw_override, dict):
                raw_override = None

            snap = dict(SESSION_STATE.get("last_snapshot") or {})
            if isinstance(body.get("snapshot"), dict):
                snap.update(body["snapshot"])

            res = run_full_crash_investigation(
                base_dir=base_dir,
                period_hours=period_hours,
                severity_filter=severity,
                category_filter=category,
                source_filter=source,
                event_id_filter=event_id,
                equipment_filter=equipment,
                snapshot=snap,
                use_ai=bool(body.get("use_ai")) or ai_provider.lower() in ("gemini", "grok"),
                ai_provider=ai_provider,
                api_key=api_key,
                grok_api_key=grok_key,
                user_role=sess.get("role", "trial"),
                raw_override=raw_override,
            )
            SESSION_STATE["last_crash_investigation"] = res
            if SESSION_STATE.get("last_snapshot"):
                SESSION_STATE["last_snapshot"]["crash_investigation"] = res
            inc_sum = res.get("incident_summary") or {}
            log_action(
                f"Crash Investigator ({period_hours}h | {category})",
                f"Investigação concluída: {inc_sum.get('total_events_collected', 0)} evento(s), {inc_sum.get('bugcheck_count', 0)} BSOD(s), Severidade: {inc_sum.get('overall_severity')}",
            )
            self._send_json(
                {
                    "success": True,
                    "crash_investigation": res,
                    "safe_actions_catalog": SAFE_CRASH_ACTIONS_CATALOG,
                    "action_logs": SESSION_STATE["action_logs"],
                }
            )
            return

        if route == "/api/crash-investigator/action":
            action_id = str(body.get("action_id", ""))
            confirm_token = str(body.get("confirm_token", ""))
            inv_id_raw = body.get("investigation_id")
            inv_id = int(inv_id_raw) if inv_id_raw is not None and str(inv_id_raw).isdigit() else None

            res = execute_authorized_crash_action(
                base_dir=base_dir,
                action_id=action_id,
                confirm_token=confirm_token,
                investigation_id=inv_id,
            )
            log_action(
                f"Ação N3 Crash Investigator ({action_id})",
                res.get("message", ""),
            )
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        # ==================== ROTAS DO MÓDULO DE DISCOS, SMART & RECUPERAÇÃO (v4.0+) ====================
        if route == "/api/health-score/evaluate":
            with ThreadPoolExecutor(max_workers=6) as pool:
                f_hw = pool.submit(_safe_call, collect_hardware_info, default={})
                f_os = pool.submit(_safe_call, collect_os_info, default={})
                f_drv = pool.submit(_safe_call, collect_drivers_and_bios, default={})
                f_sw = pool.submit(_safe_call, collect_installed_software, default={})
                f_net = pool.submit(_safe_call, collect_network_diagnostics, default={})
                f_st = pool.submit(_safe_call, build_complete_storage_suite_payload, base_dir, default={})
                hw = f_hw.result()
                os_data = f_os.result()
                drv_bios = f_drv.result()
                sw = f_sw.result()
                net = f_net.result()
                storage_suite = f_st.result()
            gaming = _safe_call(audit_gaming_and_dlls, hardware=hw, default={})
            compat = _safe_call(analyze_hardware_compatibility, hardware=hw, os_info=os_data, default={})

            eval_res = compute_health_score(
                {
                    "hardware": hw,
                    "os": os_data,
                    "drivers_bios": drv_bios,
                    "software": sw,
                    "gaming": gaming,
                    "storage_suite": storage_suite,
                },
                base_dir=base_dir,
            )
            if SESSION_STATE.get("last_snapshot"):
                SESSION_STATE["last_snapshot"]["health_score"] = eval_res
            log_action(
                "Avaliação Health Score",
                f"Índice calculado: {eval_res['overall_score']}/100 ({eval_res['classification']}) — Cobertura: {eval_res['coverage']['percent']}%",
            )
            self._send_json({"success": True, "health_score": eval_res, "action_logs": SESSION_STATE["action_logs"]})
            return

        if route == "/api/storage/test":
            disk_num = int(body.get("disk_number", 0))
            dev_uid = str(body.get("device_uid", ""))
            test_type = str(body.get("test_type", "quick_health"))
            sample_mb = int(body.get("sample_mb", 16))
            block_kb = int(body.get("block_size_kb", 256))
            confirm_write = str(body.get("confirm_write_risk", ""))
            dev = _find_device_in_snapshot(disk_number=disk_num, device_uid=dev_uid)

            res = run_storage_integrity_test(
                base_dir=base_dir,
                device=dev,
                test_type=test_type,
                sample_mb=sample_mb,
                block_size_kb=block_kb,
                confirm_write_risk=confirm_write,
            )
            log_action(f"Teste de Disco ({test_type})", f"{dev.get('model')}: {res.get('message')}")
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/storage/recovery/image":
            disk_num = int(body.get("disk_number", 0))
            dev_uid = str(body.get("device_uid", ""))
            dest_path = str(body.get("destination_path", ""))
            confirm_token = str(body.get("confirm_token", ""))
            max_mb = int(body.get("max_mb", 16))
            resume_flag = bool(body.get("resume", True))
            dev = _find_device_in_snapshot(disk_number=disk_num, device_uid=dev_uid)

            res = create_or_resume_disk_image(
                base_dir=base_dir,
                source_device=dev,
                destination_image_path=dest_path,
                confirm_token=confirm_token,
                max_bytes_limit=max_mb * 1024 * 1024,
                resume=resume_flag,
            )
            log_action("Clonagem / Imagem de Disco", res.get("message", ""))
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/storage/recovery/cancel":
            dev_uid = str(body.get("device_uid", ""))
            res = cancel_active_clone_job(dev_uid)
            log_action("Cancelamento Seguro de Imagem", res.get("message", ""))
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/storage/recovery/partitions":
            disk_num = int(body.get("disk_number", 0))
            dev_uid = str(body.get("device_uid", ""))
            img_override = str(body.get("image_path", "")).strip() or None
            dev = _find_device_in_snapshot(disk_number=disk_num, device_uid=dev_uid)

            res = inspect_and_recover_partitions(
                base_dir=base_dir,
                device=dev,
                image_or_target_override=img_override,
            )
            log_action("Recuperação / Inspeção de Partições", res.get("message", ""))
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/storage/recovery/files":
            disk_num = int(body.get("disk_number", 0))
            dev_uid = str(body.get("device_uid", ""))
            dest_folder = str(body.get("destination_folder", ""))
            src_override = str(body.get("source_image_path", "")).strip() or None
            dev = _find_device_in_snapshot(disk_number=disk_num, device_uid=dev_uid)

            res = recover_files_assisted(
                base_dir=base_dir,
                source_device=dev,
                destination_folder=dest_folder,
                source_override_path=src_override,
            )
            log_action("Recuperação Assistida de Arquivos", res.get("message", ""))
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/storage/recovery/logical-repair":
            disk_num = int(body.get("disk_number", 0))
            dev_uid = str(body.get("device_uid", ""))
            drive_letter = str(body.get("drive_letter", "C:"))
            mode = str(body.get("mode", "diagnose_only"))
            confirm_rep = str(body.get("confirm_repair", ""))
            dev = _find_device_in_snapshot(disk_number=disk_num, device_uid=dev_uid)

            res = execute_logical_repair(
                base_dir=base_dir,
                device=dev,
                drive_letter=drive_letter,
                mode=mode,
                confirm_repair=confirm_rep,
            )
            log_action(f"Reparação Lógica ({mode})", res.get("message", ""))
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        # ==================== v5.1: CENTRAL SUPREMA DISKPART COM VALIDAÇÃO CENTRALIZADA OBRIGATÓRIA ====================
        if route == "/api/storage/diskpart/unlock":
            req_num = int(body["disk_number"]) if body.get("disk_number") is not None else None
            dev_uid = str(body.get("device_uid", ""))
            init_raw = bool(body.get("initialize_if_raw", False))
            dev, st = _resolve_storage_device_strict(disk_number=req_num, device_uid=dev_uid)

            res = force_unlock_and_revive_disk(
                base_dir=base_dir,
                device=dev,
                initialize_if_raw=init_raw,
                requested_disk_number=req_num,
                requested_device_uid=dev_uid,
                occupied_drive_letters=st.get("occupied_drive_letters"),
                query_telemetry=st.get("query_telemetry"),
            )
            if res.get("success"):
                updated_st = _safe_call(build_complete_storage_suite_payload, base_dir, default={})
                if SESSION_STATE.get("last_snapshot") and updated_st:
                    SESSION_STATE["last_snapshot"]["storage_suite"] = updated_st
                res["storage_suite"] = updated_st
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            log_action("Desbloqueio Seguro de Disco", res.get("message", ""))
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/storage/diskpart/assign-letter":
            req_num = int(body["disk_number"]) if body.get("disk_number") is not None else None
            dev_uid = str(body.get("device_uid", ""))
            desired_letter = str(body.get("desired_letter", "AUTO"))
            part_num = int(body.get("partition_number", 0) or 0)
            dev, st = _resolve_storage_device_strict(disk_number=req_num, device_uid=dev_uid)

            res = assign_or_change_drive_letter(
                base_dir=base_dir,
                device=dev,
                desired_letter=desired_letter,
                partition_number=part_num,
                requested_disk_number=req_num,
                requested_device_uid=dev_uid,
                occupied_drive_letters=st.get("occupied_drive_letters"),
                query_telemetry=st.get("query_telemetry"),
            )
            if res.get("success"):
                updated_st = _safe_call(build_complete_storage_suite_payload, base_dir, default={})
                if SESSION_STATE.get("last_snapshot") and updated_st:
                    SESSION_STATE["last_snapshot"]["storage_suite"] = updated_st
                res["storage_suite"] = updated_st
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            log_action(f"Atribuir Letra ({desired_letter})", res.get("message", ""))
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/storage/diskpart/format":
            req_num = int(body["disk_number"]) if body.get("disk_number") is not None else None
            dev_uid = str(body.get("device_uid", ""))
            confirm_uid = str(body.get("confirm_device_uid", ""))
            fs = str(body.get("filesystem", "NTFS"))
            label = str(body.get("volume_label", "AEGIS_DISK"))
            quick = bool(body.get("quick_format", True))
            p_style = str(body.get("partition_style", "GPT"))
            full_rep = bool(body.get("full_repartition", False))
            desired_letter = str(body.get("desired_letter", "AUTO"))
            confirm_tok = str(body.get("confirm_token", ""))
            dev, st = _resolve_storage_device_strict(disk_number=req_num, device_uid=dev_uid)

            res = format_and_partition_disk(
                base_dir=base_dir,
                device=dev,
                filesystem=fs,
                volume_label=label,
                quick_format=quick,
                partition_style=p_style,
                full_repartition=full_rep,
                desired_letter=desired_letter,
                confirm_token=confirm_tok,
                confirm_device_uid=confirm_uid,
                requested_disk_number=req_num,
                requested_device_uid=dev_uid,
                occupied_drive_letters=st.get("occupied_drive_letters"),
                query_telemetry=st.get("query_telemetry"),
            )
            if res.get("success"):
                updated_st = _safe_call(build_complete_storage_suite_payload, base_dir, default={})
                if SESSION_STATE.get("last_snapshot") and updated_st:
                    SESSION_STATE["last_snapshot"]["storage_suite"] = updated_st
                res["storage_suite"] = updated_st
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            log_action(f"Formatação DiskPart ({fs})", res.get("message", ""))
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/storage/diskpart/action":
            req_num = int(body["disk_number"]) if body.get("disk_number") is not None else None
            dev_uid = str(body.get("device_uid", ""))
            confirm_uid = str(body.get("confirm_device_uid", ""))
            dp_action = str(body.get("action", "detail_disk"))
            custom_scr = str(body.get("custom_script", ""))
            sz_mb = int(body.get("size_mb", 0) or 0)
            confirm_tok = str(body.get("confirm_token", ""))
            dev, st = _resolve_storage_device_strict(disk_number=req_num, device_uid=dev_uid)

            res = execute_diskpart_action(
                base_dir=base_dir,
                device=dev,
                action=dp_action,
                custom_script=custom_scr,
                size_mb=sz_mb,
                confirm_token=confirm_tok,
                confirm_device_uid=confirm_uid,
                requested_disk_number=req_num,
                requested_device_uid=dev_uid,
                occupied_drive_letters=st.get("occupied_drive_letters"),
                query_telemetry=st.get("query_telemetry"),
            )
            if res.get("success") and dp_action != "detail_disk":
                updated_st = _safe_call(build_complete_storage_suite_payload, base_dir, default={})
                if SESSION_STATE.get("last_snapshot") and updated_st:
                    SESSION_STATE["last_snapshot"]["storage_suite"] = updated_st
                res["storage_suite"] = updated_st
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            log_action(f"DiskPart ({dp_action})", res.get("message", ""))
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/storage/diskpart/bootable":
            req_num = int(body["disk_number"]) if body.get("disk_number") is not None else None
            dev_uid = str(body.get("device_uid", ""))
            confirm_uid = str(body.get("confirm_device_uid", ""))
            iso_path = str(body.get("iso_path", ""))
            boot_scheme = str(body.get("boot_scheme", "UEFI_GPT"))
            fs = str(body.get("filesystem", "NTFS"))
            label = str(body.get("volume_label", "AEGIS_BOOT"))
            confirm_tok = str(body.get("confirm_token", ""))
            dev, st = _resolve_storage_device_strict(disk_number=req_num, device_uid=dev_uid)

            res = create_bootable_usb_drive(
                base_dir=base_dir,
                device=dev,
                iso_path=iso_path,
                boot_scheme=boot_scheme,
                filesystem=fs,
                volume_label=label,
                confirm_token=confirm_tok,
                confirm_device_uid=confirm_uid,
                requested_disk_number=req_num,
                requested_device_uid=dev_uid,
                occupied_drive_letters=st.get("occupied_drive_letters"),
                query_telemetry=st.get("query_telemetry"),
            )
            if res.get("success"):
                updated_st = _safe_call(build_complete_storage_suite_payload, base_dir, default={})
                if SESSION_STATE.get("last_snapshot") and updated_st:
                    SESSION_STATE["last_snapshot"]["storage_suite"] = updated_st
                res["storage_suite"] = updated_st
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            log_action(f"Criador Bootável ({boot_scheme})", res.get("message", ""))
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        # ==================== DEMAIS ROTAS EXISTENTES ====================
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
                    "storage_suite": build_complete_storage_suite_payload(base_dir=base_dir),
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
            try:
                client_snap = body.get("snapshot") if isinstance(body.get("snapshot"), dict) else None
                snapshot = dict(SESSION_STATE.get("last_snapshot") or {})
                if client_snap:
                    for k, v in client_snap.items():
                        if v is not None and not snapshot.get(k):
                            snapshot[k] = v
                if not snapshot:
                    hw = _safe_call(collect_hardware_info, default={})
                    os_d = _safe_call(collect_os_info, default={})
                    snapshot = {
                        "hardware": hw,
                        "os": os_d,
                        "drivers_bios": _safe_call(collect_drivers_and_bios, default={}),
                        "software": _safe_call(collect_installed_software, default={}),
                        "gaming": _safe_call(audit_gaming_and_dlls, hardware=hw, default={}),
                        "compatibility": _safe_call(analyze_hardware_compatibility, hw, os_d, default={}),
                        "storage_suite": _safe_call(build_complete_storage_suite_payload, base_dir=base_dir, default={}),
                    }
                    SESSION_STATE["last_snapshot"] = snapshot

                if isinstance(body.get("crash_investigation"), dict) and body.get("crash_investigation"):
                    snapshot["crash_investigation"] = body["crash_investigation"]
                elif SESSION_STATE.get("last_crash_investigation") and not snapshot.get("crash_investigation"):
                    snapshot["crash_investigation"] = SESSION_STATE["last_crash_investigation"]

                ai_text = str(body.get("ai_analysis") or SESSION_STATE.get("last_ai_analysis") or "")
                out_dir_override = body.get("_test_output_dir")
                target_base_dir = Path(out_dir_override) if out_dir_override else base_dir

                if body.get("_simulate_generator_error"):
                    raise RuntimeError("Falha interna simulada no motor de renderização de relatórios.")

                res = generate_html_report(
                    snapshot=snapshot,
                    base_dir=target_base_dir,
                    ai_analysis=ai_text,
                    action_logs=SESSION_STATE["action_logs"],
                )
                if not res.get("success"):
                    self._send_json(res, status=500)
                    return

                auto_open = bool(body.get("auto_open", True))
                if auto_open and res.get("report_path") and sys.platform.startswith("win"):
                    try:
                        os.startfile(res["report_path"])
                    except Exception:
                        pass

                log_action(
                    "Exportação de Laudo HTML & PDF v5.5",
                    f"Arquivos gerados: {res.get('filename')} ({res.get('html_size_bytes')} B) | {res.get('pdf_filename')} ({res.get('pdf_size_bytes')} B)",
                )
                res["action_logs"] = SESSION_STATE["action_logs"]
                self._send_json(res, status=200)
                return
            except Exception as rep_exc:
                err_payload = {
                    "success": False,
                    "error": "report_generation_failed",
                    "error_stage": "internal_generator_exception",
                    "message": f"Erro interno ao gerar laudo HTML/PDF: {rep_exc}",
                }
                self._send_json(err_payload, status=500)
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
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((host, port), AegisPulseRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Encerrando servidor AegisPulse...")
        server.server_close()
