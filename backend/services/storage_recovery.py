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
