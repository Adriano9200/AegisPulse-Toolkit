#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/storage_health.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.0.0
================================================================================
Descrição:
Etapa 2 e Etapa 8 — Saúde, Estimativa de Vida Útil, Monitoramento Histórico
Persistente (SQLite) e Classificação de Risco/Segurança:
- Calcula tempo acumulado de funcionamento em horas, dias e anos.
- Registra no SQLite (`data/aegispulse_storage.db`) a evolução de gravações (TBW),
  leituras, temperatura, desgaste e erros por dispositivo (`device_uid`).
- Diferencia estritamente:
  1. Vida útil reportada pelo fabricante (SMART/Firmware),
  2. Desgaste estimado por volume de gravação (TBW nominal de referência),
  3. Tendência histórica de desgaste (quando houver coletas suficientes).
- Jamais promete uma data exata de falha nem inventa estimativas sem evidências.
- Classifica o risco em BAIXO, MODERADO, ALTO ou CRÍTICO, determinando quando é
  obrigatório criar imagem antes de reparar e quando recomendar laboratório
  especializado (Cleanroom / Recuperação Física).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


def get_storage_db_path(base_dir: Path) -> Path:
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "aegispulse_storage.db"


def init_storage_db(base_dir: Path) -> None:
    db_path = get_storage_db_path(base_dir)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS disk_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_uid TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                model TEXT,
                serial_number TEXT,
                media_short TEXT,
                capacity_bytes INTEGER,
                temperature_c REAL,
                power_on_hours INTEGER,
                power_cycles INTEGER,
                total_reads_gb REAL,
                total_writes_gb REAL,
                wear_percent_used REAL,
                reallocated_sectors INTEGER,
                pending_sectors INTEGER,
                uncorrectable_errors INTEGER,
                crc_errors INTEGER,
                health_score INTEGER,
                risk_level TEXT,
                summary_json TEXT
            )
            '''
        )
        conn.execute(
            '''
            CREATE INDEX IF NOT EXISTS idx_snapshots_uid
            ON disk_snapshots (device_uid, id DESC)
            '''
        )
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS storage_operations_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_uid TEXT,
                operation_type TEXT NOT NULL,
                risk_level TEXT,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                details_json TEXT
            )
            '''
        )
        conn.commit()
    finally:
        conn.close()


def log_storage_operation(
    base_dir: Path,
    device_uid: str,
    operation_type: str,
    risk_level: str,
    status: str,
    summary: str,
    details: dict[str, Any] | None = None,
) -> None:
    init_storage_db(base_dir)
    db_path = get_storage_db_path(base_dir)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            '''
            INSERT INTO storage_operations_log
            (timestamp, device_uid, operation_type, risk_level, status, summary, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                now_str,
                device_uid or "GLOBAL",
                operation_type,
                risk_level,
                status,
                summary,
                json.dumps(details or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_storage_operations_log(base_dir: Path, device_uid: str | None = None, limit: int = 40) -> list[dict[str, Any]]:
    init_storage_db(base_dir)
    db_path = get_storage_db_path(base_dir)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        if device_uid:
            rows = conn.execute(
                "SELECT * FROM storage_operations_log WHERE device_uid = ? ORDER BY id DESC LIMIT ?",
                (device_uid, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM storage_operations_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["details"] = json.loads(d.get("details_json") or "{}")
        except Exception:
            d["details"] = {}
        out.append(d)
    return out


def _estimate_nominal_tbw_reference(capacity_gb: float, media_short: str) -> float | None:
    if "SSD" not in (media_short or "").upper() or capacity_gb <= 0:
        return None
    if capacity_gb <= 150:
        return 75.0
    if capacity_gb <= 300:
        return 150.0
    if capacity_gb <= 600:
        return 300.0
    if capacity_gb <= 1200:
        return 600.0
    if capacity_gb <= 2400:
        return 1200.0
    return round(capacity_gb * 0.6, 1)


def classify_storage_risk(
    device: dict[str, Any],
    data_importance: str = "alta",
    recent_disconnections: int = 0,
) -> dict[str, Any]:
    sm = device.get("smart_summary") or {}
    media_short = str(device.get("media_short") or "")
    is_ssd = "SSD" in media_short.upper()

    realloc = int(sm.get("reallocated_sectors") or 0)
    pending = int(sm.get("pending_sectors") or 0)
    uncorr = int(sm.get("uncorrectable_errors") or 0)
    crc_err = int(sm.get("crc_interface_errors") or 0)
    cw_nvme = int(sm.get("critical_warning_raw") or 0)
    wear_pct = sm.get("wear_percent_used")
    avail_spare = sm.get("available_spare_percent")
    spare_thresh = sm.get("available_spare_threshold") or 10
    temp_c = sm.get("temperature_c")
    unsafe_shut = int(sm.get("unsafe_shutdowns") or 0)

    has_raw = bool(device.get("has_raw_volume"))
    is_uninit = not bool(device.get("is_initialized", True))
    is_inacc = bool(device.get("is_inaccessible"))
    is_ro = bool(device.get("is_read_only"))
    predict_fail = bool(device.get("smart_predict_failure"))
    health_os = str(device.get("health_status_os") or "Healthy").upper()

    score = 100
    reasons: list[str] = []
    physical_failure_signs = False

    if predict_fail or cw_nvme > 0 or health_os in ("UNHEALTHY", "PREDICTED FAILURE", "CRITICAL"):
        score -= 60
        physical_failure_signs = True
        reasons.append("Sinalizador de falha iminente SMART / Critical Warning ativo no firmware.")

    if uncorr > 0:
        score -= min(55, 30 + uncorr * 5)
        physical_failure_signs = True
        reasons.append(f"{uncorr} erro(s) incorrigível(is) de mídia/ECC detectado(s) (perda física de integridade em setores).")

    if pending > 0:
        score -= min(50, 25 + pending * 4)
        physical_failure_signs = True
        reasons.append(f"{pending} setor(es) pendente(s) (instáveis) aguardando remapeamento — alto risco de travamento de I/O.")

    if realloc > 0:
        score -= min(45, 15 + realloc * 2)
        physical_failure_signs = True
        reasons.append(f"{realloc} setor(es) defeituoso(s) já realocado(s) para a área de reserva (Spare Area).")

    if avail_spare is not None and int(avail_spare) <= int(spare_thresh):
        score -= 50
        physical_failure_signs = True
        reasons.append(f"Reserva de blocos NVMe (Available Spare = {avail_spare}%) atingiu ou caiu abaixo do limiar mínimo ({spare_thresh}%).")

    if wear_pct is not None:
        w = float(wear_pct)
        if w >= 100:
            score -= 35
            reasons.append(f"Desgaste reportado atingiu {w}% (resistência nominal TBW esgotada).")
        elif w >= 85:
            score -= 18
            reasons.append(f"Desgaste elevado da memória Flash NAND ({w}% utilizado).")

    if has_raw:
        score -= 30
        reasons.append("Volume em estado RAW (sistema de arquivos corrompido ou ilegível pelo Windows).")
    if is_uninit and int(device.get("capacity", {}).get("bytes") or 0) > 0:
        score -= 25
        reasons.append("Disco físico sem tabela de partições inicializada (MBR/GPT ausente ou danificado).")
    if is_ro:
        score -= 25
        if is_ssd or device.get("is_removable_usb"):
            reasons.append("Unidade em modo Somente-Leitura (pode indicar trava de segurança do controlador por fim de vida NAND ou bloqueio lógico).")
        else:
            reasons.append("Unidade marcada como Somente-Leitura (Read-Only).")
    if is_inacc and int(device.get("capacity", {}).get("bytes") or 0) == 0:
        score -= 65
        physical_failure_signs = True
        reasons.append("Dispositivo reporta capacidade 0 Bytes (Sem Mídia / Controlador não enxerga a memória Flash ou pratos).")

    if temp_c is not None:
        tc = float(temp_c)
        crit_t = 72.0 if is_ssd else 60.0
        warn_t = 62.0 if is_ssd else 52.0
        if tc >= crit_t:
            score -= 25
            reasons.append(f"Temperatura crítica ({tc}°C >= {crit_t}°C) — risco de Thermal Throttling severo e degradação acelerada.")
        elif tc >= warn_t:
            score -= 10
            reasons.append(f"Temperatura elevada ({tc}°C) — recomenda-se melhorar fluxo de ar ou dissipador térmico.")

    if crc_err > 0:
        score -= min(15, 5 + (1 if crc_err < 10 else 10))
        reasons.append(
            f"{crc_err} erro(s) de CRC (UltraDMA/Interface): indica ruído ou mau contato no cabo SATA/porta USB (não significa necessariamente setor defeituoso)."
        )

    if recent_disconnections > 0 or unsafe_shut > 100:
        score -= 12
        reasons.append(f"Histórico de desconexões abruptas ou resets de barramento ({recent_disconnections} eventos recentes / {unsafe_shut} desligamentos inseguros).")

    score = max(0, min(100, score))

    if score < 45 or (physical_failure_signs and (uncorr > 0 or pending > 5 or realloc > 20 or cw_nvme > 0)):
        risk_level = "CRÍTICO"
    elif score < 70 or physical_failure_signs or has_raw or is_uninit:
        risk_level = "ALTO"
    elif score < 90 or crc_err > 0 or is_ro:
        risk_level = "MODERADO"
    else:
        risk_level = "BAIXO"

    if data_importance in ("alta", "critica_missao") and risk_level == "MODERADO" and (has_raw or physical_failure_signs):
        risk_level = "ALTO"

    requires_image = risk_level in ("ALTO", "CRÍTICO") or has_raw or physical_failure_signs
    block_auto_chkdsk = physical_failure_signs or risk_level == "CRÍTICO"
    recommend_lab = (
        risk_level == "CRÍTICO"
        and physical_failure_signs
        and data_importance in ("alta", "critica_missao")
    ) or (int(device.get("capacity", {}).get("bytes") or 0) == 0 and device.get("is_inaccessible"))

    if not reasons:
        reasons.append("Todos os indicadores SMART, térmicos e de superfície verificados estão dentro dos parâmetros normais.")

    ordered_plan: list[str] = []
    if recommend_lab:
        ordered_plan.append(
            "1. [PRIORIDADE MÁXIMA — PRESERVAÇÃO FÍSICA] Interromper imediatamente escritas ou tentativas de reparo lógico (CHKDSK). "
            "Se os dados forem insubstituíveis, encaminhar para laboratório especializado com sala limpa (Cleanroom) / PC-3000."
        )
    if requires_image:
        ordered_plan.append(
            "2. [CLONAGEM / IMAGEM PRÉVIA OBRIGATÓRIA] Criar uma imagem setor-a-setor (.img) com mapa de progresso (AegisPulse Imager ou GNU ddrescue) "
            "para outra unidade saudável antes de tentar qualquer recuperação de partições ou arquivos."
        )
    if block_auto_chkdsk:
        ordered_plan.append(
            "3. [BLOQUEIO DE SEGURANÇA ATIVO] NÃO executar CHKDSK /F ou /R diretamente no disco afetado, pois a realocação forçada da tabela MFT sobre setores instáveis pode destruir dados recuperáveis."
        )
    elif has_raw or is_uninit:
        ordered_plan.append(
            "3. [RECUPERAÇÃO NÃO-DESTRUTIVA] Inspecionar cabeçalhos de partição (TestDisk) ou extrair arquivos (PhotoRec / Scanner Nativo) salvando o resultado em outro disco."
        )
    else:
        ordered_plan.append(
            "1. [MANUTENÇÃO PREVENTIVA] Manter rotina regular de backup 3-2-1 e monitorar evolução histórica de temperatura e TBW no AegisPulse."
        )

    return {
        "health_score": score,
        "risk_level": risk_level,
        "data_importance": data_importance,
        "physical_failure_suspected": physical_failure_signs,
        "requires_image_before_repair": requires_image,
        "block_destructive_or_chkdsk_write": block_auto_chkdsk,
        "recommend_cleanroom_lab": recommend_lab,
        "reasons": reasons,
        "ordered_action_plan": ordered_plan,
    }


def evaluate_lifespan_and_record_history(
    base_dir: Path,
    device: dict[str, Any],
    data_importance: str = "alta",
    record_snapshot: bool = True,
) -> dict[str, Any]:
    init_storage_db(base_dir)
    db_path = get_storage_db_path(base_dir)

    uid = device["device_uid"]
    sm = device.get("smart_summary") or {}
    cap_gb = float(device.get("capacity", {}).get("gb") or 0.0)
    media_short = str(device.get("media_short") or "")

    poh = sm.get("power_on_hours")
    poh_days = round(poh / 24.0, 1) if poh is not None else None
    poh_years = round(poh / 8760.0, 2) if poh is not None else None

    writes_gb = sm.get("total_writes_gb")
    writes_tb = round(writes_gb / 1024.0, 3) if writes_gb is not None else None
    reads_gb = sm.get("total_reads_gb")
    reads_tb = round(reads_gb / 1024.0, 3) if reads_gb is not None else None

    manuf_life_pct = sm.get("life_remaining_percent")
    wear_used_pct = sm.get("wear_percent_used")
    if manuf_life_pct is not None:
        manuf_life_str = f"{manuf_life_pct}% restante ({wear_used_pct}% de desgaste reportado pelo firmware)"
    else:
        manuf_life_str = "Não reportado pelo firmware/controlador deste dispositivo"

    ref_tbw = _estimate_nominal_tbw_reference(cap_gb, media_short)
    est_tbw_wear_pct = None
    if ref_tbw and writes_tb is not None:
        est_tbw_wear_pct = round((writes_tb / ref_tbw) * 100, 2)
        tbw_est_str = f"{est_tbw_wear_pct}% da resistência típica de referência ({writes_tb} TB gravados de ~{ref_tbw} TBW nominais)"
    else:
        tbw_est_str = "Indisponível (o controlador não expõe contador de Host Writes/TBW ou trata-se de mídia magnética/USB)"

    avg_daily_write_gb = None
    if poh_days and poh_days >= 1.0 and writes_gb is not None:
        avg_daily_write_gb = round(writes_gb / poh_days, 2)

    risk_info = classify_storage_risk(device, data_importance=data_importance)

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        prev_rows = conn.execute(
            "SELECT * FROM disk_snapshots WHERE device_uid = ? ORDER BY id DESC LIMIT 15",
            (uid,),
        ).fetchall()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if record_snapshot:
            conn.execute(
                """
                INSERT INTO disk_snapshots (
                    device_uid, captured_at, model, serial_number, media_short,
                    capacity_bytes, temperature_c, power_on_hours, power_cycles,
                    total_reads_gb, total_writes_gb, wear_percent_used,
                    reallocated_sectors, pending_sectors, uncorrectable_errors,
                    crc_errors, health_score, risk_level, summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    now_str,
                    device.get("model"),
                    device.get("serial_number"),
                    media_short,
                    int(device.get("capacity", {}).get("bytes") or 0),
                    sm.get("temperature_c"),
                    poh,
                    sm.get("power_cycles"),
                    reads_gb,
                    writes_gb,
                    wear_used_pct,
                    int(sm.get("reallocated_sectors") or 0),
                    int(sm.get("pending_sectors") or 0),
                    int(sm.get("uncorrectable_errors") or 0),
                    int(sm.get("crc_interface_errors") or 0),
                    risk_info["health_score"],
                    risk_info["risk_level"],
                    json.dumps(sm, ensure_ascii=False),
                ),
            )
            conn.commit()
            prev_rows = conn.execute(
                "SELECT * FROM disk_snapshots WHERE device_uid = ? ORDER BY id DESC LIMIT 15",
                (uid,),
            ).fetchall()
    finally:
        conn.close()

    snapshots_history = [dict(r) for r in reversed(prev_rows)]
    degradation_alerts: list[str] = []

    if len(snapshots_history) >= 2:
        oldest = snapshots_history[0]
        prev = snapshots_history[-2]
        curr = snapshots_history[-1]

        if (curr.get("reallocated_sectors") or 0) > (prev.get("reallocated_sectors") or 0):
            diff = (curr.get("reallocated_sectors") or 0) - (prev.get("reallocated_sectors") or 0)
            degradation_alerts.append(f"⚠️ Aumento de +{diff} setor(es) realocado(s) desde a última coleta ({prev['captured_at']})!")
        if (curr.get("pending_sectors") or 0) > (prev.get("pending_sectors") or 0):
            diff = (curr.get("pending_sectors") or 0) - (prev.get("pending_sectors") or 0)
            degradation_alerts.append(f"🚨 Surgimento de +{diff} setor(es) pendente(s) instável(is) desde a última coleta!")
        if (curr.get("uncorrectable_errors") or 0) > (prev.get("uncorrectable_errors") or 0):
            diff = (curr.get("uncorrectable_errors") or 0) - (prev.get("uncorrectable_errors") or 0)
            degradation_alerts.append(f"🚨 Aumento de +{diff} erro(s) incorrigível(is) de mídia desde a última coleta!")
        if (curr.get("crc_errors") or 0) > (prev.get("crc_errors") or 0):
            diff = (curr.get("crc_errors") or 0) - (prev.get("crc_errors") or 0)
            degradation_alerts.append(f"⚠️ Aumento de +{diff} erro(s) CRC de interface: verifique cabo SATA ou conexão USB.")
        if (curr.get("wear_percent_used") or 0) > (oldest.get("wear_percent_used") or 0):
            diff = (curr.get("wear_percent_used") or 0) - (oldest.get("wear_percent_used") or 0)
            degradation_alerts.append(f"ℹ️ Evolução do desgaste de +{diff}% desde o registro inicial em {oldest['captured_at']}.")

    if risk_info["physical_failure_suspected"]:
        failure_forecast_note = (
            "ALERTA TÉCNICO: Há evidências físicas de degradação (setores realocados/pendentes ou erros de mídia). "
            "Falhas eletrônicas e magnéticas não seguem cronograma fixo e podem evoluir abruptamente — realize backup/imagem imediatamente."
        )
    elif avg_daily_write_gb is not None and manuf_life_pct is not None and manuf_life_pct > 0:
        failure_forecast_note = (
            f"Ritmo médio histórico de gravação: ~{avg_daily_write_gb} GB/dia com {manuf_life_pct}% de vida útil reportada restante. "
            "Nota técnica: a resistência de células NAND orienta o desgaste gradual, mas não permite prever uma data exata de falha eletrônica."
        )
    else:
        failure_forecast_note = (
            "Coleta registrada no histórico SQLite. Continue realizando coletas periódicas para traçar a curva de tendência de desgaste "
            "(não é tecnicamente possível prever uma data exata de falha sem incorrer em adivinhação)."
        )

    return {
        "power_on_hours": poh,
        "power_on_days": poh_days,
        "power_on_years": poh_years,
        "power_on_formatted": f"{poh:,} horas (~{poh_days} dias / {poh_years} anos)" if poh is not None else "Não reportado pelo dispositivo",
        "manufacturer_reported_life_pct": manuf_life_pct,
        "manufacturer_reported_str": manuf_life_str,
        "estimated_tbw_wear_pct": est_tbw_wear_pct,
        "reference_tbw_limit": ref_tbw,
        "estimated_tbw_str": tbw_est_str,
        "avg_daily_write_gb": avg_daily_write_gb,
        "total_reads_formatted": f"{reads_gb:,.2f} GB ({reads_tb} TB)" if reads_gb is not None else "Não suportado pelo controlador",
        "total_writes_formatted": f"{writes_gb:,.2f} GB ({writes_tb} TBW)" if writes_gb is not None else "Não suportado pelo controlador",
        "failure_forecast_disclaimer": failure_forecast_note,
        "degradation_alerts": degradation_alerts,
        "snapshots_count": len(snapshots_history),
        "history_series": snapshots_history,
        "risk_assessment": risk_info,
    }


def build_complete_storage_suite_payload(
    base_dir: Path,
    raw_override: dict[str, Any] | None = None,
    data_importance: str = "alta",
    record_snapshot: bool = True,
) -> dict[str, Any]:
    from backend.collectors.storage_advanced import collect_storage_forensics
    from backend.services.storage_diagnostics import diagnose_specialized_faults
    from backend.services.storage_recovery import detect_external_recovery_tools

    forensics = collect_storage_forensics(raw_override=raw_override)
    sys_events = forensics.get("system_disk_events") or []
    enriched_devices: list[dict[str, Any]] = []

    highest_risk = "BAIXO"
    risk_order = {"BAIXO": 0, "MODERADO": 1, "ALTO": 2, "CRÍTICO": 3}

    for dev in (forensics.get("devices") or []):
        lifespan_and_risk = evaluate_lifespan_and_record_history(
            base_dir=base_dir,
            device=dev,
            data_importance=data_importance,
            record_snapshot=record_snapshot,
        )
        faults = diagnose_specialized_faults(device=dev, system_disk_events=sys_events)
        dev["lifespan"] = lifespan_and_risk
        dev["risk_assessment"] = lifespan_and_risk["risk_assessment"]
        dev["fault_diagnostics"] = faults

        r_lvl = dev["risk_assessment"]["risk_level"]
        if risk_order.get(r_lvl, 0) > risk_order.get(highest_risk, 0):
            highest_risk = r_lvl

        enriched_devices.append(dev)

    ext_tools = detect_external_recovery_tools()
    ops_log = list_storage_operations_log(base_dir=base_dir, limit=35)

    return {
        "collected_at": forensics.get("collected_at"),
        "smartctl_available": forensics.get("smartctl_available"),
        "smartctl_path": forensics.get("smartctl_path"),
        "total_physical_disks": len(enriched_devices),
        "highest_risk_level": highest_risk,
        "devices": enriched_devices,
        "system_disk_events": sys_events,
        "external_recovery_tools": ext_tools,
        "operations_log": ops_log,
    }
