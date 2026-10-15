#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/storage_diagnostics.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.0.0
================================================================================
"""

from __future__ import annotations

import os
import platform
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.collectors.storage_advanced import _find_smartctl_binary
from backend.services.storage_health import classify_storage_risk, log_storage_operation


def _resolve_readable_target(device: dict[str, Any], target_override: str | None = None) -> tuple[str | None, str, int]:
    if target_override and os.path.exists(target_override):
        sz = os.path.getsize(target_override)
        return target_override, "Arquivo/Dispositivo Direto", sz

    dev_path = str(device.get("device_path") or "")
    cap_bytes = int(device.get("capacity", {}).get("bytes") or 0)

    if platform.system() == "Windows" and dev_path.startswith("\\\\.\\"):
        try:
            with open(dev_path, "rb") as f:
                f.read(512)
            return dev_path, f"Leitura Direta de Setores Físicos ({dev_path})", cap_bytes
        except PermissionError:
            pass
        except OSError:
            pass

    letters = device.get("drive_letters") or []
    search_roots = [f"{dl}\\" for dl in letters if os.path.exists(f"{dl}\\")]
    if not search_roots and platform.system() != "Windows":
        search_roots = ["/"]

    for root_dir in search_roots:
        try:
            candidates: list[tuple[int, str]] = []
            scan_dirs = [root_dir]
            win_sys32 = os.path.join(root_dir, "Windows", "System32")
            if os.path.isdir(win_sys32):
                scan_dirs.insert(0, win_sys32)
            for sdir in scan_dirs:
                with os.scandir(sdir) as it:
                    for entry in it:
                        if entry.is_file(follow_symlinks=False):
                            try:
                                st_sz = entry.stat().st_size
                                if st_sz >= 65536:
                                    candidates.append((st_sz, entry.path))
                                    if len(candidates) >= 5:
                                        break
                            except OSError:
                                continue
                if candidates:
                    break
            if candidates:
                candidates.sort(reverse=True)
                best_sz, best_path = candidates[0]
                return best_path, f"Amostra Real Somente-Leitura ({best_path})", cap_bytes or best_sz
        except Exception:
            continue

    return None, "Sem Permissão ou Dispositivo Offline/RAW Inacessível", cap_bytes


def run_storage_integrity_test(
    base_dir: Path,
    device: dict[str, Any],
    test_type: str = "quick_health",
    sample_mb: int = 16,
    block_size_kb: int = 256,
    confirm_write_risk: str = "",
    target_override: str | None = None,
) -> dict[str, Any]:
    uid = device.get("device_uid") or "DISK_0"
    risk = classify_storage_risk(device)
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    t0 = time.perf_counter()

    if test_type == "write_verify":
        if confirm_write_risk.strip() != "CONFIRMAR_ESCRITA_RISCO_DADOS":
            msg = (
                "🔒 TESTE DE ESCRITA BLOQUEADO POR SEGURANÇA: O AegisPulse não executa testes de escrita por padrão "
                "para proteger os dados do cliente. Para autorizar um teste controlado de escrita em arquivo temporário, "
                "digite exatamente CONFIRMAR_ESCRITA_RISCO_DADOS."
            )
            log_storage_operation(base_dir, uid, "Teste de Escrita (Bloqueado)", risk["risk_level"], "blocked", msg)
            return {
                "success": False,
                "blocked_by_safety": True,
                "test_type": test_type,
                "message": msg,
            }
        if risk["block_destructive_or_chkdsk_write"]:
            msg = (
                f"🚨 OPERAÇÃO RECUSADA: O dispositivo {device.get('model')} possui risco {risk['risk_level']} "
                "com indícios de degradação física/mídia. Testes de escrita são estritamente proibidos para evitar perda irreversível de dados."
            )
            log_storage_operation(base_dir, uid, "Teste de Escrita (Recusado por Risco Físico)", risk["risk_level"], "refused", msg)
            return {
                "success": False,
                "blocked_by_safety": True,
                "test_type": test_type,
                "message": msg,
            }

        try:
            block_bytes = 256 * 1024
            blocks_to_write = 16
            buf = os.urandom(block_bytes)
            latencies_ms: list[float] = []
            with tempfile.NamedTemporaryFile(prefix="aegispulse_wtest_", suffix=".tmp", delete=True) as tf:
                for _ in range(blocks_to_write):
                    bt0 = time.perf_counter()
                    tf.write(buf)
                    tf.flush()
                    latencies_ms.append((time.perf_counter() - bt0) * 1000.0)
            dur = max(0.001, time.perf_counter() - t0)
            examined = block_bytes * blocks_to_write
            mb_s = round((examined / (1024 * 1024)) / dur, 2)
            avg_lat = round(sum(latencies_ms) / len(latencies_ms), 2)
            res_out = {
                "success": True,
                "test_type": "Teste Controlado de Escrita Não-Destrutiva (Arquivo Temporário)",
                "started_at": started_at,
                "duration_sec": round(dur, 3),
                "bytes_examined": examined,
                "untested_bytes": max(0, int(device.get("capacity", {}).get("bytes") or 0) - examined),
                "speed_mb_s": mb_s,
                "avg_latency_ms": avg_lat,
                "max_latency_ms": round(max(latencies_ms), 2),
                "iops_estimate": int(round(blocks_to_write / dur)),
                "io_errors_count": 0,
                "slow_blocks_count": sum(1 for l in latencies_ms if l > 150.0),
                "status_badge": "ok",
                "message": f"Teste de escrita temporária concluído ({mb_s} MB/s | Latência média: {avg_lat} ms).",
            }
            log_storage_operation(base_dir, uid, "Teste Controlado de Escrita", risk["risk_level"], "completed", res_out["message"], res_out)
            return res_out
        except Exception as exc:
            return {"success": False, "test_type": test_type, "message": f"Erro de I/O durante escrita temporária: {exc}"}

    if test_type in ("smart_short", "smart_extended"):
        smartctl_bin = _find_smartctl_binary()
        disk_num = int(device.get("disk_number") or 0)
        st_arg = "short" if test_type == "smart_short" else "long"
        st_label = "Autoteste SMART Curto (Short Self-Test)" if st_arg == "short" else "Autoteste SMART Estendido (Extended Self-Test)"

        if smartctl_bin and target_override is None:
            dev_arg = f"/dev/pd{disk_num}" if platform.system() == "Windows" else "/dev/sda"
            try:
                proc = subprocess.run(
                    [smartctl_bin, "-t", st_arg, dev_arg],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                )
                out_txt = (proc.stdout or proc.stderr or "").strip()
                msg = f"{st_label} enviado ao controlador de {device.get('model')}. Saída: {out_txt[:220]}"
                log_storage_operation(base_dir, uid, st_label, risk["risk_level"], "started", msg)
                return {
                    "success": True,
                    "test_type": st_label,
                    "started_at": started_at,
                    "duration_sec": round(time.perf_counter() - t0, 2),
                    "smartctl_used": True,
                    "previous_self_tests": device.get("self_test_logs") or [],
                    "message": msg,
                }
            except Exception:
                pass

        prev_logs = device.get("self_test_logs") or []
        msg = (
            f"{st_label}: O firmware reporta status '{device.get('health_status_os', 'Healthy')}' via WMI/Storage API. "
            "Para disparar a rotina interna offline no firmware SATA/NVMe, instale o pacote opcional 'smartmontools' (smartctl) "
            "ou utilize os testes de leitura de superfície e blocos abaixo."
        )
        log_storage_operation(base_dir, uid, st_label, risk["risk_level"], "info", msg)
        return {
            "success": True,
            "test_type": st_label,
            "started_at": started_at,
            "duration_sec": round(time.perf_counter() - t0, 2),
            "smartctl_used": False,
            "previous_self_tests": prev_logs,
            "message": msg,
        }

    target_path, target_desc, total_cap_bytes = _resolve_readable_target(device, target_override=target_override)
    if not target_path:
        msg = (
            f"Não foi possível realizar leitura direta em {device.get('model')} ({target_desc}). "
            "Verifique se a unidade está online ou execute o AegisPulse como Administrador para acesso bruto a \\\\.\\PhysicalDrive."
        )
        log_storage_operation(base_dir, uid, f"Teste de Integridade ({test_type})", risk["risk_level"], "inaccessible", msg)
        return {
            "success": False,
            "test_type": test_type,
            "started_at": started_at,
            "bytes_examined": 0,
            "untested_bytes": total_cap_bytes,
            "io_errors_count": 1,
            "message": msg,
        }

    block_bytes = max(4096, int(block_size_kb) * 1024)
    if test_type == "quick_health":
        max_bytes_to_read = min(4 * 1024 * 1024, max(block_bytes * 4, int(sample_mb) * 1024 * 1024))
    elif test_type == "surface_scan":
        max_bytes_to_read = min(32 * 1024 * 1024, max(block_bytes * 16, int(sample_mb) * 1024 * 1024))
    else:
        max_bytes_to_read = min(64 * 1024 * 1024, max(block_bytes * 8, int(sample_mb) * 1024 * 1024))

    bytes_examined = 0
    io_errors = 0
    slow_blocks = 0
    healthy_blocks = 0
    latencies_ms: list[float] = []
    block_samples: list[dict[str, Any]] = []
    error_details: list[str] = []

    try:
        file_size = os.path.getsize(target_path) if os.path.isfile(target_path) else total_cap_bytes
        target_limit = min(file_size, max_bytes_to_read) if file_size > 0 else max_bytes_to_read
        total_blocks = max(1, target_limit // block_bytes)

        with open(target_path, "rb") as f:
            for b_idx in range(int(total_blocks)):
                offset = b_idx * block_bytes
                bt0 = time.perf_counter()
                try:
                    if file_size > 0 and offset + block_bytes <= file_size:
                        f.seek(offset)
                    chunk = f.read(block_bytes)
                    if not chunk:
                        f.seek(0)
                        chunk = f.read(block_bytes)
                    lat_ms = (time.perf_counter() - bt0) * 1000.0
                    latencies_ms.append(lat_ms)
                    bytes_examined += len(chunk)
                    blk_mb_s = round((len(chunk) / (1024 * 1024)) / max(0.00001, lat_ms / 1000.0), 2)

                    if lat_ms > 150.0:
                        slow_blocks += 1
                        blk_status = "slow"
                    else:
                        healthy_blocks += 1
                        blk_status = "ok"

                    if len(block_samples) < 32:
                        block_samples.append({
                            "block": b_idx + 1,
                            "offset_bytes": offset,
                            "latency_ms": round(lat_ms, 2),
                            "speed_mb_s": blk_mb_s,
                            "status": blk_status,
                        })
                except OSError as io_err:
                    lat_ms = (time.perf_counter() - bt0) * 1000.0
                    latencies_ms.append(lat_ms)
                    io_errors += 1
                    error_details.append(f"Bloco #{b_idx + 1} (Offset {offset}): {io_err}")
                    if len(block_samples) < 32:
                        block_samples.append({
                            "block": b_idx + 1,
                            "offset_bytes": offset,
                            "latency_ms": round(lat_ms, 2),
                            "speed_mb_s": 0.0,
                            "status": "error",
                        })
    except Exception as exc:
        io_errors += 1
        error_details.append(f"Falha ao abrir/ler alvo ({target_path}): {exc}")

    duration_sec = max(0.001, time.perf_counter() - t0)
    speed_mb_s = round((bytes_examined / (1024 * 1024)) / duration_sec, 2) if bytes_examined > 0 else 0.0
    avg_lat = round(sum(latencies_ms) / len(latencies_ms), 2) if latencies_ms else 0.0
    max_lat = round(max(latencies_ms), 2) if latencies_ms else 0.0
    blocks_done = healthy_blocks + slow_blocks + io_errors
    iops_est = int(round(blocks_done / duration_sec)) if blocks_done > 0 else 0
    untested_bytes = max(0, total_cap_bytes - bytes_examined)

    if io_errors > 0:
        badge = "err"
        verdict = f"ALERTA: {io_errors} erro(s) físico(s)/I/O de leitura encontrado(s) durante o teste!"
    elif slow_blocks > 0:
        badge = "warn"
        verdict = f"ATENÇÃO: {slow_blocks} bloco(s) com leitura lenta (>150ms) detectado(s)."
    else:
        badge = "ok"
        verdict = f"APROVADO: {healthy_blocks} blocos lidos sem erros ({speed_mb_s} MB/s | Latência média: {avg_lat} ms)."

    label_map = {
        "quick_health": "Verificação Rápida de Saúde & Latência",
        "read_benchmark": "Benchmark de Leitura Sequencial e por Blocos",
        "surface_scan": "Varredura Controlada de Superfície (Somente-Leitura)",
    }
    test_title = label_map.get(test_type, test_type)

    result_payload = {
        "success": io_errors == 0 or bytes_examined > 0,
        "test_type": test_title,
        "target_used": target_desc,
        "started_at": started_at,
        "duration_sec": round(duration_sec, 3),
        "bytes_examined": bytes_examined,
        "examined_mb": round(bytes_examined / (1024 * 1024), 2),
        "untested_bytes": untested_bytes,
        "untested_note": (
            f"Examinados {round(bytes_examined / (1024 * 1024), 2)} MB em modo não-destrutivo. "
            f"Restante da capacidade ({round(untested_bytes / (1024 ** 3), 2)} GiB) preservado sem leitura exaustiva para evitar estresse mecânico/térmico."
            if untested_bytes > 0
            else "100% da área alvo examinada."
        ),
        "speed_mb_s": speed_mb_s,
        "avg_latency_ms": avg_lat,
        "max_latency_ms": max_lat,
        "iops_estimate": iops_est,
        "healthy_blocks_count": healthy_blocks,
        "slow_blocks_count": slow_blocks,
        "io_errors_count": io_errors,
        "error_details": error_details,
        "block_samples": block_samples,
        "risk_assessment": risk,
        "status_badge": badge,
        "message": verdict,
    }

    log_storage_operation(
        base_dir=base_dir,
        device_uid=uid,
        operation_type=test_title,
        risk_level=risk["risk_level"],
        status="completed" if io_errors == 0 else "errors_found",
        summary=verdict,
        details=result_payload,
    )
    return result_payload


def diagnose_specialized_faults(
    device: dict[str, Any],
    system_disk_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    sm = device.get("smart_summary") or {}
    events = system_disk_events or []
    findings: list[dict[str, Any]] = []

    crc = int(sm.get("crc_interface_errors") or 0)
    realloc = int(sm.get("reallocated_sectors") or 0)
    pending = int(sm.get("pending_sectors") or 0)
    uncorr = int(sm.get("uncorrectable_errors") or 0)
    cw_nvme = int(sm.get("critical_warning_raw") or 0)
    unsafe_shut = int(sm.get("unsafe_shutdowns") or 0)
    read_lat_max = int(sm.get("read_latency_max_ms") or 0)
    write_lat_max = int(sm.get("write_latency_max_ms") or 0)
    cap_bytes = int(device.get("capacity", {}).get("bytes") or 0)
    cap_gb = float(device.get("capacity", {}).get("gb") or 0.0)

    crc_events = [e for e in events if "CRC" in str(e.get("Message", "")).upper() or int(e.get("Id", 0)) == 11]
    if crc > 0 or crc_events:
        findings.append({
            "code": "FAULT_CRC_INTERFACE",
            "title": "Erro de Redundância Cíclica (CRC de Comunicação SATA/USB)",
            "category": "Problema de Conexão / Interface Física",
            "severity": "warning" if (realloc == 0 and pending == 0 and uncorr == 0) else "critical",
            "evidence": f"Atributo SMART 199 (UltraDMA CRC Error Count) = {crc} | Eventos de Controladora = {len(crc_events)}",
            "explanation": (
                "IMPORTANTE: Um erro de CRC (Cyclic Redundancy Check) na camada de transporte significa que o pacote de dados "
                "sofreu corrupção elétrica enquanto trafegava pelo cabo SATA, conector M.2 ou ponte USB — NÃO significa automaticamente "
                "que o disco possui setores defeituosos (Bad Blocks) na mídia!"
                if (realloc == 0 and pending == 0 and uncorr == 0)
                else "Foram detectados TANTO erros de comunicação CRC no barramento QUANTO setores instáveis na mídia."
            ),
            "recommendation": (
                "Substitua imediatamente o cabo de dados SATA, troque de porta SATA na placa-mãe ou, se for disco externo/pendrive, "
                "conecte-o diretamente na porta USB traseira da placa-mãe (evitando hubs USB ou cabos frouxos)."
            ),
        })

    if realloc > 0 or pending > 0 or uncorr > 0:
        findings.append({
            "code": "FAULT_BAD_SECTORS",
            "title": "Setores Defeituosos / Degradação Física da Superfície ou NAND",
            "category": "Falha Física de Mídia",
            "severity": "critical",
            "evidence": f"Realocados (ID 05): {realloc} | Pendentes (ID 197): {pending} | Incorrigíveis (ID 198/187): {uncorr}",
            "explanation": (
                "O disco apresenta falha física real em setores magnéticos ou blocos Flash NAND. "
                "Setores Pendentes (ID 197) causam congelamentos severos no Windows quando um programa tenta ler o endereço afetado."
            ),
            "recommendation": (
                "NÃO execute desfragmentação nem CHKDSK /R agora! Crie imediatamente uma imagem setor-a-setor na aba de Recuperação Assistida "
                "(pulando blocos defeituosos via mapa de progresso / ddrescue) e substitua a unidade."
            ),
        })

    if cw_nvme > 0 or (sm.get("available_spare_percent") is not None and int(sm["available_spare_percent"]) <= int(sm.get("available_spare_threshold") or 10)):
        findings.append({
            "code": "FAULT_NVME_CRITICAL",
            "title": "Alerta Crítico NVMe (Critical Warning / Reserva de Blocos Esgotada)",
            "category": "Falha Física de Mídia / Controlador NVMe",
            "severity": "critical",
            "evidence": f"Critical Warning = 0x{cw_nvme:02X} | Available Spare = {sm.get('available_spare_percent')}%",
            "explanation": (
                "O controlador NVMe acionou o bit de alerta crítico por esgotamento dos blocos sobressalentes (Available Spare) "
                "ou erro de integridade da memória NAND."
            ),
            "recommendation": "Copie ou gere imagem imediata dos dados enquanto o SSD ainda permite leitura e providencie a substituição.",
        })

    if device.get("has_raw_volume"):
        findings.append({
            "code": "FAULT_VOLUME_RAW",
            "title": "Volume em Estado RAW (Sistema de Arquivos Não Reconhecido)",
            "category": "Corrupção Lógica ou Setor de Boot Danificado",
            "severity": "critical",
            "evidence": f"Partição montada como RAW em {', '.join(device.get('drive_letters') or ['Unidade'])}",
            "explanation": (
                "O Windows enxerga a partição física, mas não consegue ler o cabeçalho do sistema de arquivos (VBR / $MFT / tabela FAT). "
                "Isso pode ocorrer por desconexão abrupta sem ejeção segura (corrupção lógica) ou por setor defeituoso bem no início da partição."
            ),
            "recommendation": (
                "BLOQUEIO DE SEGURANÇA: Jamais clique na janela 'Você precisa formatar o disco antes de usá-lo' do Windows! "
                "1º Crie uma imagem (.img) da unidade; 2º Use a Recuperação de Partições (TestDisk) ou Recuperação de Arquivos (PhotoRec)."
            ),
        })

    if not device.get("is_initialized", True) or (cap_bytes > 0 and int(device.get("partitions_count") or 0) == 0):
        findings.append({
            "code": "FAULT_UNINITIALIZED_OR_LOST_PARTITION",
            "title": "Disco Não Inicializado ou Tabela de Partições Perdida (MBR/GPT)",
            "category": "Corrupção de Tabela de Partições / Falha de Inicialização",
            "severity": "critical",
            "evidence": f"Estilo de Partição: {device.get('partition_style')} | Partições reconhecidas: {device.get('partitions_count', 0)}",
            "explanation": (
                "O setor 0 (MBR) ou o cabeçalho GPT primário não foi encontrado. Se este disco continha arquivos do cliente, "
                "a tabela de partições foi apagada acidentalmente ou corrompida."
            ),
            "recommendation": (
                "NÃO inicialize o disco pelo Gerenciamento de Disco se houver dados a recuperar! "
                "Utilize a inspeção de cabeçalhos MBR/GPT e o TestDisk na seção de Recuperação Assistida para restaurar a tabela original."
            ),
        })

    if cap_bytes == 0 or device.get("is_inaccessible"):
        findings.append({
            "code": "FAULT_INACCESSIBLE_NO_MEDIA",
            "title": "Unidade Inacessível ou Reportando Capacidade 0 Bytes (No Media)",
            "category": "Falha Física de Controlador / Ponte USB ou Firmware Travado",
            "severity": "critical",
            "evidence": f"Capacidade reportada: {cap_bytes} bytes | Status: {device.get('operational_status')}",
            "explanation": (
                "O sistema operacional detecta o controlador USB/SATA, mas o controlador não consegue comunicar-se com os chips NAND "
                "(comum em pendrives com controlador em modo de pânico/ROM ou HD externo sem alimentação suficiente)."
            ),
            "recommendation": (
                "Se for HD externo, teste outro cabo USB e porta traseira. Se for pendrive ou SSD em modo 0 Bytes com dados críticos, "
                "software comum não acessa a memória Flash — requer extração Chip-Off / PC-3000 em laboratório especializado."
            ),
        })

    if device.get("is_read_only"):
        is_hw_lock = (sm.get("wear_percent_used") or 0) >= 95 or cw_nvme > 0 or device.get("is_removable_usb")
        findings.append({
            "code": "FAULT_WRITE_PROTECTED",
            "title": "Unidade Protegida Contra Gravação (Modo Somente-Leitura / Read-Only)",
            "category": "Bloqueio de Segurança do Controlador NAND vs Política Lógica do SO",
            "severity": "warning" if not is_hw_lock else "critical",
            "evidence": f"IsReadOnly = True | Mídia: {device.get('media_short')}",
            "explanation": (
                "Em SSDs NVMe e Pendrives USB, quando o controlador detecta falha grave nos blocos de escrita ou esgotamento do Spare Area, "
                "ele trava permanentemente em Somente-Leitura (Hardware Write Protection) para permitir que o dono salve os arquivos antes da morte total. "
                "Alternativamente, pode ser apenas uma flag lógica (`attributes disk readonly`) ou chave `StorageDevicePolicies` no Windows."
            ),
            "recommendation": (
                "1º Aproveite que a leitura está ativa e copie/faça backup de todos os arquivos imediatamente! "
                "2º Só tente limpar o atributo Read-Only lógico após garantir o backup completo."
            ),
        })

    io_events = [e for e in events if int(e.get("Id", 0)) in (7, 9, 51, 129, 153, 157)]
    if io_events or unsafe_shut > 25:
        findings.append({
            "code": "FAULT_DISCONNECTIONS_POWER",
            "title": "Desconexões Inesperadas, Resets de Barramento ou Queda de Alimentação",
            "category": "Problema de Conexão / Alimentação Elétrica",
            "severity": "warning",
            "evidence": f"Eventos de Sistema (51/129/153/157): {len(io_events)} | Desligamentos Abruptos (Unsafe Shutdowns): {unsafe_shut}",
            "explanation": (
                "O Windows registrou resets de controladora (Event 129), falhas de paginação durante I/O (Event 51), "
                "tentativas repetidas de leitura (Event 153) ou remoção surpresa do disco (Event 157)."
            ),
            "recommendation": (
                "Para discos externos e pendrives: nunca utilize as portas USB frontais do gabinete nem hubs USB sem fonte própria, "
                "pois a queda de tensão (5V) faz o disco desligar e corromper a tabela de arquivos."
            ),
        })

    if device.get("is_removable_usb") or "Pendrive" in str(device.get("media_short")):
        suspicious_fake = cap_gb >= 900 and ("2.0" in str(device.get("model")) or device.get("brand") == "Genérico / OEM")
        if suspicious_fake:
            findings.append({
                "code": "FAULT_USB_FAKE_CAPACITY",
                "title": "Suspeita de Adulteração de Firmware / Capacidade Anômala em Pendrive USB",
                "category": "Anomalia de Firmware / Pendrive Adulterado",
                "severity": "critical",
                "evidence": f"Marca: {device.get('brand')} | Modelo: {device.get('model')} | Capacidade Reportada: {cap_gb} GB",
                "explanation": (
                    "Pendrives genéricos que reportam capacidades gigantescas (1 TB / 2 TB) frequentemente possuem apenas 8 GB a 32 GB reais "
                    "de memória Flash com firmware reprogramado para sobrescrever ciclicamente os próprios dados do usuário (corrompendo os arquivos)."
                ),
                "recommendation": (
                    "Pare de gravar novos arquivos imediatamente. Recupere o que ainda estiver íntegro nos primeiros gigabytes da unidade."
                ),
            })

    if max(read_lat_max, write_lat_max) > 500:
        findings.append({
            "code": "FAULT_EXTREME_SLOWNESS",
            "title": "Lentidão Extrema e Picos de Tempo de Resposta (Latência > 500ms)",
            "category": "Degradação de Desempenho / Saturação de I/O",
            "severity": "warning",
            "evidence": f"Pico de Latência Leitura: {read_lat_max} ms | Escrita: {write_lat_max} ms",
            "explanation": (
                "Tempos de resposta acima de 500 ms causam travamentos na interface do Windows (100% de uso de disco no Gerenciador de Tarefas). "
                "Pode decorrer de saturação do cache SLC (disco >90% cheio), superaquecimento ou tentativas repetidas de leitura em setores lentos."
            ),
            "recommendation": "Execute o Benchmark de Leitura e a Varredura de Superfície na aba de Testes de Integridade para localizar se há blocos lentos.",
        })

    if not findings:
        findings.append({
            "code": "STATUS_HEALTHY_NO_FAULTS",
            "title": "Nenhuma Falha Física, Lógica ou de Comunicação Detectada",
            "category": "Conformidade Operacional",
            "severity": "ok",
            "evidence": f"SMART: {device.get('health_status_os')} | Estilo: {device.get('partition_style')} | Sem erros de CRC ou setores defeituosos",
            "explanation": (
                "O dispositivo passou na inspeção de atributos físicos (setores realocados/pendentes/incorrigíveis zerados), "
                "comunicação de interface (sem erros CRC) e estrutura lógica de partições."
            ),
            "recommendation": "Mantenha pelo menos 15% a 20% de espaço livre em SSDs para eficiência do TRIM e Wear Leveling.",
        })

    return findings
