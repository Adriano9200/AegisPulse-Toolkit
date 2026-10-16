from concurrent.futures import ThreadPoolExecutor
import sys
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/server.py (Servidor HTTP/REST API v4.0 com Storage Forensics)
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.0.0
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
from backend.services.health_score import (
    compute_health_score,
    get_latest_health_score,
    list_health_score_history,
    compare_health_evaluations,
)
from backend.services.storage_health import (
    build_complete_storage_suite_payload,
    list_storage_operations_log,
)
from backend.services.storage_diagnostics import run_storage_integrity_test
from backend.services.storage_recovery import (
    create_or_resume_disk_image,
    cancel_active_clone_job,
    inspect_and_recover_partitions,
    recover_files_assisted,
    execute_logical_repair,
    force_unlock_and_revive_disk,
    assign_or_change_drive_letter,
    format_and_partition_disk,
    execute_diskpart_action,
    create_bootable_usb_drive,
)
from backend.services.gemini_ai import check_internet_connection, query_gemini_ai
from backend.services.html_reporter import generate_html_report

SESSION_STATE = {
    "base_dir": Path("."),
    "last_snapshot": {},
    "last_ai_analysis": "",
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


def _find_device_in_snapshot(disk_number: int = 0, device_uid: str = "") -> dict:
    snap = SESSION_STATE.get("last_snapshot") or {}
    st = snap.get("storage_suite") or {}
    devs = st.get("devices") or []
    for d in devs:
        if (device_uid and d.get("device_uid") == device_uid) or int(d.get("disk_number", -1)) == int(disk_number):
            return d
    if devs:
        return devs[0]
    fresh = build_complete_storage_suite_payload(SESSION_STATE["base_dir"])
    if fresh.get("devices"):
        return fresh["devices"][0]
    return {"device_uid": "DISK_0", "disk_number": 0, "model": "Disco Principal", "drive_letters": ["C:"], "capacity": {"bytes": 0}}


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
                "pricing_catalog": FAIR_PRICING_CATALOG if updated_sess.get("role") == "admin" else [],
                "action_logs": SESSION_STATE["action_logs"],
            }
            SESSION_STATE["last_snapshot"] = snapshot
            log_action(
                f"Diagnóstico Completo & Health Score v4.5 ({updated_sess.get('role', 'user').upper()})",
                f"Varredura executada em {hw.get('hostname')} ({storage_suite.get('total_physical_disks', 1)} disco(s) auditado(s) | {msg})",
            )
            self._send_json(snapshot)
            return

        if route == "/api/health-score/latest":
            if not self._require_auth():
                return
            latest = get_latest_health_score(base_dir)
            if not latest:
                # Se não houver no banco, gera a partir do snapshot atual
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
                    self._send_json({"success": False, "message": "Histórico insuficiente para comparação (mínimo de 1 avaliação)."}, status=400)
                    return
            else:
                eval_older = next((it for it in items if str(it.get("id")) == str(older_id)), None)
                eval_newer = next((it for it in items if str(it.get("id")) == str(newer_id)), None)
                if not eval_older or not eval_newer:
                    self._send_json({"success": False, "message": "Uma das avaliações solicitadas não foi encontrada no histórico."}, status=404)
                    return

            diff = compare_health_evaluations(eval_older, eval_newer)
            self._send_json({"success": True, "comparison": diff})
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

        # ==================== ROTAS DO MÓDULO DE DISCOS, SMART & RECUPERAÇÃO (v4.0) ====================
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
            log_action("Avaliação Health Score", f"Índice calculado: {eval_res['overall_score']}/100 ({eval_res['classification']}) — Cobertura: {eval_res['coverage']['percent']}%")
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

        # ==================== v5.0: CENTRAL SUPREMA DISKPART, DESBLOQUEIO, FORMATAÇÃO & BOOTÁVEL ====================
        if route == "/api/storage/diskpart/unlock":
            disk_num = int(body.get("disk_number", 0))
            dev_uid = str(body.get("device_uid", ""))
            init_raw = bool(body.get("initialize_if_raw", True))
            dev = _find_device_in_snapshot(disk_number=disk_num, device_uid=dev_uid)

            res = force_unlock_and_revive_disk(base_dir=base_dir, device=dev, initialize_if_raw=init_raw)
            updated_st = _safe_call(build_complete_storage_suite_payload, base_dir, default={})
            if SESSION_STATE.get("last_snapshot") and updated_st:
                SESSION_STATE["last_snapshot"]["storage_suite"] = updated_st
            res["storage_suite"] = updated_st
            res["operations_log"] = list_storage_operations_log(base_dir, limit=35)
            log_action("Desbloqueio Forçado de Disco", res.get("message", ""))
            res["action_logs"] = SESSION_STATE["action_logs"]
            self._send_json(res)
            return

        if route == "/api/storage/diskpart/assign-letter":
            disk_num = int(body.get("disk_number", 0))
            dev_uid = str(body.get("device_uid", ""))
            desired_letter = str(body.get("desired_letter", "AUTO"))
            part_num = int(body.get("partition_number", 0))
            dev = _find_device_in_snapshot(disk_number=disk_num, device_uid=dev_uid)

            res = assign_or_change_drive_letter(
                base_dir=base_dir,
                device=dev,
                desired_letter=desired_letter,
                partition_number=part_num,
            )
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
            disk_num = int(body.get("disk_number", 0))
            dev_uid = str(body.get("device_uid", ""))
            fs = str(body.get("filesystem", "NTFS"))
            label = str(body.get("volume_label", "AEGIS_DISK"))
            quick = bool(body.get("quick_format", True))
            p_style = str(body.get("partition_style", "GPT"))
            full_rep = bool(body.get("full_repartition", False))
            desired_letter = str(body.get("desired_letter", "AUTO"))
            confirm_tok = str(body.get("confirm_token", ""))
            dev = _find_device_in_snapshot(disk_number=disk_num, device_uid=dev_uid)

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
            disk_num = int(body.get("disk_number", 0))
            dev_uid = str(body.get("device_uid", ""))
            dp_action = str(body.get("action", "detail_disk"))
            custom_scr = str(body.get("custom_script", ""))
            sz_mb = int(body.get("size_mb", 0) or 0)
            confirm_tok = str(body.get("confirm_token", ""))
            dev = _find_device_in_snapshot(disk_number=disk_num, device_uid=dev_uid)

            res = execute_diskpart_action(
                base_dir=base_dir,
                device=dev,
                action=dp_action,
                custom_script=custom_scr,
                size_mb=sz_mb,
                confirm_token=confirm_tok,
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
            disk_num = int(body.get("disk_number", 0))
            dev_uid = str(body.get("device_uid", ""))
            iso_path = str(body.get("iso_path", ""))
            boot_scheme = str(body.get("boot_scheme", "UEFI_GPT"))
            fs = str(body.get("filesystem", "NTFS"))
            label = str(body.get("volume_label", "AEGIS_BOOT"))
            confirm_tok = str(body.get("confirm_token", ""))
            dev = _find_device_in_snapshot(disk_number=disk_num, device_uid=dev_uid)

            res = create_bootable_usb_drive(
                base_dir=base_dir,
                device=dev,
                iso_path=iso_path,
                boot_scheme=boot_scheme,
                filesystem=fs,
                volume_label=label,
                confirm_token=confirm_tok,
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
                    "storage_suite": build_complete_storage_suite_payload(base_dir=base_dir),
                }
                SESSION_STATE["last_snapshot"] = snapshot

            res = generate_html_report(
                snapshot=snapshot,
                base_dir=base_dir,
                ai_analysis=SESSION_STATE.get("last_ai_analysis", ""),
                action_logs=SESSION_STATE["action_logs"],
            )
            log_action("Exportação de Laudo HTML v4.0", f"Arquivo gerado: {res.get('filename')}")
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
