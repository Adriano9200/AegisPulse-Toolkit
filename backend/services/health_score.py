#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/health_score.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.5.0
================================================================================
Descrição:
Módulo AegisPulse Health Score — Índice Inteligente de Saúde do Computador:
- Avaliação técnica determinística e reproduzível de 0 a 100 baseada em evidências.
- Faixas de Classificação:
    90–100 : Excelente (Verde)
    75–89  : Bom (Verde Claro)
    60–74  : Atenção (Amarelo)
    40–59  : Ruim (Laranja)
    0–39   : Crítico (Vermelho)
- 8 Categorias Ponderadas:
    1. Armazenamento & SMART (20%)
    2. Memória RAM (15%)
    3. Processador / CPU (15%)
    4. Temperaturas & Refrigeração (15%)
    5. Sistema Operacional & Estabilidade (10%)
    6. Drivers & Dispositivos PnP (10%)
    7. Desempenho & Runtimes/Gargalos (8%)
    8. Segurança Básica (7%)
- Cálculo real de cobertura (categorias disponíveis vs ausentes).
- Trava de Não-Mascaramento de Falha Crítica: falhas críticas de hardware/dados
  impedem classificação Excelente/Bom mesmo com média alta.
- Trilha de auditoria explícita: lista de fatores de dedução e métricas observadas.
- Diagnóstico acionável priorizado por gravidade, impacto, evidência, confiança e risco.
- Persistência no SQLite existente (`data/aegispulse_storage.db`), análise de
  tendências e comparação temporal (diff inteligente).
- Independência da IA: o score é 100% determinístico; a IA atua na interpretação.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.storage_health import get_storage_db_path

ALGORITHM_VERSION = "4.5.0"

# Faixas de classificação oficiais
SCORE_BANDS = [
    (90.0, 100.0, "Excelente", "#10b981", "ok"),
    (75.0, 89.9, "Bom", "#34d399", "ok"),
    (60.0, 74.9, "Atenção", "#f59e0b", "warn"),
    (40.0, 59.9, "Ruim", "#f97316", "warn"),
    (0.0, 39.9, "Crítico", "#ef4444", "err"),
]

# Pesos base nominais das 8 categorias (total = 100)
BASE_CATEGORY_WEIGHTS: dict[str, float] = {
    "storage": 20.0,
    "ram": 15.0,
    "cpu": 15.0,
    "thermals": 15.0,
    "os_stability": 10.0,
    "drivers_devices": 10.0,
    "performance": 8.0,
    "security": 7.0,
}

CATEGORY_TITLES: dict[str, str] = {
    "storage": "Armazenamento & Saúde SMART",
    "ram": "Memória RAM & Pressão",
    "cpu": "Processador & Carga",
    "thermals": "Temperaturas & Refrigeração",
    "os_stability": "Sistema Operacional & Estabilidade",
    "drivers_devices": "Drivers & Dispositivos PnP",
    "performance": "Desempenho & Gargalos",
    "security": "Segurança Básica & TPM",
}


def get_machine_identifier(hardware: dict[str, Any]) -> str:
    """Gera um identificador estável e não-volátil do equipamento a partir do UUID, Placa-Mãe ou Service Tag."""
    uuid_raw = str(hardware.get("uuid") or "").strip()
    tag_raw = str(hardware.get("serial_service_tag") or "").strip()
    mb_raw = str(hardware.get("motherboard", {}).get("serial") or "").strip()
    host_raw = str(hardware.get("hostname") or "UNKNOWN_HOST").strip()

    valid_id_parts = []
    for val in (uuid_raw, tag_raw, mb_raw):
        if val and val.upper() not in ("N/D", "NONE", "DEFAULT STRING", "TO BE FILLED BY O.E.M.", "0", "UNKNOWN"):
            valid_id_parts.append(val)

    if valid_id_parts:
        fingerprint = ":".join(valid_id_parts)
    else:
        fingerprint = f"{hardware.get('manufacturer', 'OEM')}:{hardware.get('model', 'PC')}:{host_raw}"

    stable_hash = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16].upper()
    return f"AEGIS-DEV-{stable_hash}"


def init_health_score_db(base_dir: Path) -> None:
    """Inicializa as tabelas de Health Score dentro do banco de dados SQLite existente."""
    db_path = get_storage_db_path(base_dir)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS health_score_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_uuid TEXT NOT NULL,
                hostname TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                algorithm_version TEXT NOT NULL,
                overall_score REAL NOT NULL,
                classification TEXT NOT NULL,
                coverage_count INTEGER NOT NULL,
                coverage_total INTEGER NOT NULL,
                coverage_percent REAL NOT NULL,
                has_critical_issue INTEGER NOT NULL,
                critical_cap_applied INTEGER NOT NULL,
                categories_json TEXT NOT NULL,
                findings_json TEXT NOT NULL,
                audit_breakdown_json TEXT NOT NULL,
                raw_metrics_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_health_eval_uuid
            ON health_score_evaluations (machine_uuid, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_health_eval_date
            ON health_score_evaluations (evaluated_at DESC)
            """
        )
        conn.commit()
    finally:
        conn.close()


def classify_score(score: float) -> tuple[str, str, str]:
    """Retorna (Classificação, Cor Hex, Badge Class)."""
    s = max(0.0, min(100.0, float(score)))
    for min_s, max_s, label, color, badge in SCORE_BANDS:
        if s >= min_s:
            return label, color, badge
    return "Crítico", "#ef4444", "err"


def _eval_storage(storage_suite: dict[str, Any], hw_volumes: list[dict[str, Any]]) -> dict[str, Any]:
    """Avalia integridade física dos discos, atributos SMART, setores e espaço livre."""
    devs = storage_suite.get("devices") or []
    if not devs:
        return {
            "available": False,
            "status": "desconhecido",
            "score": 0.0,
            "deductions": [],
            "metrics_observed": {"disks_count": 0},
            "findings": [],
            "summary": "Nenhum disco físico reportado pelo coletor de armazenamento.",
        }

    score = 100.0
    deductions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {
        "disks_count": len(devs),
        "total_reallocated": 0,
        "total_pending": 0,
        "total_uncorrectable": 0,
        "total_crc": 0,
        "critical_warning_count": 0,
        "raw_volumes_count": 0,
        "min_free_space_gb": None,
        "min_free_space_pct": None,
    }

    has_critical_disk_issue = False

    for d in devs:
        sm = d.get("smart_summary") or {}
        lf = d.get("lifespan") or {}
        model = str(d.get("model") or "Disco")
        serial = str(d.get("serial_number") or "N/D")

        realloc = int(sm.get("reallocated_sectors") or 0)
        pending = int(sm.get("pending_sectors") or 0)
        uncorr = int(sm.get("uncorrectable_errors") or 0)
        crc = int(sm.get("crc_interface_errors") or 0)
        cw = int(sm.get("critical_warning_raw") or 0)
        spare = sm.get("available_spare_percent")
        spare_th = sm.get("available_spare_threshold") or 10
        wear_pct = sm.get("wear_percent_used")

        metrics["total_reallocated"] += realloc
        metrics["total_pending"] += pending
        metrics["total_uncorrectable"] += uncorr
        metrics["total_crc"] += crc
        if cw > 0:
            metrics["critical_warning_count"] += 1

        if d.get("has_raw_volume"):
            metrics["raw_volumes_count"] += 1
            score -= 35.0
            has_critical_disk_issue = True
            deductions.append({
                "points": 35.0,
                "reason": f"Volume em estado RAW detectado em {model} (corrupção de sistema de arquivos ou falha de leitura no cabeçalho VBR/$MFT).",
            })
            findings.append({
                "id": "STORAGE_RAW_VOLUME",
                "category": "storage",
                "title": f"Volume em Estado RAW ({model})",
                "severity": "CRÍTICO",
                "probable_impact": "Inacessibilidade imediata de arquivos e risco de formatação acidental.",
                "technical_evidence": f"Partição montada com sistema de arquivos RAW no disco {model} ({serial}).",
                "affected_component": f"Disco {d.get('disk_number')} ({model})",
                "confidence": "Fato Observado (100%)",
                "recommendation": "Não formate nem inicialize a unidade. Gere uma imagem (.img) e execute a recuperação assistida.",
                "action_risk_level": "ALTO RISCO (Exige Imagem/Cópia Prévia)",
                "needs_more_data": False,
            })

        if pending > 0:
            score -= min(45.0, 25.0 + pending * 4.0)
            has_critical_disk_issue = True
            deductions.append({
                "points": min(45.0, 25.0 + pending * 4.0),
                "reason": f"{pending} setor(es) pendente(s) instável(is) no disco {model} (SMART ID 197).",
            })
            findings.append({
                "id": "STORAGE_PENDING_SECTORS",
                "category": "storage",
                "title": f"Setores Pendentes de Leitura ({model})",
                "severity": "CRÍTICO",
                "probable_impact": "Congelamentos aleatórios do Windows e falha iminente de setores de dados.",
                "technical_evidence": f"Atributo SMART 197 = {pending} setores pendentes em {model}.",
                "affected_component": f"Disco {d.get('disk_number')} ({model})",
                "confidence": "Fato Observado (100%)",
                "recommendation": "Preserve uma imagem do disco imediatamente antes de qualquer reparo com CHKDSK.",
                "action_risk_level": "ALTO RISCO (Exige Imagem/Cópia Prévia)",
                "needs_more_data": False,
            })

        if realloc > 0:
            score -= min(30.0, 15.0 + realloc * 1.5)
            deductions.append({
                "points": min(30.0, 15.0 + realloc * 1.5),
                "reason": f"{realloc} setor(es) defeituoso(s) já realocado(s) no disco {model} (SMART ID 05).",
            })
            findings.append({
                "id": "STORAGE_REALLOCATED_SECTORS",
                "category": "storage",
                "title": f"Setores Defeituosos Realocados ({model})",
                "severity": "ALTO",
                "probable_impact": "Degradação da superfície física e redução da vida útil do dispositivo.",
                "technical_evidence": f"Atributo SMART 05 = {realloc} setores remapeados em {model}.",
                "affected_component": f"Disco {d.get('disk_number')} ({model})",
                "confidence": "Fato Observado (100%)",
                "recommendation": "Monitore a evolução histórica. Se o número continuar subindo, substitua a unidade.",
                "action_risk_level": "RISCO MODERADO",
                "needs_more_data": False,
            })

        if uncorr > 0:
            score -= min(40.0, 20.0 + uncorr * 3.0)
            has_critical_disk_issue = True
            deductions.append({
                "points": min(40.0, 20.0 + uncorr * 3.0),
                "reason": f"{uncorr} erro(s) incorrigível(is) de mídia/ECC em {model} (SMART ID 198/187).",
            })

        if cw > 0 or (spare is not None and int(spare) <= int(spare_th)):
            score -= 50.0
            has_critical_disk_issue = True
            deductions.append({
                "points": 50.0,
                "reason": f"Alerta Crítico NVMe ativo (Critical Warning = 0x{cw:02X} / Spare: {spare}% <= Limiar: {spare_th}%).",
            })
            findings.append({
                "id": "STORAGE_NVME_CRITICAL",
                "category": "storage",
                "title": f"Alerta Crítico de Firmware NVMe ({model})",
                "severity": "CRÍTICO",
                "probable_impact": "O controlador NVMe pode travar permanentemente em modo Somente-Leitura.",
                "technical_evidence": f"NVMe Critical Warning = 0x{cw:02X}, Available Spare = {spare}%.",
                "affected_component": f"SSD NVMe ({model})",
                "confidence": "Fato Observado (100%)",
                "recommendation": "Realize backup integral imediato e substitua o SSD.",
                "action_risk_level": "ALTO RISCO (Exige Imagem/Cópia Prévia)",
                "needs_more_data": False,
            })

        if crc > 0 and realloc == 0 and pending == 0 and uncorr == 0:
            score -= min(10.0, 4.0 + (crc * 0.1))
            deductions.append({
                "points": min(10.0, 4.0 + (crc * 0.1)),
                "reason": f"{crc} erro(s) de CRC de interface em {model} (ruído no cabo SATA ou porta USB; não indica setor ruim).",
            })
            findings.append({
                "id": "STORAGE_CRC_INTERFACE",
                "category": "storage",
                "title": f"Erros de Comunicação CRC SATA/USB ({model})",
                "severity": "MÉDIO",
                "probable_impact": "Lentidão intermitente e resets na controladora de armazenamento.",
                "technical_evidence": f"SMART 199 UltraDMA CRC = {crc} erros registrados sem setores defeituosos.",
                "affected_component": f"Interface / Cabo de {model}",
                "confidence": "Forte Suspeita Técnica (85%)",
                "recommendation": "Substitua o cabo SATA de dados ou troque de porta USB na placa-mãe.",
                "action_risk_level": "BAIXO RISCO",
                "needs_more_data": False,
            })

        if wear_pct is not None and float(wear_pct) >= 90.0:
            score -= 15.0
            deductions.append({
                "points": 15.0,
                "reason": f"Desgaste elevado da memória NAND Flash em {model} ({wear_pct}% utilizado).",
            })

    # Avaliação de espaço livre nos volumes (C: e outros)
    for v in hw_volumes:
        free_gb = float(v.get("free_gb") or 0.0)
        used_pct = float(v.get("used_percent") or 0.0)
        drive_name = str(v.get("drive") or "C:")

        if metrics["min_free_space_gb"] is None or free_gb < metrics["min_free_space_gb"]:
            metrics["min_free_space_gb"] = free_gb
            metrics["min_free_space_pct"] = round(100.0 - used_pct, 1)

        if drive_name.upper().startswith("C") and free_gb < 15.0:
            score -= 15.0
            deductions.append({
                "points": 15.0,
                "reason": f"Volume do sistema ({drive_name}) com espaço livre crítico ({free_gb} GB restantes / {used_pct}% ocupado).",
            })
            findings.append({
                "id": "STORAGE_LOW_DISK_SPACE_C",
                "category": "storage",
                "title": f"Espaço Livre Crítico na Unidade de Sistema ({drive_name})",
                "severity": "ALTO",
                "probable_impact": "Falhas em atualizações do Windows, corrupção da memória virtual e lentidão severa.",
                "technical_evidence": f"Apenas {free_gb} GB livres na unidade {drive_name} ({used_pct}% de uso).",
                "affected_component": f"Volume {drive_name}",
                "confidence": "Fato Observado (100%)",
                "recommendation": "Execute a limpeza segura de temporários no AegisPulse e libere ao menos 25 GB na unidade C:.",
                "action_risk_level": "BAIXO RISCO",
                "needs_more_data": False,
            })

    score = max(0.0, min(100.0, score))
    if has_critical_disk_issue:
        status = "critico"
        score = min(39.0, score)
    elif score < 75.0:
        status = "atencao"
    else:
        status = "normal"

    summary_text = (
        f"{len(devs)} disco(s) avaliado(s). "
        f"Setores pendentes: {metrics['total_pending']}, realocados: {metrics['total_reallocated']}, "
        f"erros CRC: {metrics['total_crc']}."
    )
    return {
        "available": True,
        "status": status,
        "score": round(score, 1),
        "deductions": deductions,
        "metrics_observed": metrics,
        "findings": findings,
        "summary": summary_text,
    }


def _eval_ram(hardware: dict[str, Any], gaming_dll: dict[str, Any] | None) -> dict[str, Any]:
    """Avalia capacidade de memória RAM, dual-channel e pressão operacional."""
    total_gb = float(hardware.get("total_ram_gb") or 0.0)
    modules = hardware.get("ram_modules") or []

    if total_gb <= 0:
        return {
            "available": False,
            "status": "desconhecido",
            "score": 0.0,
            "deductions": [],
            "metrics_observed": {},
            "findings": [],
            "summary": "Capacidade total de memória RAM não reportada pelo SMBIOS.",
        }

    score = 100.0
    deductions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    is_dual = len(modules) >= 2
    if gaming_dll:
        rg = gaming_dll.get("gamer_profile", {}).get("ram_gamer", {})
        if "Dual" in str(rg.get("channel_status", "")):
            is_dual = True
        elif "Single" in str(rg.get("channel_status", "")):
            is_dual = False

    metrics = {
        "total_ram_gb": total_gb,
        "modules_count": len(modules),
        "is_dual_channel": is_dual,
    }

    if total_gb < 8.0:
        score -= 30.0
        deductions.append({
            "points": 30.0,
            "reason": f"Capacidade de RAM de {total_gb} GB insuficiente para operação fluida em Windows 10/11 64-bit.",
        })
        findings.append({
            "id": "RAM_CAPACITY_LOW",
            "category": "ram",
            "title": "Capacidade de Memória RAM Insuficiente (< 8 GB)",
            "severity": "ALTO",
            "probable_impact": "Paginação excessiva em disco, travamentos em multitarefa pesada e navegação lenta.",
            "technical_evidence": f"{total_gb} GB instalados em {len(modules)} módulo(s).",
            "affected_component": "Memória RAM",
            "confidence": "Fato Observado (100%)",
            "recommendation": "Realizar upgrade para no mínimo 16 GB DDR4/DDR5.",
            "action_risk_level": "BAIXO RISCO",
            "needs_more_data": False,
        })
    elif total_gb < 16.0:
        score -= 10.0
        deductions.append({
            "points": 10.0,
            "reason": f"Capacidade de {total_gb} GB atende uso básico, mas limita multitarefa pesada e jogos modernos.",
        })

    if not is_dual and len(modules) == 1 and total_gb >= 8.0:
        score -= 8.0
        deductions.append({
            "points": 8.0,
            "reason": "Memória operando em Single-Channel (1 módulo instalado), reduzindo a largura de banda da CPU/iGPU.",
        })
        findings.append({
            "id": "RAM_SINGLE_CHANNEL",
            "category": "ram",
            "title": "Memória RAM em Single-Channel (Largura de Banda Reduzida)",
            "severity": "MÉDIO",
            "probable_impact": "Perda de 15% a 25% de desempenho em processamento gráfico integrado e compactação.",
            "technical_evidence": f"Apenas 1 módulo de {total_gb} GB instalado.",
            "affected_component": "Módulos de Memória",
            "confidence": "Forte Suspeita Técnica (85%)",
            "recommendation": "Instalar um segundo módulo idêntico para ativar Dual-Channel (128-bit).",
            "action_risk_level": "BAIXO RISCO",
            "needs_more_data": False,
        })

    score = max(0.0, min(100.0, score))
    status = "critico" if score < 40.0 else ("atencao" if score < 75.0 else "normal")
    return {
        "available": True,
        "status": status,
        "score": round(score, 1),
        "deductions": deductions,
        "metrics_observed": metrics,
        "findings": findings,
        "summary": f"{total_gb} GB instalados ({'Dual-Channel' if is_dual else 'Single-Channel'} com {len(modules)} módulo(s)).",
    }


def _eval_cpu(hardware: dict[str, Any]) -> dict[str, Any]:
    """Avalia o processador, contagem de núcleos/threads, clock e nível de carga."""
    cpus = hardware.get("cpus") or []
    if not cpus:
        return {
            "available": False,
            "status": "desconhecido",
            "score": 0.0,
            "deductions": [],
            "metrics_observed": {},
            "findings": [],
            "summary": "Processador não reportado pelo CIM/WMI.",
        }

    c0 = cpus[0]
    cores = int(c0.get("cores") or 0)
    threads = int(c0.get("threads") or 0)
    load = float(c0.get("load_percent") or 0.0)
    cpu_name = str(c0.get("name") or "Processador")

    score = 100.0
    deductions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    metrics = {
        "cpu_name": cpu_name,
        "cores": cores,
        "threads": threads,
        "load_percent": load,
    }

    if cores > 0 and cores < 4:
        score -= 20.0
        deductions.append({
            "points": 20.0,
            "reason": f"Processador com apenas {cores} núcleos físicos ({threads} threads), vulnerável a saturação sob Windows 11.",
        })
        findings.append({
            "id": "CPU_LOW_CORE_COUNT",
            "category": "cpu",
            "title": f"Processador com Baixo Número de Núcleos ({cores} núcleos)",
            "severity": "MÉDIO",
            "probable_impact": "Engasgos e lentidão quando navegadores e processos de segundo plano concorrem por tempo de CPU.",
            "technical_evidence": f"{cpu_name} com {cores} núcleos / {threads} threads.",
            "affected_component": "Processador",
            "confidence": "Fato Observado (100%)",
            "recommendation": "Consultar a aba de Compatibilidade & Setup para verificar opções de upgrade suportadas pela placa-mãe.",
            "action_risk_level": "BAIXO RISCO",
            "needs_more_data": False,
        })

    if load >= 95.0:
        score -= 30.0
        deductions.append({
            "points": 30.0,
            "reason": f"Utilização de CPU extremamente alta no momento da coleta ({load}%).",
        })
        findings.append({
            "id": "CPU_HIGH_LOAD",
            "category": "cpu",
            "title": f"Sobrecarga Severa de CPU ({load}%)",
            "severity": "ALTO",
            "probable_impact": "Queda imediata de resposta do sistema e aumento de temperatura.",
            "technical_evidence": f"Carga de processamento registrada em {load}%.",
            "affected_component": "Processador",
            "confidence": "Fato Observado (100%)",
            "recommendation": "Identificar no Gerenciador de Tarefas se há processos em loop ou mineradores em segundo plano.",
            "action_risk_level": "BAIXO RISCO",
            "needs_more_data": True,
        })
    elif load >= 80.0:
        score -= 12.0
        deductions.append({
            "points": 12.0,
            "reason": f"Carga de processamento elevada ({load}%).",
        })

    score = max(0.0, min(100.0, score))
    status = "critico" if score < 40.0 else ("atencao" if score < 75.0 else "normal")
    return {
        "available": True,
        "status": status,
        "score": round(score, 1),
        "deductions": deductions,
        "metrics_observed": metrics,
        "findings": findings,
        "summary": f"{cpu_name} ({cores}C/{threads}T) operando em {load}% de carga.",
    }


def _eval_thermals(hardware: dict[str, Any], storage_suite: dict[str, Any]) -> dict[str, Any]:
    """Avalia temperaturas de CPU, GPU e Discos com limites específicos por componente."""
    temps = hardware.get("temperatures") or {}
    cpu_t = temps.get("cpu_temp_c")
    gpu_t = temps.get("gpu_temp_c")

    disk_temps: list[tuple[str, float]] = []
    for d in (storage_suite.get("devices") or []):
        dt = d.get("smart_summary", {}).get("temperature_c")
        if dt is not None and float(dt) > 0:
            disk_temps.append((d.get("model", "Disco"), float(dt)))

    if cpu_t is None and gpu_t is None and not disk_temps:
        return {
            "available": False,
            "status": "desconhecido",
            "score": 0.0,
            "deductions": [],
            "metrics_observed": {},
            "findings": [],
            "summary": "Sensores térmicos não disponíveis ou não reportados por este equipamento.",
        }

    score = 100.0
    deductions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    has_critical_thermal = False

    metrics: dict[str, Any] = {
        "cpu_temp_c": cpu_t,
        "cpu_temp_source": temps.get("cpu_temp_source"),
        "gpu_temp_c": gpu_t,
        "max_disk_temp_c": max([t for _, t in disk_temps], default=None),
    }

    # Limites para CPU (Desktop/Workstation): Normal <75°C, Alerta 75–84°C, Crítico >=85°C
    if cpu_t is not None:
        ct = float(cpu_t)
        if ct >= 88.0:
            score -= 40.0
            has_critical_thermal = True
            deductions.append({
                "points": 40.0,
                "reason": f"Temperatura crítica da CPU ({ct}°C >= 88°C) — risco iminente de Thermal Throttling e desligamento por proteção térmica.",
            })
            findings.append({
                "id": "THERMAL_CPU_CRITICAL",
                "category": "thermals",
                "title": f"Temperatura Crítica no Processador ({ct}°C)",
                "severity": "CRÍTICO",
                "probable_impact": "Thermal Throttling severo (perda drástica de clock) e risco de degradação do silício.",
                "technical_evidence": f"Sensor de CPU registrou {ct}°C ({temps.get('cpu_temp_source')}).",
                "affected_component": "Refrigeração da CPU (Cooler/Pasta Térmica)",
                "confidence": "Fato Observado (100%)",
                "recommendation": "Verificar se o ventilador do cooler gira normalmente, limpar poeira e trocar a pasta térmica.",
                "action_risk_level": "RISCO MODERADO",
                "needs_more_data": False,
            })
        elif ct >= 78.0:
            score -= 15.0
            deductions.append({
                "points": 15.0,
                "reason": f"Temperatura elevada no Processador ({ct}°C).",
            })
            findings.append({
                "id": "THERMAL_CPU_WARNING",
                "category": "thermals",
                "title": f"Temperatura Elevada no Processador ({ct}°C)",
                "severity": "MÉDIO",
                "probable_impact": "Aumento do ruído da ventoinha e redução de margem térmica.",
                "technical_evidence": f"Sensor de CPU registrou {ct}°C.",
                "affected_component": "Cooler da CPU",
                "confidence": "Fato Observado (100%)",
                "recommendation": "Inspecionar o fluxo de ar do gabinete e desobstruir as entradas de ar.",
                "action_risk_level": "BAIXO RISCO",
                "needs_more_data": False,
            })

    # Limites para GPU: Normal <78°C, Alerta 78–84°C, Crítico >=85°C
    if gpu_t is not None:
        gt = float(gpu_t)
        if gt >= 86.0:
            score -= 25.0
            deductions.append({
                "points": 25.0,
                "reason": f"Temperatura crítica na Placa de Vídeo ({gt}°C >= 86°C).",
            })
        elif gt >= 79.0:
            score -= 10.0
            deductions.append({
                "points": 10.0,
                "reason": f"Temperatura elevada na Placa de Vídeo ({gt}°C).",
            })

    # Limites para Discos (NVMe / SATA / HDD): Alerta >=65°C para NVMe, >=55°C para HDD
    for d_name, dt in disk_temps:
        if dt >= 70.0:
            score -= 20.0
            has_critical_thermal = True
            deductions.append({
                "points": 20.0,
                "reason": f"Temperatura crítica de armazenamento no disco {d_name} ({dt}°C >= 70°C).",
            })
            findings.append({
                "id": "THERMAL_STORAGE_CRITICAL",
                "category": "thermals",
                "title": f"Superaquecimento em Unidade de Armazenamento ({d_name}: {dt}°C)",
                "severity": "ALTO",
                "probable_impact": "Degradação acelerada da memória Flash NAND e perda temporária de I/O por proteção térmica.",
                "technical_evidence": f"Sensor SMART registrou {dt}°C em {d_name}.",
                "affected_component": f"Disco {d_name}",
                "confidence": "Fato Observado (100%)",
                "recommendation": "Instalar dissipador térmico M.2 ou melhorar o fluxo de ar sobre o compartimento de discos.",
                "action_risk_level": "BAIXO RISCO",
                "needs_more_data": False,
            })
        elif dt >= 58.0:
            score -= 8.0
            deductions.append({
                "points": 8.0,
                "reason": f"Temperatura de armazenamento elevada no disco {d_name} ({dt}°C).",
            })

    score = max(0.0, min(100.0, score))
    if has_critical_thermal:
        status = "critico"
        score = min(39.0, score)
    elif score < 75.0:
        status = "atencao"
    else:
        status = "normal"

    summary_text = (
        f"CPU: {cpu_t or 'N/D'}°C | GPU: {gpu_t or 'N/D'}°C | "
        f"Disco Pico: {metrics['max_disk_temp_c'] or 'N/D'}°C."
    )
    return {
        "available": True,
        "status": status,
        "score": round(score, 1),
        "deductions": deductions,
        "metrics_observed": metrics,
        "findings": findings,
        "summary": summary_text,
    }


def _eval_os_stability(os_info: dict[str, Any], storage_suite: dict[str, Any]) -> dict[str, Any]:
    """Avalia estabilidade do Windows, uptime excessivo e eventos críticos do sistema."""
    os_name = os_info.get("os_name")
    if not os_name:
        return {
            "available": False,
            "status": "desconhecido",
            "score": 0.0,
            "deductions": [],
            "metrics_observed": {},
            "findings": [],
            "summary": "Informações do Sistema Operacional não coletadas.",
        }

    score = 100.0
    deductions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    uptime_h = float(os_info.get("uptime_hours") or 0.0)
    sys_events = storage_suite.get("system_disk_events") or []

    metrics = {
        "os_name": os_name,
        "display_version": os_info.get("display_version"),
        "full_build": os_info.get("full_build"),
        "uptime_hours": uptime_h,
        "system_disk_events_count": len(sys_events),
    }

    # Uptime maior que 30 dias (720 horas) indica falta de reinicialização para patches/estabilidade
    if uptime_h >= 720.0:
        score -= 15.0
        deductions.append({
            "points": 15.0,
            "reason": f"Uptime contínuo de {round(uptime_h / 24, 1)} dias sem reinicialização (risco de vazamento de memória e patches pendentes).",
        })
        findings.append({
            "id": "OS_HIGH_UPTIME",
            "category": "os_stability",
            "title": f"Tempo Excessivo sem Reiniciar o Sistema ({round(uptime_h / 24)} dias)",
            "severity": "MÉDIO",
            "probable_impact": "Instabilidade acumulada de drivers, vazamento de recursos e atualizações paradas.",
            "technical_evidence": f"Último boot registrado há {uptime_h} horas ({os_info.get('last_boot')}).",
            "affected_component": "Sistema Operacional",
            "confidence": "Fato Observado (100%)",
            "recommendation": "Reiniciar o computador para aplicar atualizações e liberar pools de memória.",
            "action_risk_level": "BAIXO RISCO",
            "needs_more_data": False,
        })
    elif uptime_h >= 360.0:
        score -= 6.0
        deductions.append({
            "points": 6.0,
            "reason": f"Computador ligado há {round(uptime_h / 24, 1)} dias sem reinicialização.",
        })

    # Eventos de barramento / I/O críticos (51, 129, 153, 157)
    io_events = [e for e in sys_events if int(e.get("Id", 0)) in (51, 129, 153, 157)]
    if len(io_events) >= 10:
        score -= 25.0
        deductions.append({
            "points": 25.0,
            "reason": f"{len(io_events)} evento(s) de erro de paginação / reset de barramento registrados no Log de Eventos do Windows.",
        })
        findings.append({
            "id": "OS_CRITICAL_IO_EVENTS",
            "category": "os_stability",
            "title": "Múltiplos Eventos de Falha de Paginação e Reset de Disco",
            "severity": "ALTO",
            "probable_impact": "Congelamentos temporários do sistema e risco de corrupção do arquivo de paginação (pagefile.sys).",
            "technical_evidence": f"{len(io_events)} ocorrências de Event ID 51/129/153 no Log System.",
            "affected_component": "Subsistema de E/S do Windows",
            "confidence": "Fato Observado (100%)",
            "recommendation": "Revisar conexões físicas de armazenamento e atualizar drivers da controladora SATA/NVMe.",
            "action_risk_level": "RISCO MODERADO",
            "needs_more_data": False,
        })
    elif len(io_events) > 0:
        score -= min(12.0, len(io_events) * 2.0)
        deductions.append({
            "points": min(12.0, len(io_events) * 2.0),
            "reason": f"{len(io_events)} alerta(s) de E/S de disco no Log de Eventos.",
        })

    score = max(0.0, min(100.0, score))
    status = "critico" if score < 40.0 else ("atencao" if score < 75.0 else "normal")
    return {
        "available": True,
        "status": status,
        "score": round(score, 1),
        "deductions": deductions,
        "metrics_observed": metrics,
        "findings": findings,
        "summary": f"{os_name} Build {os_info.get('full_build')} (Uptime: {round(uptime_h / 24, 1)} dias).",
    }


def _eval_drivers_devices(drivers_bios: dict[str, Any]) -> dict[str, Any]:
    """Avalia integridade de dispositivos PnP, drivers problemáticos e idade da BIOS."""
    bios = drivers_bios.get("bios") or {}
    total_drivers = int(drivers_bios.get("total_drivers") or 0)
    pnp_errors = drivers_bios.get("pnp_errors") or []
    outdated_count = int(drivers_bios.get("outdated_drivers_count") or 0)

    if total_drivers <= 0 and not bios.get("smbios_version"):
        return {
            "available": False,
            "status": "desconhecido",
            "score": 0.0,
            "deductions": [],
            "metrics_observed": {},
            "findings": [],
            "summary": "Inventário de drivers e BIOS não disponível.",
        }

    score = 100.0
    deductions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    metrics = {
        "total_drivers": total_drivers,
        "outdated_drivers_count": outdated_count,
        "pnp_errors_count": len(pnp_errors),
        "bios_version": bios.get("smbios_version"),
        "bios_age_months": bios.get("age_months"),
        "bios_needs_review": bios.get("needs_review"),
    }

    if pnp_errors:
        score -= min(40.0, 15.0 + len(pnp_errors) * 5.0)
        deductions.append({
            "points": min(40.0, 15.0 + len(pnp_errors) * 5.0),
            "reason": f"{len(pnp_errors)} dispositivo(s) com código de erro ativo no Gerenciador de Dispositivos.",
        })
        for pnp in pnp_errors[:3]:
            findings.append({
                "id": "DRIVER_PNP_ERROR",
                "category": "drivers_devices",
                "title": f"Dispositivo com Falha de Driver ({pnp.get('device_name')})",
                "severity": "ALTO",
                "probable_impact": "Hardware inoperante ou causando interrupções de sistema.",
                "technical_evidence": f"Status: {pnp.get('status')} | Código de Erro: {pnp.get('error_code')}.",
                "affected_component": str(pnp.get("device_name")),
                "confidence": "Fato Observado (100%)",
                "recommendation": "Atualizar ou reinstalar o driver oficial correspondente via Windows Update ou catálogo do fabricante.",
                "action_risk_level": "BAIXO RISCO",
                "needs_more_data": False,
            })

    if bios.get("needs_review"):
        score -= 10.0
        deductions.append({
            "points": 10.0,
            "reason": f"Firmware BIOS/UEFI com mais de 24 meses de idade ({bios.get('age_months')} meses — Versão {bios.get('smbios_version')}).",
        })
        findings.append({
            "id": "BIOS_NEEDS_REVIEW",
            "category": "drivers_devices",
            "title": "Firmware BIOS/UEFI Antigo (Mais de 2 Anos)",
            "severity": "MÉDIO",
            "probable_impact": "Possível vulnerabilidade a falhas de segurança de microcódigo (Spectre/Meltdown) e incompatibilidade com hardware recente.",
            "technical_evidence": f"Data de Lançamento: {bios.get('release_date')} ({bios.get('age_months')} meses atrás).",
            "affected_component": "Firmware da Placa-Mãe (BIOS)",
            "confidence": "Fato Observado (100%)",
            "recommendation": "Consultar a página de suporte oficial do fabricante da placa-mãe e avaliar atualização de BIOS.",
            "action_risk_level": "RISCO MODERADO",
            "needs_more_data": False,
        })

    if outdated_count > 25:
        score -= 8.0
        deductions.append({
            "points": 8.0,
            "reason": f"Elevada quantidade de drivers antigos ({outdated_count} controladores com mais de 36 meses).",
        })

    score = max(0.0, min(100.0, score))
    status = "critico" if score < 40.0 else ("atencao" if score < 75.0 else "normal")
    return {
        "available": True,
        "status": status,
        "score": round(score, 1),
        "deductions": deductions,
        "metrics_observed": metrics,
        "findings": findings,
        "summary": f"{total_drivers} drivers auditados ({len(pnp_errors)} erros PnP | BIOS {bios.get('smbios_version', 'N/D')}).",
    }


def _eval_performance(software: dict[str, Any], gaming_dll: dict[str, Any] | None) -> dict[str, Any]:
    """Avalia integridade de DLLs, runtimes de jogos, programas obsoletos e bloatwares."""
    gp = (gaming_dll or {}).get("gamer_profile") or {}
    missing_dlls = int((gaming_dll or {}).get("missing_dlls_count") or 0)
    outdated_sw = int(software.get("outdated_count") or 0)
    bloatwares = int(software.get("bloatware_count") or 0)

    score = 100.0
    deductions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    metrics = {
        "missing_dlls_count": missing_dlls,
        "outdated_software_count": outdated_sw,
        "bloatware_count": bloatwares,
        "gamer_tier": gp.get("gamer_tier"),
    }

    if missing_dlls > 0:
        score -= min(25.0, missing_dlls * 6.0)
        deductions.append({
            "points": min(25.0, missing_dlls * 6.0),
            "reason": f"{missing_dlls} biblioteca(s) DLL crítica(s) de Visual C++ ou DirectX ausente(s) no System32/SysWOW64.",
        })
        findings.append({
            "id": "PERF_MISSING_DLLS",
            "category": "performance",
            "title": f"Bibliotecas DLL de Jogos e Runtimes Ausentes ({missing_dlls} DLLs)",
            "severity": "MÉDIO",
            "probable_impact": "Erros 0xc000007b e falha ao abrir jogos e softwares que exigem Visual C++.",
            "technical_evidence": f"{missing_dlls} arquivo(s) não encontrado(s) nos diretórios do sistema.",
            "affected_component": "Runtimes do Windows (VC++ / DirectX)",
            "confidence": "Fato Observado (100%)",
            "recommendation": "Utilizar a ferramenta de reparo 1-clique na aba PC Gamer & DLLs do AegisPulse.",
            "action_risk_level": "BAIXO RISCO",
            "needs_more_data": False,
        })

    if outdated_sw > 5:
        score -= min(15.0, 5.0 + (outdated_sw * 0.8))
        deductions.append({
            "points": min(15.0, 5.0 + (outdated_sw * 0.8)),
            "reason": f"{outdated_sw} programa(s) com atualizações de segurança pendentes detectados pelo Winget.",
        })
        findings.append({
            "id": "PERF_OUTDATED_SOFTWARE",
            "category": "performance",
            "title": f"Softwares com Atualização de Segurança Pendente ({outdated_sw} apps)",
            "severity": "MÉDIO",
            "probable_impact": "Vulnerabilidade a falhas conhecidas e perda de correções de estabilidade.",
            "technical_evidence": f"Winget reportou {outdated_sw} pacote(s) desatualizado(s).",
            "affected_component": "Aplicativos Instalados",
            "confidence": "Fato Observado (100%)",
            "recommendation": "Atualizar os programas em lote na aba Softwares & Debloat do AegisPulse.",
            "action_risk_level": "BAIXO RISCO",
            "needs_more_data": False,
        })

    if bloatwares > 8:
        score -= 8.0
        deductions.append({
            "points": 8.0,
            "reason": f"{bloatwares} aplicativos pré-instalados (Bloatware) consumindo recursos em segundo plano.",
        })

    score = max(0.0, min(100.0, score))
    status = "critico" if score < 40.0 else ("atencao" if score < 75.0 else "normal")
    return {
        "available": True,
        "status": status,
        "score": round(score, 1),
        "deductions": deductions,
        "metrics_observed": metrics,
        "findings": findings,
        "summary": f"{missing_dlls} DLLs ausentes | {outdated_sw} apps obsoletos | {bloatwares} bloatwares.",
    }


def _eval_security(os_info: dict[str, Any]) -> dict[str, Any]:
    """Avalia indicadores verificáveis de segurança (Antivírus, Proteção em Tempo Real, Assinaturas, TPM)."""
    sec = os_info.get("security") or {}
    if not sec:
        return {
            "available": False,
            "status": "desconhecido",
            "score": 0.0,
            "deductions": [],
            "metrics_observed": {},
            "findings": [],
            "summary": "Métricas de segurança não reportadas pelo SecurityCenter2.",
        }

    score = 100.0
    deductions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    av_enabled = bool(sec.get("antivirus_enabled"))
    rt_enabled = bool(sec.get("realtime_protection"))
    sig_age = int(sec.get("signature_age_days") or 0)
    tpm_present = bool(sec.get("tpm_present"))
    tpm_ready = bool(sec.get("tpm_ready"))

    metrics = {
        "antivirus_enabled": av_enabled,
        "realtime_protection": rt_enabled,
        "signature_age_days": sig_age,
        "tpm_present": tpm_present,
        "tpm_ready": tpm_ready,
    }

    if not av_enabled or not rt_enabled:
        score -= 40.0
        deductions.append({
            "points": 40.0,
            "reason": "Antivírus ou Proteção em Tempo Real do Windows Defender desativada.",
        })
        findings.append({
            "id": "SEC_ANTIVIRUS_DISABLED",
            "category": "security",
            "title": "Proteção Antivírus / Tempo Real Desativada",
            "severity": "CRÍTICO",
            "probable_impact": "Exposição direta a Malwares, Ransomwares e ameaças ativas da rede.",
            "technical_evidence": f"antivirus_enabled={av_enabled}, realtime_protection={rt_enabled}.",
            "affected_component": "Segurança do Windows",
            "confidence": "Fato Observado (100%)",
            "recommendation": "Ativar a Proteção em Tempo Real nas Configurações de Segurança do Windows.",
            "action_risk_level": "BAIXO RISCO",
            "needs_more_data": False,
        })

    if sig_age > 7:
        score -= 15.0
        deductions.append({
            "points": 15.0,
            "reason": f"Definições de antivírus desatualizadas há {sig_age} dias.",
        })
        findings.append({
            "id": "SEC_SIGNATURES_OUTDATED",
            "category": "security",
            "title": f"Assinaturas de Antivírus Desatualizadas ({sig_age} dias)",
            "severity": "ALTO",
            "probable_impact": "Incapacidade de detectar novas variantes de ameaças recentes.",
            "technical_evidence": f"signature_age_days = {sig_age} dias.",
            "affected_component": "Windows Defender",
            "confidence": "Fato Observado (100%)",
            "recommendation": "Forçar atualização de definições pelo Windows Update.",
            "action_risk_level": "BAIXO RISCO",
            "needs_more_data": False,
        })

    if not tpm_present or not tpm_ready:
        score -= 10.0
        deductions.append({
            "points": 10.0,
            "reason": "Módulo de Segurança TPM 2.0 não detectado ou não inicializado.",
        })

    score = max(0.0, min(100.0, score))
    status = "critico" if score < 40.0 else ("atencao" if score < 75.0 else "normal")
    return {
        "available": True,
        "status": status,
        "score": round(score, 1),
        "deductions": deductions,
        "metrics_observed": metrics,
        "findings": findings,
        "summary": f"Antivírus: {'Ativo' if av_enabled else 'Desativado'} (Defasagem: {sig_age}d) | TPM 2.0: {'OK' if (tpm_present and tpm_ready) else 'Atenção'}.",
    }


def compute_health_score(snapshot: dict[str, Any], base_dir: Path | None = None) -> dict[str, Any]:
    """
    Motor Central de Avaliação Determinística Health Score v4.5:
    - Processa o snapshot do sistema através dos 8 avaliadores especializados.
    - Calcula a pontuação e cobertura estritamente com base nos dados disponíveis.
    - Aplica trava de não-mascaramento de falha crítica quando há risco real de perda de dados.
    - Gera lista priorizada de achados acionáveis e trilha de auditoria completa.
    """
    hw = snapshot.get("hardware") or {}
    os_info = snapshot.get("os") or {}
    drv = snapshot.get("drivers_bios") or {}
    sw = snapshot.get("software") or {}
    gaming = snapshot.get("gaming") or {}
    st_suite = snapshot.get("storage_suite") or {}

    machine_id = get_machine_identifier(hw)
    hostname = str(hw.get("hostname") or "COMPUTADOR")
    evaluated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Avaliação das 8 categorias
    categories: dict[str, dict[str, Any]] = {
        "storage": _eval_storage(st_suite, hw.get("volumes") or []),
        "ram": _eval_ram(hw, gaming),
        "cpu": _eval_cpu(hw),
        "thermals": _eval_thermals(hw, st_suite),
        "os_stability": _eval_os_stability(os_info, st_suite),
        "drivers_devices": _eval_drivers_devices(drv),
        "performance": _eval_performance(sw, gaming),
        "security": _eval_security(os_info),
    }

    # Consolidação de achados, deduções e cálculo de cobertura
    all_findings: list[dict[str, Any]] = []
    all_deductions: list[dict[str, Any]] = []
    available_weights_sum = 0.0
    weighted_score_sum = 0.0
    coverage_count = 0
    total_categories = len(categories)
    has_critical_issue = False

    for cat_key, cat_eval in categories.items():
        base_w = BASE_CATEGORY_WEIGHTS.get(cat_key, 10.0)
        cat_eval["category_key"] = cat_key
        cat_eval["category_title"] = CATEGORY_TITLES.get(cat_key, cat_key.capitalize())
        cat_eval["nominal_weight_pct"] = base_w

        if cat_eval.get("available"):
            coverage_count += 1
            available_weights_sum += base_w
            weighted_score_sum += cat_eval["score"] * base_w

        if cat_eval.get("status") == "critico":
            has_critical_issue = True

        for f in cat_eval.get("findings") or []:
            all_findings.append(f)
            if f.get("severity") == "CRÍTICO":
                has_critical_issue = True

        for d in cat_eval.get("deductions") or []:
            all_deductions.append({
                "category": cat_key,
                "category_title": cat_eval["category_title"],
                **d,
            })

    # Normalização de peso para as categorias disponíveis
    for cat_key, cat_eval in categories.items():
        base_w = BASE_CATEGORY_WEIGHTS.get(cat_key, 10.0)
        if cat_eval.get("available") and available_weights_sum > 0:
            cat_eval["effective_weight_pct"] = round((base_w / available_weights_sum) * 100.0, 1)
        else:
            cat_eval["effective_weight_pct"] = 0.0

    if available_weights_sum > 0:
        raw_overall = weighted_score_sum / available_weights_sum
    else:
        raw_overall = 0.0

    coverage_pct = round((coverage_count / total_categories) * 100.0, 1) if total_categories > 0 else 0.0

    # Aplicação da Trava de Não-Mascaramento de Falha Crítica
    critical_cap_applied = False
    final_score = raw_overall

    if has_critical_issue and final_score >= 60.0:
        critical_cap_applied = True
        # Limita a 59.0 (faixa Ruim) para garantir que problemas graves nunca sejam ocultados por uma média alta
        final_score = 59.0

    final_score = round(max(0.0, min(100.0, final_score)), 1)
    class_label, class_color, class_badge = classify_score(final_score)

    # Ordenação de achados por severidade técnica (CRÍTICO > ALTO > MÉDIO > BAIXO)
    severity_order = {"CRÍTICO": 0, "ALTO": 1, "MÉDIO": 2, "BAIXO": 3, "INFORMATIVO": 4}
    all_findings.sort(key=lambda x: severity_order.get(x.get("severity", "BAIXO"), 5))

    # Montagem da trilha de auditoria auditável
    audit_trail = {
        "base_score": 100.0,
        "raw_weighted_score": round(raw_overall, 1),
        "final_score": final_score,
        "critical_cap_applied": critical_cap_applied,
        "critical_cap_reason": "Pontuação limitada em 59.0 (Ruim) devido à presença de falha(s) crítica(s) de hardware ou integridade." if critical_cap_applied else None,
        "coverage_statement": f"Avaliação baseada em {coverage_count} de {total_categories} categorias disponíveis ({coverage_pct}% de cobertura).",
        "total_deductions_points": round(sum(d.get("points", 0.0) for d in all_deductions), 1),
        "deductions_detail": all_deductions,
        "unavailable_categories": [
            {"key": k, "title": CATEGORY_TITLES.get(k, k), "reason": c.get("summary")}
            for k, c in categories.items() if not c.get("available")
        ],
    }

    result = {
        "machine_uuid": machine_id,
        "hostname": hostname,
        "evaluated_at": evaluated_at,
        "algorithm_version": ALGORITHM_VERSION,
        "overall_score": final_score,
        "raw_overall_score": round(raw_overall, 1),
        "classification": class_label,
        "classification_color": class_color,
        "classification_badge": class_badge,
        "has_critical_issue": has_critical_issue,
        "critical_cap_applied": critical_cap_applied,
        "coverage": {
            "count": coverage_count,
            "total": total_categories,
            "percent": coverage_pct,
            "label": f"{coverage_count} de {total_categories} categorias disponíveis",
        },
        "categories": categories,
        "prioritized_findings": all_findings,
        "audit_trail": audit_trail,
    }

    # Persistência no SQLite se base_dir for fornecido
    if base_dir:
        try:
            init_health_score_db(base_dir)
            save_health_score_evaluation(base_dir, result)
        except Exception:
            pass

    return result


def save_health_score_evaluation(base_dir: Path, result: dict[str, Any]) -> int:
    """Grava o registro de avaliação no banco de dados SQLite."""
    init_health_score_db(base_dir)
    db_path = get_storage_db_path(base_dir)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO health_score_evaluations (
                machine_uuid, hostname, evaluated_at, algorithm_version,
                overall_score, classification, coverage_count, coverage_total,
                coverage_percent, has_critical_issue, critical_cap_applied,
                categories_json, findings_json, audit_breakdown_json, raw_metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["machine_uuid"],
                result["hostname"],
                result["evaluated_at"],
                result["algorithm_version"],
                result["overall_score"],
                result["classification"],
                result["coverage"]["count"],
                result["coverage"]["total"],
                result["coverage"]["percent"],
                1 if result["has_critical_issue"] else 0,
                1 if result["critical_cap_applied"] else 0,
                json.dumps(result["categories"], ensure_ascii=False),
                json.dumps(result["prioritized_findings"], ensure_ascii=False),
                json.dumps(result["audit_trail"], ensure_ascii=False),
                json.dumps({k: v.get("metrics_observed") for k, v in result["categories"].items()}, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0
    finally:
        conn.close()


def get_latest_health_score(base_dir: Path, machine_uuid: str | None = None) -> dict[str, Any] | None:
    """Recupera a avaliação mais recente do SQLite."""
    init_health_score_db(base_dir)
    db_path = get_storage_db_path(base_dir)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        if machine_uuid:
            row = conn.execute(
                "SELECT * FROM health_score_evaluations WHERE machine_uuid = ? ORDER BY id DESC LIMIT 1",
                (machine_uuid,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM health_score_evaluations ORDER BY id DESC LIMIT 1"
            ).fetchone()

        if not row:
            return None

        return _hydrate_evaluation_row(dict(row))
    finally:
        conn.close()


def list_health_score_history(
    base_dir: Path,
    machine_uuid: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Retorna histórico paginado de avaliações com dados para série temporal."""
    init_health_score_db(base_dir)
    db_path = get_storage_db_path(base_dir)
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        where_clause = "WHERE machine_uuid = ?" if machine_uuid else ""
        params: list[Any] = [machine_uuid] if machine_uuid else []

        total = conn.execute(f"SELECT COUNT(*) FROM health_score_evaluations {where_clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM health_score_evaluations {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        items = [_hydrate_evaluation_row(dict(r)) for r in rows]

        # Série cronológica simplificada para gráficos SVG no frontend
        chart_series = [
            {
                "id": it["id"],
                "date": it["evaluated_at"],
                "score": it["overall_score"],
                "classification": it["classification"],
                "coverage_pct": it["coverage"]["percent"],
                "has_critical": it["has_critical_issue"],
            }
            for it in reversed(items)
        ]

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items,
            "chart_series": chart_series,
        }
    finally:
        conn.close()


def compare_health_evaluations(
    eval_older: dict[str, Any],
    eval_newer: dict[str, Any],
) -> dict[str, Any]:
    """
    Compara duas avaliações (mais antiga vs mais recente), identificando:
    - Variação da nota global e por categoria
    - Variação de cobertura (evitando conclusões falsas se o conjunto de métricas mudou)
    - Problemas novos vs problemas resolvidos
    - Mudanças métricas específicas
    - Interpretação da tendência técnica
    """
    s_old = float(eval_older.get("overall_score") or 0.0)
    s_new = float(eval_newer.get("overall_score") or 0.0)
    delta_score = round(s_new - s_old, 1)

    cov_old = eval_older.get("coverage", {}).get("percent") or 0.0
    cov_new = eval_newer.get("coverage", {}).get("percent") or 0.0
    delta_cov = round(cov_new - cov_old, 1)

    # Comparação por categoria
    cats_old = eval_older.get("categories") or {}
    cats_new = eval_newer.get("categories") or {}
    cat_deltas: dict[str, dict[str, Any]] = {}

    for k in set(cats_old.keys()).union(cats_new.keys()):
        c_o = cats_old.get(k) or {}
        c_n = cats_new.get(k) or {}
        sc_o = c_o.get("score")
        sc_n = c_n.get("score")
        av_o = c_o.get("available", False)
        av_n = c_n.get("available", False)

        cat_deltas[k] = {
            "title": CATEGORY_TITLES.get(k, k.capitalize()),
            "score_older": sc_o,
            "score_newer": sc_n,
            "delta": round(sc_n - sc_o, 1) if (sc_o is not None and sc_n is not None) else None,
            "status_older": c_o.get("status", "desconhecido"),
            "status_newer": c_n.get("status", "desconhecido"),
            "availability_changed": av_o != av_n,
        }

    # Problemas novos vs resolvidos
    findings_old = {f.get("id"): f for f in eval_older.get("prioritized_findings") or [] if f.get("id")}
    findings_new = {f.get("id"): f for f in eval_newer.get("prioritized_findings") or [] if f.get("id")}

    new_ids = set(findings_new.keys()) - set(findings_old.keys())
    resolved_ids = set(findings_old.keys()) - set(findings_new.keys())
    persisting_ids = set(findings_new.keys()).intersection(set(findings_old.keys()))

    new_findings = [findings_new[fid] for fid in new_ids]
    resolved_findings = [findings_old[fid] for fid in resolved_ids]
    persisting_findings = [findings_new[fid] for fid in persisting_ids]

    # Interpretação técnica da tendência
    if abs(delta_cov) >= 20.0:
        trend_label = "Variação Explicada por Mudança de Cobertura"
        trend_summary = (
            f"A cobertura de métricas variou {delta_cov}% entre as duas coletas. "
            "A diferença na nota reflete disponibilidade de sensores e não necessariamente alteração no hardware."
        )
    elif delta_score >= 10.0 or (resolved_findings and not new_findings):
        trend_label = "Melhora Real Comprovada"
        trend_summary = (
            f"A pontuação subiu +{delta_score} pontos com resolução de {len(resolved_findings)} problema(s)."
        )
    elif delta_score <= -10.0 or (new_findings and any(f.get("severity") in ("CRÍTICO", "ALTO") for f in new_findings)):
        trend_label = "Degradação Ativa Detectada"
        trend_summary = (
            f"A pontuação caiu {delta_score} pontos com surgimento de {len(new_findings)} novo(s) alerta(s)."
        )
    else:
        trend_label = "Estável"
        trend_summary = f"A condição geral permaneceu estável (variação de {delta_score} pontos)."

    return {
        "older_id": eval_older.get("id"),
        "older_date": eval_older.get("evaluated_at"),
        "newer_id": eval_newer.get("id"),
        "newer_date": eval_newer.get("evaluated_at"),
        "score_delta": delta_score,
        "coverage_delta": delta_cov,
        "trend_label": trend_label,
        "trend_summary": trend_summary,
        "category_deltas": cat_deltas,
        "new_findings": new_findings,
        "resolved_findings": resolved_findings,
        "persisting_findings": persisting_findings,
    }


def _hydrate_evaluation_row(d: dict[str, Any]) -> dict[str, Any]:
    """Converte colunas JSON do SQLite em dicionários Python."""
    for field in ("categories_json", "findings_json", "audit_breakdown_json", "raw_metrics_json"):
        clean_field = field.replace("_json", "")
        try:
            d[clean_field] = json.loads(d.get(field) or "{}")
        except Exception:
            d[clean_field] = {}

    d["has_critical_issue"] = bool(d.get("has_critical_issue"))
    d["critical_cap_applied"] = bool(d.get("critical_cap_applied"))
    d["coverage"] = {
        "count": d.get("coverage_count", 0),
        "total": d.get("coverage_total", 8),
        "percent": d.get("coverage_percent", 0.0),
        "label": f"{d.get('coverage_count', 0)} de {d.get('coverage_total', 8)} categorias disponíveis",
    }
    class_label, class_color, class_badge = classify_score(d.get("overall_score", 0.0))
    d["classification_color"] = class_color
    d["classification_badge"] = class_badge
    return d
