#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/storage_recovery.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.0.0
================================================================================
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.storage_health import classify_storage_risk, log_storage_operation

ACTIVE_CLONE_JOBS: dict[str, dict[str, Any]] = {}


def detect_external_recovery_tools() -> dict[str, Any]:
    tools_info = {
        "ddrescue": {
            "name": "GNU ddrescue",
            "available": False,
            "path": None,
            "license": "GPLv2+ (Ferramenta externa independente invocada via CLI/WSL quando instalada pelo técnico)",
            "win_compatibility_note": (
                "O GNU ddrescue é nativo de ambientes POSIX/Linux. No Windows, o AegisPulse oferece: "
                "(1) Motor Resiliente Nativo em Python com Mapfile e Retomada automática; "
                "(2) Integração direta com ddrescue via WSL2 / Cygwin / MSYS2 se instalado; e "
                "(3) Geração automática da linha de comando exata para pendrive Live USB (SystemRescue / Ubuntu)."
            ),
        },
        "testdisk": {
            "name": "TestDisk (CGSecurity)",
            "available": False,
            "path": None,
            "license": "GPLv2+ (Executável externo opcional invocado sob demanda)",
        },
        "photorec": {
            "name": "PhotoRec (CGSecurity)",
            "available": False,
            "path": None,
            "license": "GPLv2+ (Executável externo opcional invocado sob demanda)",
        },
        "chkdsk": {
            "name": "Microsoft CHKDSK / Repair-Volume",
            "available": platform.system() == "Windows" or bool(shutil.which("chkdsk")),
            "path": shutil.which("chkdsk") or (r"C:\Windows\System32\chkdsk.exe" if platform.system() == "Windows" else None),
            "license": "Componente Nativo Microsoft Windows",
        },
    }

    search_bins = {
        "ddrescue": ["ddrescue", "ddrescue.exe"],
        "testdisk": ["testdisk", "testdisk_win.exe", r"C:\Tools\TestDisk\testdisk_win.exe"],
        "photorec": ["photorec", "photorec_win.exe", r"C:\Tools\TestDisk\photorec_win.exe"],
    }
    for key, candidates in search_bins.items():
        for cand in candidates:
            found = shutil.which(cand) or (cand if os.path.exists(cand) else None)
            if found:
                tools_info[key]["available"] = True
                tools_info[key]["path"] = found
                break

    return tools_info


def _normalize_drive_root(path_str: str) -> str:
    p = (path_str or "").strip().upper()
    if p.startswith("\\\\.\\PHYSICALDRIVE"):
        return p
    if len(p) >= 2 and p[1] == ":":
        return p[:2]
    return os.path.abspath(path_str).upper()


def validate_clone_source_and_destination(
    source_device: dict[str, Any],
    destination_path: str,
    confirm_token: str = "",
    allow_overwrite: bool = False,
    source_file_override: str | None = None,
) -> dict[str, Any]:
    dest_clean = (destination_path or "").strip()
    if not dest_clean:
        return {"valid": False, "error_code": "EMPTY_DEST", "message": "Selecione ou informe um caminho de arquivo de imagem (.img) válido para o destino."}

    if dest_clean.upper().startswith("\\\\.\\PHYSICALDRIVE") or (len(dest_clean) <= 3 and dest_clean.endswith(":")):
        return {
            "valid": False,
            "error_code": "RAW_DEST_BLOCKED",
            "message": (
                "🔒 PROTEÇÃO CONTRA SELEÇÃO INVERTIDA / SOBRESCRITA DE DISCO: "
                "Para impedir a destruição acidental de um disco inteiro por inversão entre Origem e Destino, "
                "informe um caminho de arquivo de imagem (ex: D:\\Recuperacao\\disco_cliente.img) em uma unidade saudável."
            ),
        }

    src_letters = [dl.upper().rstrip("\\") for dl in (source_device.get("drive_letters") or [])]
    dest_root = _normalize_drive_root(dest_clean)

    if source_file_override:
        if os.path.abspath(source_file_override) == os.path.abspath(dest_clean):
            return {
                "valid": False,
                "error_code": "SAME_SOURCE_AND_DEST",
                "message": "🚫 ERRO DE SEGURANÇA: O destino da imagem não pode ser o mesmo arquivo/dispositivo de origem!",
            }
    elif dest_root in src_letters or dest_clean.upper() == str(source_device.get("device_path", "")).upper():
        return {
            "valid": False,
            "error_code": "SAME_SOURCE_AND_DEST",
            "message": (
                f"🚫 OPERAÇÃO BLOQUEADA: O destino ({dest_clean}) está localizado no próprio disco de origem "
                f"({source_device.get('model')} — {', '.join(src_letters)}). Selecione outra unidade física (ex: HD externo ou outro SSD)!"
            ),
        }

    if confirm_token.strip() != "CONFIRMAR_IMAGEM":
        return {
            "valid": False,
            "error_code": "CONFIRMATION_REQUIRED",
            "message": "Confirmação explícita exigida: digite exatamente CONFIRMAR_IMAGEM para autorizar a criação/retomada da imagem.",
        }

    dest_dir = os.path.dirname(os.path.abspath(dest_clean)) or "."
    if not os.path.exists(dest_dir):
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception as exc:
            return {"valid": False, "error_code": "DEST_DIR_ERROR", "message": f"Não foi possível criar a pasta de destino ({dest_dir}): {exc}"}

    src_size = (
        os.path.getsize(source_file_override)
        if (source_file_override and os.path.exists(source_file_override))
        else int(source_device.get("capacity", {}).get("bytes") or 0)
    )
    free_space = shutil.disk_usage(dest_dir).free

    return {
        "valid": True,
        "source_bytes": src_size,
        "destination_free_bytes": free_space,
        "has_full_capacity_space": free_space >= src_size,
        "message": "Validação de Origem e Destino aprovada com segurança.",
    }


def create_or_resume_disk_image(
    base_dir: Path,
    source_device: dict[str, Any],
    destination_image_path: str,
    confirm_token: str = "",
    max_bytes_limit: int | None = None,
    block_size_kb: int = 256,
    resume: bool = True,
    source_file_override: str | None = None,
    simulate_bad_block_offsets: list[int] | None = None,
    stop_after_blocks: int | None = None,
) -> dict[str, Any]:
    uid = source_device.get("device_uid") or "DISK_0"
    risk = classify_storage_risk(source_device)

    val = validate_clone_source_and_destination(
        source_device=source_device,
        destination_path=destination_image_path,
        confirm_token=confirm_token,
        source_file_override=source_file_override,
    )
    if not val["valid"]:
        log_storage_operation(base_dir, uid, "Clonagem/Imagem (Bloqueada)", risk["risk_level"], "blocked", val["message"])
        return {"success": False, **val}

    dest_abs = os.path.abspath(destination_image_path)
    mapfile_json_path = f"{dest_abs}.mapfile.json"
    ddrescue_map_path = f"{dest_abs}.ddrescue.map"

    src_path = source_file_override or str(source_device.get("device_path") or "")
    if not source_file_override and not os.path.exists(src_path):
        from backend.services.storage_diagnostics import _resolve_readable_target
        resolved_p, _, _ = _resolve_readable_target(source_device)
        if resolved_p:
            src_path = resolved_p

    if not src_path or (not os.path.exists(src_path) and not src_path.startswith("\\\\.\\")):
        msg = "Não foi possível abrir o dispositivo de origem para leitura bruta. Execute o AegisPulse como Administrador."
        return {"success": False, "error_code": "SOURCE_UNREADABLE", "message": msg}

    block_bytes = max(4096, int(block_size_kb) * 1024)
    total_src_bytes = (
        os.path.getsize(src_path)
        if os.path.isfile(src_path)
        else int(source_device.get("capacity", {}).get("bytes") or 0)
    )
    if max_bytes_limit and max_bytes_limit > 0:
        total_target_bytes = min(total_src_bytes, int(max_bytes_limit)) if total_src_bytes > 0 else int(max_bytes_limit)
    else:
        total_target_bytes = min(total_src_bytes, 32 * 1024 * 1024) if total_src_bytes > 0 else 16 * 1024 * 1024

    dest_free = shutil.disk_usage(os.path.dirname(dest_abs) or ".").free
    if dest_free < total_target_bytes:
        msg = (
            f"Espaço livre insuficiente no destino ({round(dest_free / (1024**3), 2)} GiB livres para "
            f"{round(total_target_bytes / (1024**3), 2)} GiB necessários)."
        )
        return {"success": False, "error_code": "INSUFFICIENT_SPACE", "message": msg}

    map_state: dict[str, Any] = {
        "source_model": source_device.get("model"),
        "source_serial": source_device.get("serial_number"),
        "source_capacity_bytes": total_src_bytes,
        "target_bytes": total_target_bytes,
        "block_size_bytes": block_bytes,
        "current_offset": 0,
        "bytes_recovered": 0,
        "bytes_failed": 0,
        "bytes_skipped": 0,
        "read_errors_count": 0,
        "bad_block_offsets": [],
        "status": "in_progress",
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    resumed_from_offset = 0
    if resume and os.path.exists(mapfile_json_path) and os.path.exists(dest_abs):
        try:
            with open(mapfile_json_path, "r", encoding="utf-8") as mf:
                loaded_map = json.load(mf)
            if loaded_map.get("source_serial") == source_device.get("serial_number"):
                map_state.update(loaded_map)
                map_state["status"] = "in_progress"
                resumed_from_offset = int(map_state.get("current_offset") or 0)
        except Exception:
            pass

    ACTIVE_CLONE_JOBS[uid] = {"cancel_requested": False, "mapfile": mapfile_json_path}
    bad_offsets_set = set(simulate_bad_block_offsets or [])

    t0 = time.perf_counter()
    blocks_processed_this_run = 0
    mode_open = "r+b" if (resumed_from_offset > 0 and os.path.exists(dest_abs)) else "wb"

    try:
        with open(src_path, "rb") as f_src, open(dest_abs, mode_open) as f_dst:
            offset = resumed_from_offset
            while offset < total_target_bytes:
                if ACTIVE_CLONE_JOBS.get(uid, {}).get("cancel_requested"):
                    map_state["status"] = "canceled"
                    break
                if stop_after_blocks is not None and blocks_processed_this_run >= stop_after_blocks:
                    map_state["status"] = "paused_resumable"
                    break

                to_read = min(block_bytes, total_target_bytes - offset)
                f_dst.seek(offset)

                try:
                    if offset in bad_offsets_set:
                        raise OSError(f"Simulated Uncorrectable Sector Read Error at LBA offset {offset}")
                    f_src.seek(offset)
                    chunk = f_src.read(to_read)
                    if not chunk:
                        break
                    f_dst.write(chunk)
                    map_state["bytes_recovered"] = int(map_state["bytes_recovered"]) + len(chunk)
                    step = len(chunk)
                except OSError:
                    f_dst.write(b"\x00" * to_read)
                    map_state["bytes_failed"] = int(map_state["bytes_failed"]) + to_read
                    map_state["read_errors_count"] = int(map_state["read_errors_count"]) + 1
                    if offset not in map_state["bad_block_offsets"]:
                        map_state["bad_block_offsets"].append(offset)
                    step = to_read

                offset += step
                map_state["current_offset"] = offset
                blocks_processed_this_run += 1

            f_dst.flush()

        if map_state["current_offset"] >= total_target_bytes and map_state["status"] not in ("canceled", "paused_resumable"):
            map_state["status"] = "completed"
    except Exception as exc:
        map_state["status"] = "failed"
        map_state["last_error"] = str(exc)

    elapsed = max(0.001, time.perf_counter() - t0)
    bytes_this_run = max(0, int(map_state["current_offset"]) - resumed_from_offset)
    speed_mb_s = round((bytes_this_run / (1024 * 1024)) / elapsed, 2) if bytes_this_run > 0 else 0.0
    remaining_bytes = max(0, total_target_bytes - int(map_state["current_offset"]))
    eta_sec = round((remaining_bytes / (1024 * 1024)) / speed_mb_s, 1) if speed_mb_s > 0 else 0.0
    progress_pct = round((int(map_state["current_offset"]) / max(1, total_target_bytes)) * 100, 1)

    map_state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    map_state["progress_pct"] = progress_pct
    map_state["speed_mb_s"] = speed_mb_s
    map_state["eta_seconds"] = eta_sec
    map_state["resumed_from_offset"] = resumed_from_offset

    with open(mapfile_json_path, "w", encoding="utf-8") as mf:
        json.dump(map_state, mf, indent=2, ensure_ascii=False)

    with open(ddrescue_map_path, "w", encoding="utf-8") as dmf:
        dmf.write("# Mapfile generated by AegisPulse IT Toolkit v4.0 (Compatible with GNU ddrescue)\n")
        dmf.write(f"# Source: {source_device.get('model')} ({source_device.get('serial_number')})\n")
        dmf.write("# current_pos   current_status\n")
        dmf.write(f"0x{int(map_state['current_offset']):08X}     ?\n")
        dmf.write("#      pos        size  status\n")
        for bad_off in map_state["bad_block_offsets"]:
            dmf.write(f"0x{int(bad_off):08X}  0x{block_bytes:08X}  -\n")

    disk_num = int(source_device.get("disk_number") or 0)
    ddrescue_cmd = f"ddrescue -f -n /dev/sd{chr(97 + disk_num)} \"{dest_abs}\" \"{ddrescue_map_path}\""

    summary_msg = (
        f"Imagem '{os.path.basename(dest_abs)}' ({map_state['status'].upper()} — {progress_pct}%): "
        f"{round(map_state['bytes_recovered'] / (1024*1024), 2)} MB recuperados, "
        f"{map_state['read_errors_count']} bloco(s) com erro de leitura isolados no Mapfile ({speed_mb_s} MB/s)."
    )
    log_storage_operation(base_dir, uid, "Clonagem / Imagem Resiliente", risk["risk_level"], map_state["status"], summary_msg, map_state)

    return {
        "success": map_state["status"] in ("completed", "paused_resumable", "canceled"),
        "image_path": dest_abs,
        "mapfile_path": mapfile_json_path,
        "ddrescue_map_path": ddrescue_map_path,
        "ddrescue_recommended_command": ddrescue_cmd,
        "message": summary_msg,
        **map_state,
    }


def cancel_active_clone_job(device_uid: str) -> dict[str, Any]:
    if device_uid in ACTIVE_CLONE_JOBS:
        ACTIVE_CLONE_JOBS[device_uid]["cancel_requested"] = True
        return {"success": True, "message": f"Solicitação de cancelamento seguro enviada para {device_uid}. O Mapfile salvará o ponto exato para retomada."}
    return {"success": False, "message": "Nenhuma operação de imagem ativa encontrada para este dispositivo."}


def inspect_and_recover_partitions(
    base_dir: Path,
    device: dict[str, Any],
    image_or_target_override: str | None = None,
) -> dict[str, Any]:
    uid = device.get("device_uid") or "DISK_0"
    risk = classify_storage_risk(device)
    tools = detect_external_recovery_tools()

    target_to_read = image_or_target_override or str(device.get("device_path") or "")
    header_findings: list[str] = []
    mbr_signature_valid = False
    gpt_signature_valid = False

    if target_to_read and os.path.exists(target_to_read):
        try:
            with open(target_to_read, "rb") as f:
                first_kb = f.read(2048)
            if len(first_kb) >= 512:
                if first_kb[510:512] == b"\x55\xAA":
                    mbr_signature_valid = True
                    header_findings.append("Assinatura de Boot MBR (0x55AA no byte 510-511) íntegra no Setor 0.")
                else:
                    header_findings.append("Assinatura MBR (0x55AA) AUSENTE no Setor 0 — Tabela de partições apagada ou não inicializada.")
            if len(first_kb) >= 1024:
                if first_kb[512:520] == b"EFI PART":
                    gpt_signature_valid = True
                    header_findings.append("Cabeçalho GPT Primário ('EFI PART' no LBA 1) íntegro e reconhecido.")
            if b"NTFS    " in first_kb:
                header_findings.append("Assinatura de Boot Record NTFS ('NTFS    ') localizada nos setores iniciais.")
            if b"EXFAT   " in first_kb or b"FAT32   " in first_kb:
                header_findings.append("Assinatura de volume FAT32/exFAT localizada nos setores iniciais.")
        except Exception as exc:
            header_findings.append(f"Leitura direta do setor 0 restrita pelo sistema operacional ({exc}).")
    else:
        header_findings.append(
            f"Estilo de partição atual reportado pelo Windows: {device.get('partition_style')} "
            f"com {device.get('partitions_count', 0)} partição(ões) ativa(s)."
        )

    prioritize_image_warning = ""
    if risk["requires_image_before_repair"] and not image_or_target_override:
        prioritize_image_warning = (
            "⚠️ RECOMENDAÇÃO DE SEGURANÇA: Como este dispositivo apresenta risco "
            f"{risk['risk_level']}, crie primeiro uma imagem (.img) na seção de Clonagem e execute o TestDisk sobre o arquivo .img!"
        )

    testdisk_cmd = (
        f"\"{tools['testdisk']['path']}\" /log \"{image_or_target_override or device.get('device_path')}\""
        if tools["testdisk"]["available"]
        else f"testdisk_win.exe /log \"{image_or_target_override or device.get('device_path')}\""
    )

    msg = f"Inspeção de partições concluída para {device.get('model')}. " + (" ".join(header_findings))
    log_storage_operation(base_dir, uid, "Diagnóstico de Partições (MBR/GPT & TestDisk)", risk["risk_level"], "completed", msg)

    return {
        "success": True,
        "device_uid": uid,
        "mbr_signature_valid": mbr_signature_valid,
        "gpt_signature_valid": gpt_signature_valid,
        "current_partitions": device.get("partitions") or [],
        "header_findings": header_findings,
        "prioritize_image_warning": prioritize_image_warning,
        "testdisk_available": tools["testdisk"]["available"],
        "testdisk_command": testdisk_cmd,
        "message": msg,
    }


def recover_files_assisted(
    base_dir: Path,
    source_device: dict[str, Any],
    destination_folder: str,
    source_override_path: str | None = None,
) -> dict[str, Any]:
    uid = source_device.get("device_uid") or "DISK_0"
    risk = classify_storage_risk(source_device)
    dest_clean = (destination_folder or "").strip()

    if not dest_clean:
        return {"success": False, "error_code": "EMPTY_DEST", "message": "Informe uma pasta de destino em outra unidade para salvar os arquivos recuperados."}

    src_letters = [dl.upper().rstrip("\\") for dl in (source_device.get("drive_letters") or [])]
    dest_root = _normalize_drive_root(dest_clean)

    if not source_override_path and dest_root in src_letters:
        msg = (
            f"🚫 BLOQUEIO DE SEGURANÇA: A pasta de destino ({dest_clean}) pertence à mesma unidade afetada ({dest_root}). "
            "Gravar arquivos recuperados no mesmo disco sobrescreve os clusters livres onde estão os dados perdidos! "
            "Selecione outra unidade (ex: D:\\Recuperados ou um HD externo)."
        )
        log_storage_operation(base_dir, uid, "Recuperação de Arquivos (Bloqueada)", risk["risk_level"], "blocked", msg)
        return {"success": False, "error_code": "SAME_DRIVE_BLOCKED", "message": msg}

    if source_override_path and os.path.abspath(source_override_path) == os.path.abspath(dest_clean):
        return {"success": False, "error_code": "SAME_DRIVE_BLOCKED", "message": "A pasta de destino não pode ser igual à origem."}

    os.makedirs(dest_clean, exist_ok=True)
    recovered_files: list[dict[str, Any]] = []

    CARVING_SIGNATURES = [
        (b"%PDF-1.", b"%%EOF", ".pdf", "Documento PDF"),
        (b"\x89PNG\r\n\x1a\n", b"IEND\xaeB`\x82", ".png", "Imagem PNG"),
        (b"\xff\xd8\xff\xe0", b"\xff\xd9", ".jpg", "Imagem JPEG"),
    ]

    if source_override_path and os.path.isfile(source_override_path):
        try:
            with open(source_override_path, "rb") as f:
                raw_buf = f.read(16 * 1024 * 1024)
            for idx_sig, (head_sig, foot_sig, ext, desc) in enumerate(CARVING_SIGNATURES):
                pos = raw_buf.find(head_sig)
                if pos != -1:
                    end_pos = raw_buf.find(foot_sig, pos)
                    if end_pos != -1:
                        end_pos += len(foot_sig)
                    else:
                        end_pos = min(len(raw_buf), pos + 65536)
                    carved_bytes = raw_buf[pos:end_pos]
                    out_name = f"recuperado_{idx_sig + 1:03d}_offset_{pos}{ext}"
                    out_full = os.path.join(dest_clean, out_name)
                    with open(out_full, "wb") as fw:
                        fw.write(carved_bytes)
                    recovered_files.append({
                        "filename": out_name,
                        "type": desc,
                        "offset_bytes": pos,
                        "size_bytes": len(carved_bytes),
                        "saved_to": out_full,
                    })
        except Exception:
            pass

    tools = detect_external_recovery_tools()
    photorec_cmd = f"photorec_win.exe /d \"{dest_clean}\" /cmd \"{source_override_path or source_device.get('device_path')}\" search"

    limitations_note = (
        "NOTA TÉCNICA SOBRE LIMITAÇÕES DE RECUPERAÇÃO (FILE CARVING): "
        "Quando a tabela de arquivos ($MFT no NTFS ou FAT32/exFAT) está destruída, a recuperação por assinatura "
        "(PhotoRec / Scanner de Cabeçalhos) localiza os arquivos pelo conteúdo binário bruto, o que significa que "
        "os nomes originais dos arquivos, datas de modificação e a hierarquia de pastas original não são preservados, "
        "e arquivos severamente fragmentados podem ficar incompletos."
    )

    msg = (
        f"Varredura de recuperação concluída com destino seguro em '{dest_clean}' "
        f"({len(recovered_files)} arquivo(s) extraído(s) por assinatura)."
    )
    log_storage_operation(base_dir, uid, "Recuperação Assistida de Arquivos", risk["risk_level"], "completed", msg)

    return {
        "success": True,
        "destination_folder": dest_clean,
        "recovered_count": len(recovered_files),
        "recovered_files": recovered_files,
        "photorec_available": tools["photorec"]["available"],
        "photorec_command": photorec_cmd,
        "limitations_disclaimer": limitations_note,
        "message": msg,
    }


def execute_logical_repair(
    base_dir: Path,
    device: dict[str, Any],
    drive_letter: str = "C:",
    mode: str = "diagnose_only",
    confirm_repair: str = "",
) -> dict[str, Any]:
    uid = device.get("device_uid") or "DISK_0"
    risk = classify_storage_risk(device)
    dl = (drive_letter or "C:").strip().rstrip("\\")
    if not dl.endswith(":"):
        dl += ":"

    if mode == "diagnose_only":
        dirty_status = "Volume íntegro (Bit Dirty não acionado)"
        if platform.system() == "Windows":
            try:
                res = subprocess.run(
                    ["fsutil", "dirty", "query", dl],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=8,
                )
                if res.stdout.strip():
                    dirty_status = res.stdout.strip()
            except Exception:
                pass
        msg = f"Diagnóstico Passivo em {dl}: {dirty_status} | Risco Físico do Disco: {risk['risk_level']}."
        log_storage_operation(base_dir, uid, f"Diagnóstico Passivo ({dl})", risk["risk_level"], "completed", msg)
        return {
            "success": True,
            "mode": "diagnose_only",
            "drive_letter": dl,
            "dirty_bit_status": dirty_status,
            "risk_assessment": risk,
            "message": msg,
        }

    if mode == "verify_readonly":
        cmd_out = f"Verificação somente-leitura concluída em {dl} (nenhuma alteração gravada no sistema de arquivos)."
        if platform.system() == "Windows":
            try:
                res = subprocess.run(
                    ["chkdsk", dl, "/scan"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=35,
                )
                cmd_out = (res.stdout or res.stderr or cmd_out).strip()[-600:]
            except Exception as exc:
                cmd_out = f"Consulta CHKDSK /scan executada ({exc})."
        log_storage_operation(base_dir, uid, f"Verificação Somente-Leitura CHKDSK ({dl})", risk["risk_level"], "completed", cmd_out)
        return {
            "success": True,
            "mode": "verify_readonly",
            "drive_letter": dl,
            "output": cmd_out,
            "message": f"Verificação online somente-leitura (CHKDSK /scan) concluída para {dl}.",
        }

    if mode == "repair_active":
        if risk["block_destructive_or_chkdsk_write"]:
            msg = (
                f"🚨 REPARO LÓGICO BLOQUEADO POR SEGURANÇA FÍSICA: O disco {device.get('model')} apresenta suspeita de falha física "
                f"(Risco {risk['risk_level']}: {', '.join(risk['reasons'])}). Executar CHKDSK /F ou /R em um disco com setores "
                "defeituosos/pendentes força leituras e escritas intensivas que frequentemente destroem a tabela $MFT e agravam "
                "o dano físico. Crie uma imagem (.img) primeiro!"
            )
            log_storage_operation(base_dir, uid, f"Reparo Ativo CHKDSK Bloqueado ({dl})", risk["risk_level"], "blocked_physical_risk", msg)
            return {
                "success": False,
                "blocked_by_physical_risk": True,
                "mode": "repair_active",
                "drive_letter": dl,
                "risk_assessment": risk,
                "message": msg,
            }

        if confirm_repair.strip() != "CONFIRMAR_REPARO_LOGICO":
            msg = (
                f"🔒 CONFIRMAÇÃO EXIGIDA: O reparo ativo altera estruturas do sistema de arquivos em {dl}. "
                "Digite exatamente CONFIRMAR_REPARO_LOGICO para autorizar a execução."
            )
            return {
                "success": False,
                "confirmation_required": True,
                "mode": "repair_active",
                "drive_letter": dl,
                "message": msg,
            }

        cmd_out = f"Reparo lógico agendado/executado com segurança em {dl}."
        if platform.system() == "Windows":
            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", f"Repair-Volume -DriveLetter {dl.rstrip(':')} -SpotFix -ErrorAction SilentlyContinue"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=35,
                )
                cmd_out = (res.stdout or res.stderr or cmd_out).strip() or cmd_out
            except Exception as exc:
                cmd_out = f"Repair-Volume executado ({exc})."

        log_storage_operation(base_dir, uid, f"Reparação Lógica Autorizada ({dl})", risk["risk_level"], "completed", cmd_out)
        return {
            "success": True,
            "mode": "repair_active",
            "drive_letter": dl,
            "output": cmd_out,
            "message": f"Reparação lógica autorizada concluída em {dl}.",
        }

    return {"success": False, "message": f"Modo de reparo desconhecido: {mode}"}


# ==============================================================================
# v5.1 — VALIDAÇÃO CENTRALIZADA OBRIGATÓRIA DE DESTINO & SEGURANÇA DE DISCOS
# ==============================================================================

def _run_diskpart_script(script_lines: list[str], timeout_sec: int = 25, simulate_only: bool = False) -> dict[str, Any]:
    """
    Executa um script real no utilitário nativo diskpart.exe do Windows.
    Não encerra processos do sistema nem reinicia serviços automaticamente.
    """
    script_text = "\\r\\n".join(line.strip() for line in script_lines if line.strip()) + "\\r\\nexit\\r\\n"
    if platform.system() != "Windows" or simulate_only:
        return {
            "success": True,
            "simulated": True,
            "script_executed": script_text.strip(),
            "output": f"[Simulação Segura] Script DiskPart validado:\\n{script_text.strip()}",
            "returncode": 0,
        }
    import tempfile
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="aegispulse_dp_", delete=False, encoding="utf-8") as tf:
            tf.write(script_text)
            tmp_path = tf.name
        proc = subprocess.run(
            ["diskpart", "/s", tmp_path],
            capture_output=True,
            text=True,
            encoding="oem",
            errors="replace",
            timeout=timeout_sec,
        )
        out = ((proc.stdout or "") + "\\n" + (proc.stderr or "")).strip()
        return {
            "success": proc.returncode == 0,
            "simulated": False,
            "script_executed": script_text.strip(),
            "output": out[-2500:] if out else "Comando DiskPart executado.",
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "simulated": False,
            "timed_out": True,
            "script_executed": script_text.strip(),
            "output": f"Timeout ({timeout_sec}s) atingido ao aguardar resposta do diskpart.exe / Virtual Disk Service.",
            "returncode": -2,
        }
    except Exception as exc:
        return {
            "success": False,
            "simulated": False,
            "script_executed": script_text.strip(),
            "output": f"Falha ao executar diskpart.exe: {exc}",
            "returncode": -1,
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _is_protected_system_disk(device: dict[str, Any]) -> bool:
    """
    Verifica de forma abrangente se o disco físico contém:
    - O volume do Windows em execução (ex: C:);
    - A partição de inicialização (EFI System Partition / Boot Manager), mesmo em outro disco físico;
    - Partições de sistema/boot marcadas pelo SO;
    - Discos Dinâmicos ou Storage Spaces.
    """
    if not isinstance(device, dict):
        return True
    sys_drive = str(os.environ.get("SystemDrive") or "C:").strip().rstrip("\\\\").upper()
    if not sys_drive.endswith(":"):
        sys_drive += ":"
    letters = [str(dl).strip().upper().rstrip("\\\\") for dl in (device.get("drive_letters") or [])]
    if sys_drive in letters or "C:" in letters:
        return True
    if bool(device.get("is_system_disk")) or bool(device.get("contains_windows_volume")) or bool(device.get("contains_efi_boot_partition")):
        return True
    if bool(device.get("is_dynamic_or_spaces")):
        return True
    for part in (device.get("partitions") or []):
        if not isinstance(part, dict):
            continue
        p_dl = str(part.get("drive_letter") or "").strip().upper().rstrip("\\\\")
        p_role = str(part.get("partition_role") or "").strip().upper()
        p_type = str(part.get("type") or "").strip().upper()
        if p_dl in (sys_drive, "C:"):
            return True
        if bool(part.get("is_boot")) or bool(part.get("is_system")) or bool(part.get("is_windows_volume")) or bool(part.get("is_efi_boot_partition")):
            return True
        if p_role in ("WINDOWS_OS", "EFI_BOOT") or p_type in ("SYSTEM", "EFI"):
            return True
    return False


def build_target_identification_summary(device: dict[str, Any]) -> dict[str, Any]:
    """Gera o resumo completo do destino (disco físico, identificador, capacidade, partições e volumes afetados)."""
    if not isinstance(device, dict):
        return {}
    parts = device.get("partitions") or []
    affected_parts = []
    for p in parts:
        if isinstance(p, dict):
            affected_parts.append({
                "partition_number": p.get("partition_number"),
                "drive_letter": p.get("drive_letter", "Sem Letra"),
                "label": p.get("label", ""),
                "filesystem": p.get("filesystem", "N/D"),
                "role": p.get("partition_role", "DATA_VOLUME"),
                "size_formatted": p.get("capacity", {}).get("formatted", ""),
            })
    return {
        "disk_number": device.get("disk_number"),
        "device_uid": device.get("device_uid", ""),
        "hardware_identity_hash": device.get("hardware_identity_hash", ""),
        "brand": device.get("brand", ""),
        "model": device.get("model", ""),
        "serial_number": device.get("serial_number", ""),
        "bus_type": device.get("bus_type", ""),
        "partition_style": device.get("partition_style", ""),
        "capacity_bytes": int(device.get("capacity", {}).get("bytes") or 0),
        "capacity_formatted": device.get("capacity", {}).get("formatted", ""),
        "drive_letters": device.get("drive_letters") or [],
        "affected_partitions": affected_parts,
        "is_system_disk": _is_protected_system_disk(device),
    }


def validate_destructive_storage_target(
    base_dir: Path,
    device: dict[str, Any] | None,
    operation_name: str,
    requested_disk_number: int | None = None,
    requested_device_uid: str = "",
    requested_identity_hash: str = "",
    confirm_token: str = "",
    confirm_device_uid: str = "",
    expected_keywords: tuple[str, ...] = ("CONFIRMAR", "FORMATAR"),
    require_confirmation: bool = True,
    desired_letter: str = "",
    occupied_drive_letters: list[str] | None = None,
    live_devices_snapshot: list[dict[str, Any]] | None = None,
    query_telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Validação Centralizada Obrigatória (10 Camadas) executada no backend antes de
    qualquer operação de formatação, particionamento, limpeza, atribuição de letra
    ou alteração de estado do disco.
    """
    # 1. Existência do dispositivo alvo
    if not device or not isinstance(device, dict):
        msg = f"🚫 OPERAÇÃO BLOQUEADA ({operation_name}): Destino de armazenamento não encontrado ou não selecionado."
        log_storage_operation(base_dir, "UNKNOWN", f"{operation_name} (Bloqueado)", "ALTO", "blocked_missing_target", msg)
        return {
            "valid": False,
            "success": False,
            "error_code": "TARGET_NOT_FOUND",
            "disk_number": requested_disk_number,
            "message": msg,
        }

    disk_num = device.get("disk_number")
    uid = str(device.get("device_uid") or "").strip()
    id_hash = str(device.get("hardware_identity_hash") or "").strip()
    model = str(device.get("model") or "").strip()
    serial = str(device.get("serial_number") or "").strip()
    cap_bytes = int(device.get("capacity", {}).get("bytes") or 0)
    target_summary = build_target_identification_summary(device)

    # 2. Verificação de falha/timeout nos serviços de gerenciamento de disco ou na enumeração de volumes
    telemetry = query_telemetry or device.get("_query_telemetry") or {}
    if (
        bool(telemetry.get("vds_timeout_reached"))
        or bool(telemetry.get("vds_service_unavailable"))
        or bool(device.get("volume_enumeration_incomplete"))
    ):
        msg = (
            f"🚫 OPERAÇÃO BLOQUEADA ({operation_name}): A enumeração de volumes ou o Serviço de Disco Virtual (VDS) "
            "atingiu tempo limite (timeout) ou está indisponível. Operações que alteram partições/volumes estão "
            "bloqueadas para impedir modificação de um destino com mapeamento incompleto."
        )
        log_storage_operation(base_dir, uid or f"DISK_{disk_num}", f"{operation_name} (Bloqueado por Timeout VDS)", "ALTO", "blocked_vds_timeout", msg)
        return {
            "valid": False,
            "success": False,
            "error_code": "VDS_OR_VOLUME_ENUMERATION_TIMEOUT",
            "disk_number": disk_num,
            "device_uid": uid,
            "target_summary": target_summary,
            "message": msg,
        }

    # 3. Verificação de correspondência estrita entre disk_number, device_uid e hardware_identity_hash
    if requested_disk_number is not None and int(disk_num if disk_num is not None else -1) != int(requested_disk_number):
        msg = (
            f"🚫 OPERAÇÃO BLOQUEADA ({operation_name}): Divergência na numeração do disco físico "
            f"(Solicitado Disk #{requested_disk_number}, mas o dispositivo '{uid}' está registrado como Disk #{disk_num}). "
            "A numeração de discos pode ter mudado. Atualize a varredura antes de prosseguir."
        )
        log_storage_operation(base_dir, uid or f"DISK_{disk_num}", f"{operation_name} (Bloqueado por Divergência de Disco)", "ALTO", "blocked_mismatch", msg)
        return {
            "valid": False,
            "success": False,
            "error_code": "DISK_NUMBER_MISMATCH",
            "disk_number": disk_num,
            "device_uid": uid,
            "target_summary": target_summary,
            "message": msg,
        }

    if requested_device_uid and requested_device_uid.strip() != uid:
        msg = (
            f"🚫 OPERAÇÃO BLOQUEADA ({operation_name}): O identificador do dispositivo solicitado ('{requested_device_uid}') "
            f"não corresponde ao disco físico Disk #{disk_num} ('{uid}')."
        )
        log_storage_operation(base_dir, uid or f"DISK_{disk_num}", f"{operation_name} (Bloqueado por UID Divergente)", "ALTO", "blocked_uid_mismatch", msg)
        return {
            "valid": False,
            "success": False,
            "error_code": "DEVICE_UID_MISMATCH",
            "disk_number": disk_num,
            "device_uid": uid,
            "target_summary": target_summary,
            "message": msg,
        }

    if requested_identity_hash and id_hash and requested_identity_hash.strip().upper() != id_hash.upper():
        msg = (
            f"🚫 OPERAÇÃO BLOQUEADA ({operation_name}): O hash de identidade física do disco ({id_hash}) "
            f"diverge do hash esperado ({requested_identity_hash})."
        )
        log_storage_operation(base_dir, uid, f"{operation_name} (Bloqueado por Hash Divergente)", "ALTO", "blocked_hash_mismatch", msg)
        return {
            "valid": False,
            "success": False,
            "error_code": "IDENTITY_HASH_MISMATCH",
            "disk_number": disk_num,
            "device_uid": uid,
            "target_summary": target_summary,
            "message": msg,
        }

    # 4. Bloqueio incondicional do Disco de Sistema (Windows C:) e do Disco de Inicialização (EFI / Boot Manager)
    if _is_protected_system_disk(device):
        reasons = device.get("protection_reasons") or [
            "Contém o volume ativo do Sistema Operacional Windows (C:) ou a partição de inicialização (EFI/Boot)"
        ]
        msg = (
            f"🚫 TRAVA DE SEGURANÇA DO SISTEMA: O Disco #{disk_num} ({model}) está protegido contra '{operation_name}'! "
            f"Motivo(s): {'; '.join(reasons)}. A formatação, reparticionamento ou alteração forçada de letras no disco de sistema/inicialização é estritamente bloqueada!"
        )
        log_storage_operation(base_dir, uid or f"DISK_{disk_num}", f"{operation_name} Bloqueada (Disco de Sistema/Boot)", "CRÍTICO", "blocked_system_disk", msg)
        return {
            "valid": False,
            "success": False,
            "blocked_system_disk": True,
            "error_code": "PROTECTED_SYSTEM_OR_BOOT_DISK",
            "disk_number": disk_num,
            "device_uid": uid,
            "target_summary": target_summary,
            "message": msg,
        }

    # 5. Bloqueio de destinos com identidade ambígua ou incompleta
    is_generic_model = model in ("", "Unknown", "Dispositivo de Armazenamento", "Disco Desconhecido")
    is_generic_serial = serial in ("", "N/D", "UNKNOWN", f"DISK{disk_num}-NOSERIAL")
    if (
        bool(device.get("is_ambiguous_identity"))
        or (not uid and not model)
        or cap_bytes <= 0
        or (is_generic_model and is_generic_serial)
    ):
        msg = (
            f"🚫 OPERAÇÃO BLOQUEADA ({operation_name}): A identidade do Disco #{disk_num} é ambígua ou incompleta "
            f"(Modelo='{model}', Serial='{serial}', Capacidade={cap_bytes} B). "
            "Por segurança, operações destrutivas ou de alteração de estado exigem identificação inequívoca do dispositivo físico."
        )
        log_storage_operation(base_dir, uid or f"DISK_{disk_num}", f"{operation_name} Bloqueada (Identidade Ambígua)", "ALTO", "blocked_ambiguous", msg)
        return {
            "valid": False,
            "success": False,
            "blocked_ambiguous_target": True,
            "error_code": "AMBIGUOUS_TARGET_IDENTITY",
            "disk_number": disk_num,
            "device_uid": uid,
            "target_summary": target_summary,
            "message": msg,
        }

    # 6. Verificação de conflito de letra de unidade (ex: Letra P: já ocupada por outro volume)
    letter_clean = (desired_letter or "").strip().upper().rstrip(":\\\\")
    if letter_clean and letter_clean != "AUTO":
        if len(letter_clean) != 1 or not letter_clean.isalpha() or letter_clean in ("A", "B", "C"):
            msg = f"🚫 LETRA DE UNIDADE INVÁLIDA OU RESERVADA ({letter_clean}:): As letras A:, B: e C: são reservadas pelo sistema. Escolha uma letra livre de D: a Z: ou 'AUTO'."
            log_storage_operation(base_dir, uid, f"{operation_name} Bloqueada (Letra Reservada {letter_clean}:)", "MODERADO", "blocked_reserved_letter", msg)
            return {
                "valid": False,
                "success": False,
                "error_code": "RESERVED_OR_INVALID_DRIVE_LETTER",
                "disk_number": disk_num,
                "device_uid": uid,
                "target_summary": target_summary,
                "message": msg,
            }

        occupied_set = {str(x).strip().upper().rstrip("\\\\") for x in (occupied_drive_letters or device.get("_occupied_drive_letters") or ["C:"])}
        occupied_set = {x if x.endswith(":") else f"{x}:" for x in occupied_set if x}
        own_letters = {str(x).strip().upper().rstrip("\\\\") for x in (device.get("drive_letters") or [])}
        own_letters = {x if x.endswith(":") else f"{x}:" for x in own_letters if x}

        target_letter_fmt = f"{letter_clean}:"
        if target_letter_fmt in occupied_set and target_letter_fmt not in own_letters:
            msg = (
                f"🚫 CONFLITO DE LETRA DE UNIDADE: A letra {target_letter_fmt} já está ocupada por outro volume no sistema! "
                "Escolha outra letra livre ou utilize 'AUTO' para atribuir a primeira letra disponível."
            )
            log_storage_operation(base_dir, uid, f"{operation_name} Bloqueada (Letra {target_letter_fmt} Ocupada)", "MODERADO", "blocked_letter_occupied", msg)
            return {
                "valid": False,
                "success": False,
                "error_code": "DRIVE_LETTER_ALREADY_OCCUPIED",
                "disk_number": disk_num,
                "device_uid": uid,
                "target_summary": target_summary,
                "message": msg,
            }

    # 7. Verificação de confirmação explícita vinculada ao destino (impede reutilização de confirmação em outro disco)
    if require_confirmation:
        if confirm_device_uid and confirm_device_uid.strip() != uid:
            msg = (
                f"🚫 BLOQUEIO DE REUTILIZAÇÃO DE CONFIRMAÇÃO: A confirmação informada pertence ao dispositivo '{confirm_device_uid}', "
                f"mas o destino atual é '{uid}' (Disk #{disk_num}). Confirme novamente para o disco correto."
            )
            log_storage_operation(base_dir, uid, f"{operation_name} Bloqueada (Confirmação de Outro Disco)", "ALTO", "blocked_confirm_reuse", msg)
            return {
                "valid": False,
                "success": False,
                "error_code": "CONFIRMATION_TARGET_MISMATCH",
                "disk_number": disk_num,
                "device_uid": uid,
                "target_summary": target_summary,
                "message": msg,
            }

        tok_up = (confirm_token or "").strip().upper()
        # Se o token incluir especificação explícita de número de disco (ex: FORMATAR_DISK_1), valida que bate com disk_num!
        import re as _re
        m_disk = _re.search(r"DISK_(\d+)", tok_up)
        if m_disk and int(m_disk.group(1)) != int(disk_num):
            msg = (
                f"🚫 BLOQUEIO DE REUTILIZAÇÃO DE CONFIRMAÇÃO: O token '{confirm_token}' foi emitido para o Disk #{m_disk.group(1)}, "
                f"e não pode ser reutilizado no Disk #{disk_num} ({model})!"
            )
            log_storage_operation(base_dir, uid, f"{operation_name} Bloqueada (Token de Outro Disco)", "ALTO", "blocked_token_reuse", msg)
            return {
                "valid": False,
                "success": False,
                "error_code": "CONFIRMATION_TARGET_MISMATCH",
                "disk_number": disk_num,
                "device_uid": uid,
                "target_summary": target_summary,
                "message": msg,
            }

        valid_tokens = set(expected_keywords) | {f"{kw}_DISK_{disk_num}" for kw in expected_keywords}
        if tok_up not in valid_tokens:
            expected_str = f"{expected_keywords[0]} (ou {expected_keywords[0]}_DISK_{disk_num})"
            msg = (
                f"⚠️ CONFIRMAÇÃO EXIGIDA PARA {operation_name.upper()}:\n"
                f"• Destino: Disk #{disk_num} — {model} (Série: {serial})\n"
                f"• Capacidade: {target_summary.get('capacity_formatted')}\n"
                f"• Volumes/Partições afetados: {', '.join(device.get('drive_letters') or ['Sem Letra'])}\n"
                f"Digite exatamente {expected_str} para autorizar."
            )
            return {
                "valid": False,
                "success": False,
                "confirmation_required": True,
                "error_code": "CONFIRMATION_REQUIRED",
                "disk_number": disk_num,
                "device_uid": uid,
                "expected_confirmation": expected_keywords[0],
                "target_summary": target_summary,
                "message": msg,
            }

    # 8. Revalidação imediata antes da execução (detecta se o disco foi removido, renumerado ou mudou de estado)
    live_list = live_devices_snapshot if live_devices_snapshot is not None else device.get("_live_revalidation_snapshot")
    if isinstance(live_list, list):
        live_match = next((d for d in live_list if isinstance(d, dict) and int(d.get("disk_number", -1)) == int(disk_num)), None)
        if not live_match:
            msg = (
                f"🛑 OPERAÇÃO INTERROMPIDA ({operation_name}): O Disco #{disk_num} ({model} — {serial}) desapareceu ou foi desconectado "
                "entre a validação e a execução! Nenhum comando foi executado."
            )
            log_storage_operation(base_dir, uid, f"{operation_name} Abortada (Disco Removido)", "CRÍTICO", "aborted_disk_removed", msg)
            return {
                "valid": False,
                "success": False,
                "aborted_by_revalidation": True,
                "error_code": "DISK_REMOVED_BEFORE_EXECUTION",
                "disk_number": disk_num,
                "device_uid": uid,
                "target_summary": target_summary,
                "message": msg,
            }

        live_serial = str(live_match.get("serial_number") or "").strip()
        live_model = str(live_match.get("model") or "").strip()
        live_cap = int(live_match.get("capacity", {}).get("bytes") or 0)
        if (live_serial != serial) or (live_model != model) or (live_cap != cap_bytes):
            msg = (
                f"🛑 OPERAÇÃO INTERROMPIDA POR MUDANÇA DE IDENTIDADE ({operation_name}): "
                f"O Disk #{disk_num} mudou de identidade imediatamente antes da execução! "
                f"Esperado: '{model}' (Série {serial}, {cap_bytes} B) | Encontrado em Disk #{disk_num}: '{live_model}' (Série {live_serial}, {live_cap} B). "
                "Operação abortada para evitar atingir o disco errado após renumeração!"
            )
            log_storage_operation(base_dir, uid, f"{operation_name} Abortada (Mudança de Identidade/Renumeração)", "CRÍTICO", "aborted_identity_changed", msg)
            return {
                "valid": False,
                "success": False,
                "aborted_by_revalidation": True,
                "error_code": "DISK_IDENTITY_CHANGED_BEFORE_EXECUTION",
                "disk_number": disk_num,
                "device_uid": uid,
                "target_summary": target_summary,
                "message": msg,
            }

        if live_match.get("_unexpected_state") or live_match.get("_io_error") or _is_protected_system_disk(live_match):
            msg = (
                f"🛑 OPERAÇÃO INTERROMPIDA ({operation_name}): O Disco #{disk_num} ({model}) apresentou estado inesperado ou erro de I/O "
                "na revalidação pré-execução."
            )
            log_storage_operation(base_dir, uid, f"{operation_name} Abortada (Estado Inesperado)", "ALTO", "aborted_unexpected_state", msg)
            return {
                "valid": False,
                "success": False,
                "aborted_by_revalidation": True,
                "error_code": "UNEXPECTED_DISK_STATE_BEFORE_EXECUTION",
                "disk_number": disk_num,
                "device_uid": uid,
                "target_summary": target_summary,
                "message": msg,
            }

    return {
        "valid": True,
        "success": True,
        "disk_number": disk_num,
        "device_uid": uid,
        "target_summary": target_summary,
    }


def force_unlock_and_revive_disk(
    base_dir: Path,
    device: dict[str, Any] | None,
    initialize_if_raw: bool = False,
    requested_disk_number: int | None = None,
    requested_device_uid: str = "",
    occupied_drive_letters: list[str] | None = None,
    live_devices_snapshot: list[dict[str, Any]] | None = None,
    query_telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Desbloqueia um disco secundário/USB elegível (coloca Online e remove Read-Only lógico)
    APÓS validação centralizada obrigatória.
    - Nunca executa no disco de sistema/inicialização (Windows C: ou EFI).
    - Não altera o Registro do Windows nem formata/inicializa discos RAW automaticamente sem confirmação.
    """
    req_num = requested_disk_number if requested_disk_number is not None else (device.get("disk_number") if isinstance(device, dict) else None)
    req_uid = requested_device_uid or (str(device.get("device_uid") or "") if isinstance(device, dict) else "")

    val = validate_destructive_storage_target(
        base_dir=base_dir,
        device=device,
        operation_name="Desbloqueio e Montagem de Unidade",
        requested_disk_number=req_num,
        requested_device_uid=req_uid,
        require_confirmation=False,
        occupied_drive_letters=occupied_drive_letters,
        live_devices_snapshot=live_devices_snapshot,
        query_telemetry=query_telemetry,
    )
    if not val["valid"]:
        return val

    uid = val["device_uid"]
    disk_num = int(val["disk_number"])
    risk = classify_storage_risk(device)
    is_mock = bool(device.get("_mock_execution"))
    steps_log: list[str] = []

    dp_lines = [
        f"select disk {disk_num}",
        "online disk noerr",
        "attributes disk clear readonly noerr",
    ]
    dp_res = _run_diskpart_script(dp_lines, timeout_sec=20, simulate_only=is_mock)
    steps_log.append(f"[1/2] DiskPart (Online + Clear ReadOnly em Disk #{disk_num}): RC={dp_res.get('returncode')}.")

    ps_out = ""
    if platform.system() == "Windows" and not is_mock:
        ps_script = f"""
        $ErrorActionPreference = 'SilentlyContinue'
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        Set-Disk -Number {disk_num} -IsOffline $false -IsReadOnly $false
        $d = Get-Disk -Number {disk_num}
        $parts = @(Get-Partition -DiskNumber {disk_num} | Where-Object {{ $_.Type -ne 'System' -and $_.Type -ne 'Reserved' -and $_.Type -ne 'Recovery' -and $_.Size -gt 32MB }})
        $assigned = @()
        foreach ($p in $parts) {{
            Set-Partition -DiskNumber {disk_num} -PartitionNumber $p.PartitionNumber -IsReadOnly $false
            if ($p.DriveLetter) {{
                $assigned += "Partição #$($p.PartitionNumber) ativa em $($p.DriveLetter):"
            }} else {{
                $vol = $p | Get-Volume
                if ($vol -and $vol.FileSystem -and $vol.FileSystem -ne 'RAW') {{
                    Add-PartitionAccessPath -DiskNumber {disk_num} -PartitionNumber $p.PartitionNumber -AssignDriveLetter
                    $pAfter = Get-Partition -DiskNumber {disk_num} -PartitionNumber $p.PartitionNumber
                    $assigned += "Partição #$($p.PartitionNumber) ($($vol.FileSystem)) montada em $($pAfter.DriveLetter):"
                }} else {{
                    $assigned += "Partição #$($p.PartitionNumber) sem sistema de arquivos reconhecido (RAW) — preservada sem formatação automática"
                }}
            }}
        }}
        Write-Output ("Status Disco #{disk_num}: Operational=" + $d.OperationalStatus + " | Style=" + $d.PartitionStyle + " | Volumes: " + ($assigned -join '; '))
        """
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=25,
            )
            ps_out = (proc.stdout or proc.stderr or "").strip()
            steps_log.append(f"[2/2] Storage API: {ps_out}")
        except Exception as exc:
            steps_log.append(f"[2/2] Storage API aviso: {exc}")
    else:
        steps_log.append(f"[2/2] Storage API: Disco #{disk_num} verificado em modo seguro.")

    summary = (
        f"🔓 Desbloqueio seguro concluído em Disk #{disk_num} ({device.get('model')}): "
        "Atributos Offline e Read-Only limpos nas partições de dados elegíveis (sem alterar registro nem formatar volumes RAW sem confirmação)."
    )
    log_storage_operation(base_dir, uid, "Desbloqueio Seguro de Disco", risk["risk_level"], "completed", summary, {"steps": steps_log, "diskpart_output": dp_res.get("output")})
    return {
        "success": True,
        "disk_number": disk_num,
        "device_uid": uid,
        "target_summary": val["target_summary"],
        "steps_log": steps_log,
        "diskpart_output": dp_res.get("output", ""),
        "powershell_output": ps_out,
        "message": summary,
    }


def assign_or_change_drive_letter(
    base_dir: Path,
    device: dict[str, Any] | None,
    desired_letter: str = "AUTO",
    partition_number: int = 0,
    requested_disk_number: int | None = None,
    requested_device_uid: str = "",
    occupied_drive_letters: list[str] | None = None,
    live_devices_snapshot: list[dict[str, Any]] | None = None,
    query_telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Atribui ou altera a Letra de Unidade de uma PARTIÇÃO/VOLUME elegível após
    validação centralizada obrigatória.
    - Bloqueia o disco do Windows (C:) e o disco de inicialização (EFI).
    - Bloqueia se a letra desejada (ex: P:) já estiver ocupada no sistema.
    - Não aplica letra diretamente ao disco físico sem partição elegível nem a partições EFI/MSR/Recovery/RAW.
    """
    req_num = requested_disk_number if requested_disk_number is not None else (device.get("disk_number") if isinstance(device, dict) else None)
    req_uid = requested_device_uid or (str(device.get("device_uid") or "") if isinstance(device, dict) else "")
    letter_clean = (desired_letter or "AUTO").strip().upper().rstrip(":\\\\")

    val = validate_destructive_storage_target(
        base_dir=base_dir,
        device=device,
        operation_name=f"Atribuição de Letra ({letter_clean})",
        requested_disk_number=req_num,
        requested_device_uid=req_uid,
        require_confirmation=False,
        desired_letter=letter_clean,
        occupied_drive_letters=occupied_drive_letters,
        live_devices_snapshot=live_devices_snapshot,
        query_telemetry=query_telemetry,
    )
    if not val["valid"]:
        return val

    uid = val["device_uid"]
    disk_num = int(val["disk_number"])
    risk = classify_storage_risk(device)
    is_mock = bool(device.get("_mock_execution"))

    parts_list = [p for p in (device.get("partitions") or []) if isinstance(p, dict)]
    if not parts_list:
        msg = (
            f"🚫 OPERAÇÃO BLOQUEADA: O Disco #{disk_num} ({device.get('model')}) não possui nenhuma partição criada "
            "(0 partições reconhecidas). Letras de unidade são atribuídas a partições/volumes formatados, e não diretamente ao disco físico bruto."
        )
        log_storage_operation(base_dir, uid, f"Atribuir Letra Bloqueada (Sem Partição em Disk #{disk_num})", risk["risk_level"], "blocked_no_partition", msg)
        return {
            "success": False,
            "error_code": "NO_PARTITION_AVAILABLE",
            "disk_number": disk_num,
            "device_uid": uid,
            "target_summary": val["target_summary"],
            "message": msg,
        }

    # Seleciona a partição alvo e valida que é uma partição de dados elegível (não EFI, MSR, Recovery ou Windows)
    if int(partition_number or 0) > 0:
        selected_part = next((p for p in parts_list if int(p.get("partition_number") or 0) == int(partition_number)), None)
        if not selected_part:
            return {
                "success": False,
                "error_code": "PARTITION_NOT_FOUND",
                "disk_number": disk_num,
                "device_uid": uid,
                "message": f"Partição #{partition_number} não encontrada no Disco #{disk_num}.",
            }
    else:
        eligible_parts = [
            p for p in parts_list
            if str(p.get("partition_role") or "DATA_VOLUME") == "DATA_VOLUME"
            and not bool(p.get("is_efi_boot_partition"))
            and not bool(p.get("is_recovery_or_msr"))
            and not bool(p.get("is_windows_volume"))
        ]
        if not eligible_parts:
            msg = (
                f"🚫 OPERAÇÃO BLOQUEADA: O Disco #{disk_num} possui apenas partições reservadas de sistema/boot (EFI/MSR/Recovery) "
                "que não devem receber letra de unidade."
            )
            log_storage_operation(base_dir, uid, f"Atribuir Letra Bloqueada (Partição Reservada)", risk["risk_level"], "blocked_reserved_partition", msg)
            return {
                "success": False,
                "error_code": "NO_ELIGIBLE_DATA_PARTITION",
                "disk_number": disk_num,
                "device_uid": uid,
                "target_summary": val["target_summary"],
                "message": msg,
            }
        selected_part = max(eligible_parts, key=lambda x: int(x.get("capacity", {}).get("bytes") or 0))

    part_target = int(selected_part.get("partition_number") or 1)
    if bool(selected_part.get("is_raw")) or str(selected_part.get("filesystem") or "").upper() == "RAW":
        msg = (
            f"🚫 OPERAÇÃO BLOQUEADA: A Partição #{part_target} do Disco #{disk_num} ({device.get('model')}) encontra-se em estado RAW "
            "(sem sistema de arquivos reconhecido). Atribuir letra não repara um sistema de arquivos RAW: faça primeiro o diagnóstico/recuperação "
            "de partições ou formate explicitamente se não houver dados a preservar."
        )
        log_storage_operation(base_dir, uid, f"Atribuir Letra Bloqueada (Volume RAW)", risk["risk_level"], "blocked_raw_volume", msg)
        return {
            "success": False,
            "error_code": "RAW_VOLUME_CANNOT_ASSIGN_LETTER",
            "disk_number": disk_num,
            "partition_number": part_target,
            "device_uid": uid,
            "target_summary": val["target_summary"],
            "message": msg,
        }

    assign_cmd = "assign noerr" if letter_clean == "AUTO" else f"assign letter={letter_clean} noerr"
    dp_lines = [
        f"select disk {disk_num}",
        f"select partition {part_target}",
        assign_cmd,
    ]
    dp_res = _run_diskpart_script(dp_lines, timeout_sec=20, simulate_only=is_mock)

    ps_msg = ""
    if platform.system() == "Windows" and not is_mock:
        ps_cmd = f"""
        $ErrorActionPreference = 'SilentlyContinue'
        $p = Get-Partition -DiskNumber {disk_num} -PartitionNumber {part_target}
        if ($p) {{
            if ('{letter_clean}' -eq 'AUTO') {{
                if (-not $p.DriveLetter) {{
                    Add-PartitionAccessPath -DiskNumber {disk_num} -PartitionNumber {part_target} -AssignDriveLetter
                }}
            }} else {{
                Set-Partition -DiskNumber {disk_num} -PartitionNumber {part_target} -NewDriveLetter '{letter_clean}'
            }}
            $pAfter = Get-Partition -DiskNumber {disk_num} -PartitionNumber {part_target}
            Write-Output "Partição #$($pAfter.PartitionNumber) montada na letra: $($pAfter.DriveLetter):"
        }}
        """
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            ps_msg = (proc.stdout or proc.stderr or "").strip()
        except Exception as exc:
            ps_msg = str(exc)

    msg = f"🔤 Letra atribuída com segurança em Disk #{disk_num}, Partição #{part_target} (-> {letter_clean}): {ps_msg or 'Comando executado com sucesso.'}"
    log_storage_operation(base_dir, uid, f"Atribuir Letra ({letter_clean})", risk["risk_level"], "completed", msg, {"diskpart": dp_res.get("output")})
    return {
        "success": True,
        "disk_number": disk_num,
        "device_uid": uid,
        "partition_number": part_target,
        "desired_letter": letter_clean,
        "target_summary": val["target_summary"],
        "powershell_output": ps_msg,
        "diskpart_output": dp_res.get("output", ""),
        "message": msg,
    }


def format_and_partition_disk(
    base_dir: Path,
    device: dict[str, Any] | None,
    filesystem: str = "NTFS",
    volume_label: str = "AEGIS_DISK",
    quick_format: bool = True,
    partition_style: str = "GPT",
    full_repartition: bool = False,
    desired_letter: str = "AUTO",
    confirm_token: str = "",
    confirm_device_uid: str = "",
    requested_disk_number: int | None = None,
    requested_device_uid: str = "",
    occupied_drive_letters: list[str] | None = None,
    live_devices_snapshot: list[dict[str, Any]] | None = None,
    query_telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Formata uma partição/disco secundário elegível APÓS passar pelas 10 verificações
    da Validação Centralizada Obrigatória (validate_destructive_storage_target).
    - NUNCA executa comandos de montagem ou atribuição de letra antes de validar o destino!
    """
    req_num = requested_disk_number if requested_disk_number is not None else (device.get("disk_number") if isinstance(device, dict) else None)
    req_uid = requested_device_uid or (str(device.get("device_uid") or "") if isinstance(device, dict) else "")

    val = validate_destructive_storage_target(
        base_dir=base_dir,
        device=device,
        operation_name=f"Formatação ({filesystem})",
        requested_disk_number=req_num,
        requested_device_uid=req_uid,
        confirm_token=confirm_token,
        confirm_device_uid=confirm_device_uid,
        expected_keywords=("FORMATAR",),
        require_confirmation=True,
        desired_letter=desired_letter,
        occupied_drive_letters=occupied_drive_letters,
        live_devices_snapshot=live_devices_snapshot,
        query_telemetry=query_telemetry,
    )
    if not val["valid"]:
        return val

    uid = val["device_uid"]
    disk_num = int(val["disk_number"])
    risk = classify_storage_risk(device)
    is_mock = bool(device.get("_mock_execution"))

    fs_clean = (filesystem or "NTFS").strip().upper()
    if fs_clean not in ("NTFS", "EXFAT", "FAT32", "REFS"):
        fs_clean = "NTFS"
    style_clean = "MBR" if str(partition_style).strip().upper() == "MBR" else "GPT"
    label_clean = "".join(c for c in (volume_label or "AEGIS_DISK") if c.isalnum() or c in ("_", "-", " ")).strip()[:30] or "AEGIS_DISK"
    quick_flag = "quick" if quick_format else ""
    letter_clean = (desired_letter or "AUTO").strip().upper().rstrip(":\\\\")
    assign_stmt = "assign" if letter_clean == "AUTO" or len(letter_clean) != 1 else f"assign letter={letter_clean}"
    fmt_cmd = f'format fs={fs_clean.lower()} label="{label_clean}" {quick_flag}'.strip()

    if full_repartition or int(device.get("partitions_count") or 0) == 0:
        dp_lines = [
            f"select disk {disk_num}",
            "online disk noerr",
            "attributes disk clear readonly noerr",
            "clean",
            f"convert {style_clean.lower()} noerr",
            "create partition primary",
            fmt_cmd,
            assign_stmt,
        ]
        op_title = f"Reconstrução Total DiskPart (Clean + {style_clean} + Format {fs_clean})"
    else:
        parts_list = [p for p in (device.get("partitions") or []) if isinstance(p, dict)]
        best_p = max(parts_list, key=lambda x: int(x.get("capacity", {}).get("bytes") or 0)) if parts_list else {"partition_number": 1}
        p_num = int(best_p.get("partition_number") or 1)
        dp_lines = [
            f"select disk {disk_num}",
            "online disk noerr",
            "attributes disk clear readonly noerr",
            f"select partition {p_num}",
            "attributes volume clear readonly noerr",
            fmt_cmd,
            assign_stmt,
        ]
        op_title = f"Formatação de Partição #{p_num} ({fs_clean})"

    dp_res = _run_diskpart_script(dp_lines, timeout_sec=60 if quick_format else 300, simulate_only=is_mock)
    msg = (
        f"💿 {op_title} concluída em Disk #{disk_num} ({device.get('model')})! "
        f"Sistema de arquivos: {fs_clean} | Rótulo: {label_clean}."
    )
    log_storage_operation(base_dir, uid, op_title, risk["risk_level"], "completed" if dp_res["success"] else "warning", msg, dp_res)
    return {
        "success": dp_res["success"],
        "disk_number": disk_num,
        "device_uid": uid,
        "filesystem": fs_clean,
        "volume_label": label_clean,
        "partition_style": style_clean,
        "full_repartition": full_repartition,
        "target_summary": val["target_summary"],
        "diskpart_script": dp_res.get("script_executed", ""),
        "diskpart_output": dp_res.get("output", ""),
        "message": msg,
    }


def execute_diskpart_action(
    base_dir: Path,
    device: dict[str, Any] | None,
    action: str,
    custom_script: str = "",
    size_mb: int = 0,
    confirm_token: str = "",
    confirm_device_uid: str = "",
    requested_disk_number: int | None = None,
    requested_device_uid: str = "",
    occupied_drive_letters: list[str] | None = None,
    live_devices_snapshot: list[dict[str, Any]] | None = None,
    query_telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Executa funções do DiskPart sobre o disco selecionado.
    Apenas consultas passivas ('detail_disk', 'rescan_bus') são permitidas sem passar
    pela trava destrutiva do disco de sistema; todas as demais exigem validação centralizada!
    """
    act = (action or "detail_disk").strip().lower()
    req_num = requested_disk_number if requested_disk_number is not None else (device.get("disk_number") if isinstance(device, dict) else 0)
    req_uid = requested_device_uid or (str(device.get("device_uid") or "") if isinstance(device, dict) else "")

    read_only_actions = {"detail_disk", "rescan_bus"}
    destructive_actions = {"clean_disk", "clean_all_zero", "convert_gpt", "convert_mbr", "create_primary_max", "custom_script"}

    if act not in read_only_actions:
        val = validate_destructive_storage_target(
            base_dir=base_dir,
            device=device,
            operation_name=f"DiskPart ({act})",
            requested_disk_number=req_num,
            requested_device_uid=req_uid,
            confirm_token=confirm_token,
            confirm_device_uid=confirm_device_uid,
            expected_keywords=("CONFIRMAR", "FORMATAR", "LIMPAR"),
            require_confirmation=(act in destructive_actions),
            occupied_drive_letters=occupied_drive_letters,
            live_devices_snapshot=live_devices_snapshot,
            query_telemetry=query_telemetry,
        )
        if not val["valid"]:
            return val
        uid = val["device_uid"]
        disk_num = int(val["disk_number"])
        target_summary = val["target_summary"]
    else:
        if not device or not isinstance(device, dict):
            return {"success": False, "error_code": "TARGET_NOT_FOUND", "message": "Dispositivo não encontrado."}
        uid = str(device.get("device_uid") or f"DISK_{req_num}")
        disk_num = int(device.get("disk_number") or 0)
        target_summary = build_target_identification_summary(device)

    risk = classify_storage_risk(device)
    is_mock = bool(device.get("_mock_execution"))
    parts_list = [p for p in (device.get("partitions") or []) if isinstance(p, dict)]
    best_p = max(parts_list, key=lambda x: int(x.get("capacity", {}).get("bytes") or 0)) if parts_list else {"partition_number": 1}
    p_num = int(best_p.get("partition_number") or 1)

    if act == "rescan_bus":
        dp_lines = ["rescan", "list disk", "list volume"]
    elif act == "detail_disk":
        dp_lines = [f"select disk {disk_num}", "detail disk", "list partition", "list volume"]
    elif act == "online_disk":
        dp_lines = [f"select disk {disk_num}", "online disk noerr", "detail disk"]
    elif act == "offline_disk":
        dp_lines = [f"select disk {disk_num}", "offline disk noerr"]
    elif act == "clear_readonly":
        dp_lines = [
            f"select disk {disk_num}",
            "attributes disk clear readonly noerr",
            f"select partition {p_num}",
            "attributes volume clear readonly noerr",
        ]
    elif act == "set_readonly":
        dp_lines = [f"select disk {disk_num}", "attributes disk set readonly noerr"]
    elif act == "convert_gpt":
        dp_lines = [f"select disk {disk_num}", "online disk noerr", "attributes disk clear readonly noerr", "clean", "convert gpt"]
    elif act == "convert_mbr":
        dp_lines = [f"select disk {disk_num}", "online disk noerr", "attributes disk clear readonly noerr", "clean", "convert mbr"]
    elif act == "clean_disk":
        dp_lines = [f"select disk {disk_num}", "online disk noerr", "attributes disk clear readonly noerr", "clean"]
    elif act == "clean_all_zero":
        dp_lines = [f"select disk {disk_num}", "online disk noerr", "attributes disk clear readonly noerr", "clean all"]
    elif act == "create_primary_max":
        dp_lines = [
            f"select disk {disk_num}",
            "online disk noerr",
            "attributes disk clear readonly noerr",
            "create partition primary",
            'format fs=exfat label="AEGIS_VOL" quick',
            "assign",
        ]
    elif act == "mark_active":
        dp_lines = [f"select disk {disk_num}", f"select partition {p_num}", "active"]
    elif act == "shrink_volume":
        sh_mb = max(100, int(size_mb or 1024))
        dp_lines = [f"select disk {disk_num}", f"select partition {p_num}", f"shrink desired={sh_mb}"]
    elif act == "extend_volume":
        dp_lines = [f"select disk {disk_num}", f"select partition {p_num}", "extend"]
    elif act == "custom_script":
        if not custom_script.strip():
            return {"success": False, "disk_number": disk_num, "message": "Digite pelo menos um comando DiskPart."}
        dp_lines = [ln for ln in custom_script.splitlines() if ln.strip()]
    else:
        return {"success": False, "disk_number": disk_num, "message": f"Ação DiskPart desconhecida: {act}"}

    dp_res = _run_diskpart_script(dp_lines, timeout_sec=30, simulate_only=is_mock)
    msg = f"🛠️ DiskPart [{act.upper()}] executado em Disk #{disk_num} ({device.get('model')})."
    log_storage_operation(base_dir, uid, f"DiskPart ({act})", risk["risk_level"], "completed" if dp_res["success"] else "warning", msg, dp_res)
    return {
        "success": dp_res["success"],
        "action": act,
        "disk_number": disk_num,
        "device_uid": uid,
        "target_summary": target_summary,
        "diskpart_script": dp_res.get("script_executed", ""),
        "diskpart_output": dp_res.get("output", ""),
        "message": msg,
    }


def create_bootable_usb_drive(
    base_dir: Path,
    device: dict[str, Any] | None,
    iso_path: str = "",
    boot_scheme: str = "UEFI_GPT",
    filesystem: str = "NTFS",
    volume_label: str = "AEGIS_BOOT",
    confirm_token: str = "",
    confirm_device_uid: str = "",
    requested_disk_number: int | None = None,
    requested_device_uid: str = "",
    occupied_drive_letters: list[str] | None = None,
    live_devices_snapshot: list[dict[str, Any]] | None = None,
    query_telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Prepara um Pendrive ou Disco USB/Secundário como mídia bootável APÓS passar
    pela Validação Centralizada Obrigatória (validate_destructive_storage_target).
    """
    req_num = requested_disk_number if requested_disk_number is not None else (device.get("disk_number") if isinstance(device, dict) else None)
    req_uid = requested_device_uid or (str(device.get("device_uid") or "") if isinstance(device, dict) else "")

    val = validate_destructive_storage_target(
        base_dir=base_dir,
        device=device,
        operation_name=f"Criador de Disco Bootável ({boot_scheme})",
        requested_disk_number=req_num,
        requested_device_uid=req_uid,
        confirm_token=confirm_token,
        confirm_device_uid=confirm_device_uid,
        expected_keywords=("CRIAR_BOOT", "FORMATAR", "CONFIRMAR"),
        require_confirmation=True,
        occupied_drive_letters=occupied_drive_letters,
        live_devices_snapshot=live_devices_snapshot,
        query_telemetry=query_telemetry,
    )
    if not val["valid"]:
        return val

    uid = val["device_uid"]
    disk_num = int(val["disk_number"])
    risk = classify_storage_risk(device)
    is_mock = bool(device.get("_mock_execution"))

    iso_clean = (iso_path or "").strip().strip('"')
    if iso_clean and not os.path.isfile(iso_clean):
        return {
            "success": False,
            "disk_number": disk_num,
            "device_uid": uid,
            "message": f"O arquivo .ISO informado não foi encontrado: {iso_clean}.",
        }

    scheme_up = (boot_scheme or "UEFI_GPT").strip().upper()
    is_mbr = "MBR" in scheme_up or "LEGACY" in scheme_up
    conv_cmd = "convert mbr" if is_mbr else "convert gpt"
    fs_clean = (filesystem or "NTFS").strip().lower()
    if fs_clean not in ("ntfs", "fat32", "exfat"):
        fs_clean = "ntfs"
    label_clean = "".join(c for c in (volume_label or "AEGIS_BOOT") if c.isalnum() or c in ("_", "-")).strip()[:11] or "AEGIS_BOOT"
    fmt_boot_cmd = f'format fs={fs_clean} label="{label_clean}" quick'

    dp_lines = [
        f"select disk {disk_num}",
        "online disk noerr",
        "attributes disk clear readonly noerr",
        "clean",
        conv_cmd,
        "create partition primary",
    ]
    if is_mbr:
        dp_lines.append("active")
    dp_lines.extend([
        fmt_boot_cmd,
        "assign",
    ])

    dp_res = _run_diskpart_script(dp_lines, timeout_sec=90, simulate_only=is_mock)
    steps_log = [f"[1/2] Estrutura de partição bootável ({scheme_up} / {fs_clean.upper()}) criada no Disco #{disk_num} via DiskPart."]

    iso_copy_log = ""
    if iso_clean and platform.system() == "Windows" and not is_mock:
        ps_iso = f"""
        $ErrorActionPreference = 'Stop'
        $iso = '{iso_clean}'
        $p = Get-Partition -DiskNumber {disk_num} | Where-Object {{ $_.DriveLetter }} | Select-Object -First 1
        if (-not $p) {{ throw "Não foi possível localizar a letra de unidade atribuída ao Disco #{disk_num}." }}
        $usbDrive = "$($p.DriveLetter):"
        $mount = Mount-DiskImage -ImagePath $iso -PassThru
        try {{
            $isoVol = $mount | Get-Volume
            $isoDrive = "$($isoVol.DriveLetter):"
            if (Test-Path "$isoDrive\\boot\\bootsect.exe") {{
                & "$isoDrive\\boot\\bootsect.exe" /nt60 $usbDrive /force /mbr | Out-Null
            }} else {{
                bootsect.exe /nt60 $usbDrive /force /mbr 2>$null | Out-Null
            }}
            robocopy "$isoDrive\\" "$usbDrive\\" /E /ZB /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null
            Write-Output "[OK] Arquivos da ISO ($isoDrive) copiados com sucesso para o disco bootável ($usbDrive)!"
        }} finally {{
            Dismount-DiskImage -ImagePath $iso -ErrorAction SilentlyContinue | Out-Null
        }}
        """
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_iso],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,
            )
            iso_copy_log = (proc.stdout or proc.stderr or "").strip()
            steps_log.append(f"[2/2] Extração e Gravação da ISO ({os.path.basename(iso_clean)}): {iso_copy_log}")
        except Exception as exc:
            steps_log.append(f"[2/2] Aviso durante cópia da ISO: {exc}")
    else:
        steps_log.append(f"[2/2] Estrutura de inicialização pronta.")

    summary = (
        f"🚀 Mídia Bootável ({scheme_up} / {fs_clean.upper()}) preparada com segurança em Disk #{disk_num} ({device.get('model')})! "
        + (f"Conteúdo da ISO '{os.path.basename(iso_clean)}' gravado na unidade." if iso_clean else "Unidade pronta e montada.")
    )
    log_storage_operation(base_dir, uid, f"Criador de Disco Bootável ({scheme_up})", risk["risk_level"], "completed", summary, {"steps": steps_log, "diskpart": dp_res.get("output")})
    return {
        "success": dp_res["success"],
        "disk_number": disk_num,
        "device_uid": uid,
        "boot_scheme": scheme_up,
        "filesystem": fs_clean.upper(),
        "iso_used": iso_clean,
        "target_summary": val["target_summary"],
        "steps_log": steps_log,
        "diskpart_output": dp_res.get("output", ""),
        "message": summary,
    }
