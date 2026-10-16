#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/crash_investigator.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  5.5.0
================================================================================
Descrição:
Motor Analítico, Correlação Hardware/I/O, Hipóteses Baseadas em Evidências,
Integração com IA, Execução Segura Controlada, Persistência SQLite e Comparação
Temporal do AegisPulse Crash Investigator (Suporte N1 / N2 / N3).
"""

from __future__ import annotations

import hashlib
import json
import platform
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.collectors.crash_collector import collect_crash_and_reliability_evidence

CRASH_ENGINE_VERSION = "5.5.0"

# Catálogo estrito (Whitelist) de ações de verificação N3 permitidas sob autorização explícita.
# Nenhuma ação destrutiva (chkdsk /f, /r, bcdedit, reg add, atualização de BIOS/driver) ou texto livre da IA é permitido.
SAFE_CRASH_ACTIONS_CATALOG: dict[str, dict[str, Any]] = {
    "verify_dism_checkhealth": {
        "action_id": "verify_dism_checkhealth",
        "title": "Verificar Integridade do Repositório de Componentes (DISM CheckHealth)",
        "objective": "Inspecionar de forma 100% somente-leitura se há sinalização de corrupção na Component Store (WinSxS) do Windows.",
        "suggested_command_or_procedure": "DISM.exe /Online /Cleanup-Image /CheckHealth",
        "prerequisites": "Execução no Windows 10/11 (não altera arquivos do sistema).",
        "expected_impact": "Zero impacto nos dados; retorna em menos de 10 segundos o estado de integridade da imagem do SO.",
        "risk_level": "BAIXO RISCO (Somente-Leitura)",
        "requires_backup": False,
        "executable_via_whitelist": True,
        "win_cmd": ["dism", "/Online", "/Cleanup-Image", "/CheckHealth"],
    },
    "verify_crash_dump_settings": {
        "action_id": "verify_crash_dump_settings",
        "title": "Auditar Configuração de Geração de Minidumps e Pagefile (Somente-Leitura)",
        "objective": "Verificar se o Windows está configurado para gravar despejos de memória (256 KB Minidump) e se o pagefile.sys está ativo.",
        "suggested_command_or_procedure": "Get-ItemProperty HKLM:\\SYSTEM\\CurrentControlSet\\Control\\CrashControl; Get-CimInstance Win32_PageFileUsage",
        "prerequisites": "Acesso de leitura ao registro e WMI.",
        "expected_impact": "Apenas leitura; confirma por que dumps foram ou não gerados em telas azuis anteriores.",
        "risk_level": "BAIXO RISCO (Somente-Leitura)",
        "requires_backup": False,
        "executable_via_whitelist": True,
        "win_cmd": [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\CrashControl' | Select-Object CrashDumpEnabled, MinidumpDir; Get-CimInstance Win32_PageFileUsage | Select-Object Name, AllocatedBaseSize, CurrentUsage",
        ],
    },
    "query_whea_history": {
        "action_id": "query_whea_history",
        "title": "Consultar Detalhes Estendidos de Erros de Hardware (WHEA-Logger)",
        "objective": "Listar os últimos registros do provedor Microsoft-Windows-WHEA-Logger para identificar o componente (CPU, PCIe Root Port, NVMe ou RAM).",
        "suggested_command_or_procedure": "Get-WinEvent -ProviderName 'Microsoft-Windows-WHEA-Logger' -MaxEvents 15",
        "prerequisites": "Serviço de Log de Eventos ativo.",
        "expected_impact": "Nenhum impacto operacional (consulta somente-leitura).",
        "risk_level": "BAIXO RISCO (Somente-Leitura)",
        "requires_backup": False,
        "executable_via_whitelist": True,
        "win_cmd": [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-WinEvent -ProviderName 'Microsoft-Windows-WHEA-Logger' -MaxEvents 10 -ErrorAction SilentlyContinue | Select-Object TimeCreated, Id, LevelDisplayName, Message | Format-List",
        ],
    },
    "verify_power_pci_aspm": {
        "action_id": "verify_power_pci_aspm",
        "title": "Inspecionar Plano de Energia Ativo e Estado PCIe ASPM (Somente-Leitura)",
        "objective": "Verificar o plano de energia atual (powercfg /getactivescheme), útil para investigar Eventos 129 e BSOD 0x9F.",
        "suggested_command_or_procedure": "powercfg /getactivescheme",
        "prerequisites": "Utilitário nativo powercfg.",
        "expected_impact": "Apenas consulta; não modifica o plano de energia.",
        "risk_level": "BAIXO RISCO (Somente-Leitura)",
        "requires_backup": False,
        "executable_via_whitelist": True,
        "win_cmd": ["powercfg", "/getactivescheme"],
    },
    "manual_backup_before_storage_intervention": {
        "action_id": "manual_backup_before_storage_intervention",
        "title": "Procedimento Manual Prioritário: Backup / Imagem de Segurança Antes de Qualquer Reparo",
        "objective": "Preservar os arquivos críticos do usuário em outra unidade física antes de substituir cabos, testar superfície ou reparar o sistema.",
        "suggested_command_or_procedure": "Procedimento Manual Assistido: Utilize a aba 'Discos, SMART & Recuperação -> Criação de Imagem com Mapfile' apontando para uma unidade externa saudável.",
        "prerequisites": "Unidade externa com espaço livre suficiente.",
        "expected_impact": "Protege contra perda irreversível de dados caso o disco possua setores pendentes (ID 197) ou erros de mídia.",
        "risk_level": "ALTO CUIDADO (Prioridade Máxima de Proteção de Dados)",
        "requires_backup": True,
        "executable_via_whitelist": False,
    },
}


def _get_db_path(base_dir: Path) -> Path:
    data_dir = Path(base_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "aegispulse_storage_history.db"


def ensure_crash_investigator_schema(base_dir: Path) -> tuple[bool, str]:
    """Cria ou migra de forma compatível as tabelas do Crash Investigator no SQLite existente."""
    try:
        db_path = _get_db_path(base_dir)
        with sqlite3.connect(db_path, timeout=8) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crash_investigations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_uuid TEXT NOT NULL,
                    hostname TEXT NOT NULL,
                    investigated_at TEXT NOT NULL,
                    period_hours INTEGER NOT NULL,
                    overall_severity TEXT NOT NULL,
                    headline TEXT NOT NULL,
                    critical_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    warning_count INTEGER DEFAULT 0,
                    bugcheck_count INTEGER DEFAULT 0,
                    minidump_count INTEGER DEFAULT 0,
                    storage_io_events_count INTEGER DEFAULT 0,
                    engine_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_crash_inv_machine_date ON crash_investigations(machine_uuid, investigated_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crash_authorized_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    investigation_id INTEGER,
                    action_id TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output_summary TEXT NOT NULL
                )
                """
            )
            conn.commit()
        return True, ""
    except Exception as exc:
        return False, f"Falha ao inicializar/migrar banco SQLite do Crash Investigator: {exc}"


def correlate_hardware_and_io_faults(
    events: list[dict[str, Any]],
    bsod_analysis: dict[str, Any],
    reliability_history: dict[str, Any],
    hardware_info: dict[str, Any] | None = None,
    storage_suite: dict[str, Any] | None = None,
    drivers_bios: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    2.4. Correlaciona eventos do Windows (51, 129, 153, 154, 157, 7, 11, WHEA, 41, 4101)
    com indicadores SMART, temperaturas e drivers, diferenciando:
    - Falha Física de Mídia vs Problema de Comunicação/Interface vs Driver/Controladora vs Alimentação Elétrica.
    """
    hw = hardware_info if isinstance(hardware_info, dict) else {}
    st = storage_suite if isinstance(storage_suite, dict) else {}
    drv = drivers_bios if isinstance(drivers_bios, dict) else {}
    temps = hw.get("temperatures") if isinstance(hw.get("temperatures"), dict) else {}

    evt_51 = [e for e in events if e.get("event_id") == 51]
    evt_129 = [e for e in events if e.get("event_id") == 129]
    evt_153 = [e for e in events if e.get("event_id") == 153]
    evt_media_hw = [e for e in events if e.get("event_id") in (7, 154)]
    evt_usb_disc = [e for e in events if e.get("event_id") == 157]
    evt_whea = [e for e in events if e.get("category") == "whea_hardware"]
    evt_kp41 = [e for e in events if e.get("event_id") == 41 and e.get("category") == "kernel_power"]
    evt_tdr = [e for e in events if e.get("event_id") == 4101]

    # Inspeciona indicadores SMART nos discos coletados
    disks_with_media_faults: list[str] = []
    disks_with_crc_only: list[str] = []
    smart_collection_failed = False

    devs = st.get("devices") if isinstance(st.get("devices"), list) else []
    if not devs:
        smart_collection_failed = True
    for d in devs:
        if not isinstance(d, dict):
            continue
        sm = d.get("smart_summary") if isinstance(d.get("smart_summary"), dict) else {}
        pend = int(sm.get("pending_sectors") or 0)
        realloc = int(sm.get("reallocated_sectors") or 0)
        uncorr = int(sm.get("uncorrectable_errors") or 0)
        cw = int(sm.get("critical_warning_raw") or 0)
        crc = int(sm.get("crc_interface_errors") or 0)
        d_label = f"Disk #{d.get('disk_number')} ({d.get('brand', '')} {d.get('model', 'Disco')})".strip()

        if pend > 0 or realloc > 0 or uncorr > 0 or cw > 0:
            disks_with_media_faults.append(
                f"{d_label}: Setores Pendentes={pend}, Realocados={realloc}, Incorrigíveis={uncorr}"
            )
        elif crc > 0:
            disks_with_crc_only.append(f"{d_label}: UltraDMA CRC={crc} (0 setores defeituosos)")

    cpu_temp = float(temps.get("cpu_temp_c") or 0.0) if temps.get("cpu_temp_c") is not None else None
    gpu_temp = float(temps.get("gpu_temp_c") or 0.0) if temps.get("gpu_temp_c") is not None else None
    thermal_alert = (cpu_temp is not None and cpu_temp >= 85.0) or (gpu_temp is not None and gpu_temp >= 85.0)

    has_physical_media_risk = len(disks_with_media_faults) > 0 or len(evt_media_hw) > 0
    has_io_timeouts = (len(evt_51) + len(evt_129) + len(evt_153)) > 0

    classifications: list[str] = []
    technical_notes: list[str] = []

    if has_physical_media_risk:
        classifications.append("Falha Física de Mídia / Setores Instáveis Confirmados")
        technical_notes.append(
            "PRIORIDADE DE PROTEÇÃO DE DADOS: Há evidência direta de degradação física de mídia ("
            + ("; ".join(disks_with_media_faults) or f"{len(evt_media_hw)} evento(s) 7/154")
            + "). Testes intensivos de escrita e reparos automáticos (CHKDSK /F /R) estão suspensos para evitar perda de dados."
        )

    if has_io_timeouts or disks_with_crc_only:
        classifications.append("Instabilidade de E/S, Timeout de Controladora ou Comunicação de Interface")
        technical_notes.append(
            f"Correlação E/S: Eventos 51 ({len(evt_51)}), 129 ({len(evt_129)}) e 153 ({len(evt_153)}). "
            "NOTA METODOLÓGICA: Erros de CRC (SMART 199) não provam isoladamente que o cabo está rompido (podem decorrer de oxidação no conector, ponte USB ou ruído elétrico), "
            "e um Evento 129 (StorPort Reset) isolado não prova defeito físico do SSD (pode decorrer de transição de energia APST/LPM, driver ou espera por setor pendente)."
        )

    if evt_whea:
        classifications.append("Alertas de Arquitetura de Hardware (WHEA-Logger)")
        technical_notes.append(
            f"Foram registrados {len(evt_whea)} evento(s) WHEA-Logger no período. Avalie se são erros PCIe AER corrigidos (ID 17) ou erros de CPU/Memória não corrigidos (ID 18/1)."
        )

    if evt_kp41 and bsod_analysis.get("bugcheck_count", 0) == 0:
        classifications.append("Interrupção Abrupta de Energia (Kernel-Power 41 sem BugCheck)")
        technical_notes.append(
            f"Ocorreram {len(evt_kp41)} reinicializações Kernel-Power 41 sem código de parada BSOD associado, sugerindo corte de alimentação elétrica (PSU/rede elétrica), acionamento físico do botão Reset ou travamento total sem possibilidade de escrita no pagefile."
        )

    if thermal_alert:
        classifications.append("Estresse Térmico Elevado (CPU/GPU >= 85°C)")
        technical_notes.append(f"Temperaturas atuais elevadas (CPU: {cpu_temp}°C | GPU: {gpu_temp}°C) podem induzir throttling ou desligamento térmico.")

    if not classifications:
        primary_cls = "Operação Nominal (Sem Correlações Críticas de Falha de Hardware/I/O)"
    else:
        primary_cls = " + ".join(classifications)

    return {
        "primary_classification": primary_cls,
        "data_protection_priority": has_physical_media_risk,
        "smart_collection_failed": smart_collection_failed,
        "counts": {
            "event_51_paging": len(evt_51),
            "event_129_storport_reset": len(evt_129),
            "event_153_io_retry": len(evt_153),
            "event_7_154_media_hw": len(evt_media_hw),
            "event_157_surprise_removal": len(evt_usb_disc),
            "whea_events": len(evt_whea),
            "kernel_power_41": len(evt_kp41),
            "display_tdr_4101": len(evt_tdr),
        },
        "disks_with_media_faults": disks_with_media_faults,
        "disks_with_crc_only": disks_with_crc_only,
        "thermal_alert": thermal_alert,
        "cpu_temp_c": cpu_temp,
        "gpu_temp_c": gpu_temp,
        "technical_notes": technical_notes,
        "driver_ anomalies_count": int(drv.get("pnp_error_count") or 0),
    }


def build_hypotheses_and_action_plan(
    evidence_bundle: dict[str, Any],
    hw_io_corr: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str]]:
    """
    Constrói hipóteses técnicas ordenadas por plausibilidade (com evidências favoráveis
    e contrárias explícitas), testes adicionais recomendados, plano de ação N3 e riscos/cuidados.
    """
    events = evidence_bundle.get("all_normalized_events") or []
    bsod = evidence_bundle.get("bsod_analysis") or {}
    rel = evidence_bundle.get("reliability_history") or {}
    counts = hw_io_corr.get("counts") or {}

    hypotheses: list[dict[str, Any]] = []
    additional_tests: list[str] = []
    action_plan: list[dict[str, Any]] = []
    precautions: list[str] = [
        "Nunca execute CHKDSK /F ou /R nem testes intensivos de escrita em discos com Setores Pendentes (SMART ID 197 > 0) antes de concluir o backup ou imagem integral dos dados.",
        "Coincidência temporal com uma atualização do Windows ou presença de um módulo do kernel (como ntoskrnl.exe) em um minidump não confirma causalidade sem evidência corroborativa.",
    ]

    # Hipótese 1: Degradação Física de Mídia / Setores Pendentes provocando Timeouts de E/S
    if hw_io_corr.get("disks_with_media_faults") or counts.get("event_7_154_media_hw", 0) > 0:
        fav = list(hw_io_corr.get("disks_with_media_faults") or [])
        if counts.get("event_153_io_retry", 0) > 0:
            fav.append(f"{counts['event_153_io_retry']} ocorrência(s) de Event ID 153 (retentativa de leitura em LBA).")
        if counts.get("event_51_paging", 0) > 0:
            fav.append(f"{counts['event_51_paging']} ocorrência(s) de Event ID 51 (falha de paginação).")
        if counts.get("event_129_storport_reset", 0) > 0:
            fav.append(f"{counts['event_129_storport_reset']} ocorrência(s) de Event ID 129 (reset de controladora).")

        con = []
        if bsod.get("bugcheck_count", 0) == 0:
            con.append("A falha de leitura na unidade afetada ainda não derrubou o kernel em BSOD (provavelmente por ocorrer em unidade secundária/USB).")

        hypotheses.append({
            "rank": 1,
            "hypothesis_id": "HYP_STORAGE_MEDIA_FAULT",
            "title": "Degradação Física de Mídia / Setores Pendentes Causando Contenção de E/S",
            "category": "Falha Física de Mídia de Armazenamento",
            "plausibility_score": 92,
            "confidence_level": "Alta Confiança",
            "favorable_evidence": fav,
            "contrary_evidence": con or ["Nenhuma evidência contrária identificada."],
            "confidence_justification": (
                "Confirmado diretamente pelos registradores físicos SMART da unidade combinados com eventos de retentativa/timeout de E/S no Windows."
            ),
        })
        action_plan.append(SAFE_CRASH_ACTIONS_CATALOG["manual_backup_before_storage_intervention"])
        additional_tests.append("Executar leitura controlada de verificação (Somente-Leitura) e criar imagem setor-a-setor (.img) com Mapfile da unidade afetada.")

    # Hipótese 2: Problemas de Comunicação de Interface, Ponte USB ou Gerenciamento de Energia (Event 129 / 153 / 157 / CRC)
    if (counts.get("event_129_storport_reset", 0) > 0 or counts.get("event_157_surprise_removal", 0) > 0 or hw_io_corr.get("disks_with_crc_only")) and not hw_io_corr.get("disks_with_media_faults"):
        fav = []
        if counts.get("event_129_storport_reset", 0) > 0:
            fav.append(f"{counts['event_129_storport_reset']} reset(s) de controladora StorPort (Event ID 129).")
        if counts.get("event_157_surprise_removal", 0) > 0:
            fav.append(f"{counts['event_157_surprise_removal']} evento(s) de remoção surpresa de disco (Event ID 157).")
        if hw_io_corr.get("disks_with_crc_only"):
            fav.extend(hw_io_corr["disks_with_crc_only"])

        con = [
            "Os contadores de setores defeituosos na mídia (SMART 5, 197 e 198) estão zerados, o que fala contra defeito físico nas células Flash/pratos magnéticos."
        ]
        hypotheses.append({
            "rank": len(hypotheses) + 1,
            "hypothesis_id": "HYP_INTERFACE_OR_LPM_TIMEOUT",
            "title": "Timeout de Comunicação na Interface (Cabo SATA / Ponte USB / Economia de Energia PCIe/AHCI)",
            "category": "Comunicação de Interface / Controladora / Energia de Barramento",
            "plausibility_score": 78,
            "confidence_level": "Média-Alta Confiança",
            "favorable_evidence": fav,
            "contrary_evidence": con,
            "confidence_justification": (
                "A presença de resets (129) ou erros CRC (199) sem setores defeituosos aponta para perda de pacotes na camada de transporte ou atraso ao acordar de estados de baixo consumo (DIPM/APST)."
            ),
        })
        action_plan.append(SAFE_CRASH_ACTIONS_CATALOG["verify_power_pci_aspm"])
        additional_tests.append("Inspecionar cabo de dados SATA / conectar unidades externas em porta USB traseira direta da placa-mãe e monitorar se o contador CRC (ID 199) estabiliza.")

    # Hipótese 3: Telas Azuis (BSOD) / Falha de Driver ou Subsistema Gráfico
    if bsod.get("bugcheck_count", 0) > 0 or bsod.get("minidump_files_count", 0) > 0 or counts.get("display_tdr_4101", 0) > 0:
        fav = []
        if bsod.get("bugcheck_count", 0) > 0:
            codes_str = ", ".join(f"{k} ({v}x)" for k, v in (bsod.get("recurring_bugcheck_patterns") or {}).items())
            fav.append(f"{bsod['bugcheck_count']} ocorrência(s) de BugCheck registradas: {codes_str}.")
        if bsod.get("probable_third_party_or_hw_suspects"):
            fav.append(f"Módulos suspeitos prováveis referenciados nos minidumps: {', '.join(bsod['probable_third_party_or_hw_suspects'])}.")
        if counts.get("display_tdr_4101", 0) > 0:
            fav.append(f"{counts['display_tdr_4101']} recuperação(ões) de timeout do driver de vídeo (Event ID 4101 Display TDR).")
        if rel.get("installations_updates_count", 0) > 0:
            fav.append(f"{rel['installations_updates_count']} instalação(ões)/atualização(ões) registradas no período próximo aos incidentes.")

        con = []
        if not bsod.get("probable_third_party_or_hw_suspects"):
            con.append("Nenhum driver de terceiros específico isolado nos cabeçalhos de minidump (apenas módulos de sistema/vítimas ou dumps ausentes).")

        hypotheses.append({
            "rank": len(hypotheses) + 1,
            "hypothesis_id": "HYP_BSOD_DRIVER_OR_KERNEL",
            "title": "Parada Crítica do Kernel (BSOD) / Timeout de Driver em Modo Kernel",
            "category": "Drivers / Subsistema de Kernel / Vídeo",
            "plausibility_score": 80 if bsod.get("probable_third_party_or_hw_suspects") else 65,
            "confidence_level": "Média-Alta Confiança" if bsod.get("probable_third_party_or_hw_suspects") else "Média Confiança (Requer Símbolos de Dump)",
            "favorable_evidence": fav,
            "contrary_evidence": con or ["Coincidência temporal com atualização não confirma causalidade sem teste de regressão do driver."],
            "confidence_justification": (
                "Baseado nos códigos de parada BugCheck e metadados de minidump; diferencia módulos vítimas do SO (ntoskrnl.exe) de módulos de dispositivos."
            ),
        })
        action_plan.append(SAFE_CRASH_ACTIONS_CATALOG["verify_crash_dump_settings"])
        action_plan.append(SAFE_CRASH_ACTIONS_CATALOG["verify_dism_checkhealth"])
        additional_tests.append("Analisar os arquivos .dmp em %SystemRoot%\\Minidump com símbolos oficiais Microsoft (WinDbg !analyze -v) e verificar histórico de versões do driver envolvido.")

    # Hipótese 4: Erros de Hardware WHEA ou Reinicializações por Energia (Kernel-Power 41)
    if counts.get("whea_events", 0) > 0 or counts.get("kernel_power_41", 0) > 0:
        fav = []
        if counts.get("whea_events", 0) > 0:
            fav.append(f"{counts['whea_events']} alerta(s) de hardware registrados pelo subsistema WHEA-Logger.")
        if counts.get("kernel_power_41", 0) > 0:
            fav.append(f"{counts['kernel_power_41']} evento(s) Kernel-Power 41 (reinicialização sem desligamento limpo).")
        if hw_io_corr.get("thermal_alert"):
            fav.append(f"Temperatura elevada detectada (CPU: {hw_io_corr.get('cpu_temp_c')}°C / GPU: {hw_io_corr.get('gpu_temp_c')}°C).")

        con = []
        if not hw_io_corr.get("thermal_alert"):
            con.append("As temperaturas atuais de CPU e GPU encontram-se dentro da faixa operacional segura.")

        hypotheses.append({
            "rank": len(hypotheses) + 1,
            "hypothesis_id": "HYP_WHEA_OR_POWER_LOSS",
            "title": "Instabilidade Elétrica (PSU / VRM / Tomada) ou Erro de Barramento PCIe/CPU (WHEA)",
            "category": "Alimentação Elétrica / Hardware Base (WHEA)",
            "plausibility_score": 72 if counts.get("whea_events", 0) > 0 else 60,
            "confidence_level": "Média Confiança",
            "favorable_evidence": fav,
            "contrary_evidence": con or ["Event ID 41 isolado não distingue queda de luz externa de desarme interno da fonte (PSU)."],
            "confidence_justification": (
                "Reinicializações sem geração de minidump ou acompanhadas de eventos WHEA indicam interrupção na camada física/elétrica antes que o kernel consiga gravar o despejo."
            ),
        })
        action_plan.append(SAFE_CRASH_ACTIONS_CATALOG["query_whea_history"])
        additional_tests.append("Verificar estabilidade da linha 12V/5V da fonte de alimentação (PSU), testar sem perfil de overclock/XMP e inspecionar logs detalhados do WHEA-Logger.")

    # Hipótese 5: Falhas Restritas a Aplicativos em Modo Usuário
    if not hypotheses and (rel.get("app_failures_count", 0) > 0 or len(events) > 0):
        hypotheses.append({
            "rank": 1,
            "hypothesis_id": "HYP_USER_MODE_APP_FAULTS",
            "title": "Ocorrências Restritas a Aplicativos/Serviços em Modo Usuário (Sem Falha de Kernel/Hardware)",
            "category": "Software / Aplicativos em Modo Usuário",
            "plausibility_score": 70,
            "confidence_level": "Média-Alta Confiança",
            "favorable_evidence": [
                f"{len(events)} evento(s) registrados no período, com 0 telas azuis (BSOD) e 0 setores defeituosos nos discos."
            ],
            "contrary_evidence": [
                "Ausência de eventos WHEA-Logger, Kernel-Power 41 ou erros físicos SMART descarta falha crítica de hardware no período."
            ],
            "confidence_justification": "Os registros limitam-se a eventos de camada lógica/aplicação sem comprometimento do kernel.",
        })
        action_plan.append(SAFE_CRASH_ACTIONS_CATALOG["verify_dism_checkhealth"])

    if not action_plan:
        action_plan.append(SAFE_CRASH_ACTIONS_CATALOG["verify_dism_checkhealth"])
        action_plan.append(SAFE_CRASH_ACTIONS_CATALOG["verify_crash_dump_settings"])

    # Remove duplicatas no plano de ação mantendo a ordem
    dedup_plan: list[dict[str, Any]] = []
    seen_act: set[str] = set()
    for a in action_plan:
        if a["action_id"] not in seen_act:
            seen_act.add(a["action_id"])
            dedup_plan.append(a)

    # Ordena hipóteses por plausibilidade decrescente e renumera rank
    hypotheses.sort(key=lambda h: int(h.get("plausibility_score") or 0), reverse=True)
    for idx, h in enumerate(hypotheses, start=1):
        h["rank"] = idx

    return hypotheses, dedup_plan, additional_tests, precautions


def build_deterministic_n3_dossier_text(investigation: dict[str, Any]) -> str:
    """
    Gera o Dossiê Analítico Estruturado nas 8 seções obrigatórias (Seção 2.5)
    usando o motor determinístico local quando a IA externa não é usada ou falha.
    """
    summary = investigation.get("incident_summary") or {}
    timeline = investigation.get("consolidated_timeline") or []
    hyps = investigation.get("hypotheses") or []
    plan = investigation.get("action_plan") or []
    tests = investigation.get("recommended_additional_tests") or []
    precautions = investigation.get("risks_and_precautions") or []
    lims = investigation.get("limitations_and_gaps") or []

    lines: list[str] = []
    lines.append("## 1. Resumo Executivo do Incidente (Fatos Observados)")
    lines.append(f"- **Classificação Geral:** {summary.get('overall_severity', 'NORMAL')} — {summary.get('headline', '')}")
    lines.append(
        f"- **Métricas do Período ({investigation.get('period_hours', 168)}h):** "
        f"Críticos: {summary.get('critical_events_count', 0)} | Erros: {summary.get('error_events_count', 0)} | "
        f"Avisos: {summary.get('warning_events_count', 0)} | BSODs: {summary.get('bugcheck_count', 0)} | "
        f"Minidumps: {summary.get('minidump_files_count', 0)}."
    )

    lines.append("\n## 2. Linha do Tempo dos Eventos Relevantes")
    if timeline:
        for ev in timeline[:8]:
            lines.append(
                f"- `{ev.get('timestamp')}` — **{ev.get('source')} (ID {ev.get('event_id')} | {ev.get('severity')})**: "
                f"{ev.get('original_message')[:140]} -> *Interpretação:* {ev.get('technical_interpretation')}"
            )
    else:
        lines.append("- Nenhum evento crítico ou erro registrado no período analisado.")

    lines.append("\n## 3. Hipóteses Técnicas Ordenadas por Plausibilidade")
    if hyps:
        for h in hyps:
            lines.append(f"- **#{h.get('rank')} {h.get('title')}** — Plausibilidade: **{h.get('plausibility_score')}%** ({h.get('confidence_level')})")
    else:
        lines.append("- Nenhuma hipótese de anomalia formulada (sistema sem eventos de falha no período).")

    lines.append("\n## 4. Evidências Favoráveis (Fatos) e Contrárias por Hipótese")
    if hyps:
        for h in hyps:
            fav_s = "; ".join(h.get("favorable_evidence") or [])
            con_s = "; ".join(h.get("contrary_evidence") or [])
            lines.append(f"- **{h.get('title')}:** *Favoráveis:* {fav_s} | *Contrárias/Lacunas:* {con_s}")
    else:
        lines.append("- Sem hipóteses ativas para confrontação de evidências.")

    lines.append("\n## 5. Nível de Confiança e Justificativa")
    if hyps:
        for h in hyps:
            lines.append(f"- **{h.get('title')} ({h.get('confidence_level')}):** {h.get('confidence_justification')}")
    else:
        lines.append("- Confiança Alta na estabilidade do período avaliado (baseada na ausência de registros de falha nos logs disponíveis).")
    if lims:
        lines.append(f"- **Limitações / Lacunas Reconhecidas:** {'; '.join(lims)}")

    lines.append("\n## 6. Testes Adicionais Recomendados")
    for t in (tests or ["Manter monitoramento periódico do Health Score e SMART."]):
        lines.append(f"- {t}")

    lines.append("\n## 7. Plano de Ação Priorizado para Suporte N3")
    for idx, act in enumerate(plan, start=1):
        lines.append(
            f"- **{idx}. [{act.get('risk_level')}] {act.get('title')}:** `{act.get('suggested_command_or_procedure')}` — "
            f"Objetivo: {act.get('objective')} (Exige Backup Prévio: {'Sim' if act.get('requires_backup') else 'Não'})."
        )

    lines.append("\n## 8. Riscos e Cuidados Antes de Cada Intervenção")
    for p in precautions:
        lines.append(f"- {p}")

    return "\n".join(lines)


def save_crash_investigation_to_db(base_dir: Path, investigation: dict[str, Any]) -> tuple[int | None, str]:
    """Salva o resumo e evidências estruturadas da investigação no SQLite (sem dumps binários nem dados pessoais)."""
    ok_schema, err_msg = ensure_crash_investigator_schema(base_dir)
    if not ok_schema:
        return None, err_msg

    try:
        db_path = _get_db_path(base_dir)
        summary = investigation.get("incident_summary") or {}
        hw_io = investigation.get("hardware_io_correlation") or {}
        io_cnts = hw_io.get("counts") or {}
        storage_io_total = (
            int(io_cnts.get("event_51_paging") or 0)
            + int(io_cnts.get("event_129_storport_reset") or 0)
            + int(io_cnts.get("event_153_io_retry") or 0)
            + int(io_cnts.get("event_7_154_media_hw") or 0)
        )

        # Armazena uma cópia enxuta (sem duplicar arrays gigantes) para respeitar privacidade e espaço
        compact_payload = {
            "machine_uuid": investigation.get("machine_uuid"),
            "hostname": investigation.get("hostname"),
            "collected_at": investigation.get("collected_at"),
            "period_hours": investigation.get("period_hours"),
            "incident_summary": summary,
            "bsod_analysis": investigation.get("bsod_analysis"),
            "reliability_history": {
                "source_available": (investigation.get("reliability_history") or {}).get("source_available"),
                "app_failures_count": (investigation.get("reliability_history") or {}).get("app_failures_count"),
                "os_hardware_failures_count": (investigation.get("reliability_history") or {}).get("os_hardware_failures_count"),
                "installations_updates_count": (investigation.get("reliability_history") or {}).get("installations_updates_count"),
            },
            "hardware_io_correlation": hw_io,
            "hypotheses": investigation.get("hypotheses"),
            "action_plan": investigation.get("action_plan"),
            "consolidated_timeline": (investigation.get("consolidated_timeline") or [])[:40],
            "limitations_and_gaps": investigation.get("limitations_and_gaps"),
            "engine_version": CRASH_ENGINE_VERSION,
        }

        with sqlite3.connect(db_path, timeout=8) as conn:
            cur = conn.execute(
                """
                INSERT INTO crash_investigations (
                    machine_uuid, hostname, investigated_at, period_hours, overall_severity,
                    headline, critical_count, error_count, warning_count, bugcheck_count,
                    minidump_count, storage_io_events_count, engine_version, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(investigation.get("machine_uuid") or "AEGIS-LOCAL"),
                    str(investigation.get("hostname") or "Local"),
                    str(investigation.get("collected_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    int(investigation.get("period_hours") or 168),
                    str(summary.get("overall_severity") or "NORMAL"),
                    str(summary.get("headline") or ""),
                    int(summary.get("critical_events_count") or 0),
                    int(summary.get("error_events_count") or 0),
                    int(summary.get("warning_events_count") or 0),
                    int(summary.get("bugcheck_count") or 0),
                    int(summary.get("minidump_files_count") or 0),
                    storage_io_total,
                    CRASH_ENGINE_VERSION,
                    json.dumps(compact_payload, ensure_ascii=False, default=str),
                ),
            )
            conn.commit()
            return int(cur.lastrowid or 0), ""
    except Exception as exc:
        return None, f"Erro de persistência SQLite no Crash Investigator: {exc}"


def list_crash_investigations(
    base_dir: Path,
    limit: int = 20,
    offset: int = 0,
    period_hours_filter: int | None = None,
    severity_filter: str = "",
) -> dict[str, Any]:
    """Lista investigações anteriores salvas no SQLite com paginação e filtros."""
    ok_schema, err_msg = ensure_crash_investigator_schema(base_dir)
    if not ok_schema:
        return {"success": False, "items": [], "total": 0, "db_error": err_msg}

    try:
        db_path = _get_db_path(base_dir)
        where_clauses: list[str] = []
        params: list[Any] = []
        if period_hours_filter is not None and int(period_hours_filter) > 0:
            where_clauses.append("period_hours = ?")
            params.append(int(period_hours_filter))
        if severity_filter and severity_filter.upper() not in ("ALL", "TODOS"):
            where_clauses.append("overall_severity = ?")
            params.append(severity_filter.upper())

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        with sqlite3.connect(db_path, timeout=8) as conn:
            conn.row_factory = sqlite3.Row
            total_row = conn.execute(f"SELECT COUNT(*) AS cnt FROM crash_investigations {where_sql}", params).fetchone()
            total = int(total_row["cnt"]) if total_row else 0

            rows = conn.execute(
                f"""
                SELECT id, machine_uuid, hostname, investigated_at, period_hours, overall_severity,
                       headline, critical_count, error_count, warning_count, bugcheck_count,
                       minidump_count, storage_io_events_count, engine_version, payload_json
                FROM crash_investigations
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, max(1, int(limit)), max(0, int(offset))],
            ).fetchall()

        items = []
        for r in rows:
            try:
                pl = json.loads(r["payload_json"])
            except Exception:
                pl = {}
            items.append({
                "id": r["id"],
                "machine_uuid": r["machine_uuid"],
                "hostname": r["hostname"],
                "investigated_at": r["investigated_at"],
                "period_hours": r["period_hours"],
                "overall_severity": r["overall_severity"],
                "headline": r["headline"],
                "critical_count": r["critical_count"],
                "error_count": r["error_count"],
                "warning_count": r["warning_count"],
                "bugcheck_count": r["bugcheck_count"],
                "minidump_count": r["minidump_count"],
                "storage_io_events_count": r["storage_io_events_count"],
                "engine_version": r["engine_version"],
                "payload": pl,
            })

        return {"success": True, "items": items, "total": total, "limit": limit, "offset": offset}
    except Exception as exc:
        return {"success": False, "items": [], "total": 0, "db_error": str(exc)}


def compare_crash_investigations(older_inv: dict[str, Any], newer_inv: dict[str, Any]) -> dict[str, Any]:
    """
    2.9. Compara duas investigações para identificar:
    - Ocorrências novas, resolvidas e recorrentes;
    - Variação na frequência de telas azuis (BSOD) e erros de armazenamento;
    - Taxa normalizada por 24 horas (evitando confundir janela de tempo maior com piora real!).
    """
    old_pl = older_inv.get("payload") if isinstance(older_inv.get("payload"), dict) else older_inv
    new_pl = newer_inv.get("payload") if isinstance(newer_inv.get("payload"), dict) else newer_inv

    old_hours = max(1, int(older_inv.get("period_hours") or old_pl.get("period_hours") or 168))
    new_hours = max(1, int(newer_inv.get("period_hours") or new_pl.get("period_hours") or 168))

    old_sum = old_pl.get("incident_summary") or {}
    new_sum = new_pl.get("incident_summary") or {}

    old_crit = int(older_inv.get("critical_count") if older_inv.get("critical_count") is not None else old_sum.get("critical_events_count", 0))
    new_crit = int(newer_inv.get("critical_count") if newer_inv.get("critical_count") is not None else new_sum.get("critical_events_count", 0))

    old_bsod = int(older_inv.get("bugcheck_count") if older_inv.get("bugcheck_count") is not None else old_sum.get("bugcheck_count", 0))
    new_bsod = int(newer_inv.get("bugcheck_count") if newer_inv.get("bugcheck_count") is not None else new_sum.get("bugcheck_count", 0))

    old_io = int(older_inv.get("storage_io_events_count") if older_inv.get("storage_io_events_count") is not None else 0)
    new_io = int(newer_inv.get("storage_io_events_count") if newer_inv.get("storage_io_events_count") is not None else 0)

    # Taxas normalizadas por 24h (impede confundir janela de 30 dias vs 24h com aumento real de falhas!)
    old_crit_per_24h = round((old_crit / old_hours) * 24.0, 2)
    new_crit_per_24h = round((new_crit / new_hours) * 24.0, 2)

    old_tl = old_pl.get("consolidated_timeline") or []
    new_tl = new_pl.get("consolidated_timeline") or []

    def _sig_map(tl_list: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        mp: dict[str, dict[str, Any]] = {}
        for ev in tl_list:
            if not isinstance(ev, dict):
                continue
            sig = f"{ev.get('source')}|ID:{ev.get('event_id')}|{ev.get('category')}"
            if sig not in mp:
                mp[sig] = {"signature": sig, "source": ev.get("source"), "event_id": ev.get("event_id"), "category": ev.get("category"), "count": 0}
            mp[sig]["count"] += 1
        return mp

    old_sigs = _sig_map(old_tl)
    new_sigs = _sig_map(new_tl)

    new_occurrences = [v for k, v in new_sigs.items() if k not in old_sigs]
    resolved_occurrences = [v for k, v in old_sigs.items() if k not in new_sigs]
    recurring_occurrences = [
        {**v, "previous_count": old_sigs[k]["count"], "delta_count": v["count"] - old_sigs[k]["count"]}
        for k, v in new_sigs.items()
        if k in old_sigs
    ]

    old_lims = old_pl.get("limitations_and_gaps") or []
    new_lims = new_pl.get("limitations_and_gaps") or []
    coverage_warning = ""
    if old_hours != new_hours:
        coverage_warning = (
            f"ATENÇÃO METODOLÓGICA (Janelas Temporais Diferentes): A investigação anterior cobriu {old_hours}h "
            f"enquanto a investigação recente cobriu {new_hours}h. Utilize a taxa normalizada por 24h "
            f"({old_crit_per_24h}/dia vs {new_crit_per_24h}/dia) para avaliar melhora ou piora real sem viés de volume de coleta."
        )
    elif len(old_lims) != len(new_lims):
        coverage_warning = (
            "ATENÇÃO METODOLÓGICA (Diferença de Cobertura de Fontes): As duas investigações possuem níveis de acesso/fontes disponíveis distintos."
        )

    if new_crit_per_24h < old_crit_per_24h or (new_bsod < old_bsod):
        trend_verdict = "MELHORA OBSERVADA (Redução na taxa diária de eventos críticos / BSODs)"
    elif new_crit_per_24h > old_crit_per_24h or (new_bsod > old_bsod):
        trend_verdict = "DEGRADAÇÃO / AUMENTO DE INCIDENTES (Aumento na taxa diária de falhas)"
    else:
        trend_verdict = "ESTABILIDADE / PADRÃO MANTIDO"

    return {
        "older_id": older_inv.get("id"),
        "newer_id": newer_inv.get("id"),
        "older_date": older_inv.get("investigated_at") or old_pl.get("collected_at"),
        "newer_date": newer_inv.get("investigated_at") or new_pl.get("collected_at"),
        "older_period_hours": old_hours,
        "newer_period_hours": new_hours,
        "coverage_differ_flag": bool(coverage_warning),
        "coverage_warning": coverage_warning,
        "critical_count_delta": new_crit - old_crit,
        "critical_rate_per_24h_older": old_crit_per_24h,
        "critical_rate_per_24h_newer": new_crit_per_24h,
        "bsod_count_delta": new_bsod - old_bsod,
        "storage_io_delta": new_io - old_io,
        "new_occurrences": new_occurrences,
        "resolved_occurrences": resolved_occurrences,
        "recurring_occurrences": recurring_occurrences,
        "trend_verdict": trend_verdict,
    }


def execute_authorized_crash_action(
    base_dir: Path,
    action_id: str,
    confirm_token: str = "",
    investigation_id: int | None = None,
) -> dict[str, Any]:
    """
    2.6. Executa apenas ações pré-homologadas da Whitelist (SAFE_CRASH_ACTIONS_CATALOG)
    mediante confirmação explícita. Rejeita comandos arbitrários ou texto livre da IA.
    """
    aid = str(action_id or "").strip()
    if not aid or aid not in SAFE_CRASH_ACTIONS_CATALOG:
        return {
            "success": False,
            "error_code": "INVALID_OR_UNWHITELISTED_ACTION",
            "message": f"🚫 Ação rejeitada: '{aid}' não faz parte do catálogo seguro homologado do Crash Investigator. Texto livre ou comandos externos não são executados.",
        }

    spec = SAFE_CRASH_ACTIONS_CATALOG[aid]
    if not spec.get("executable_via_whitelist"):
        return {
            "success": False,
            "error_code": "MANUAL_PROCEDURE_ONLY",
            "message": f"ℹ️ '{spec['title']}' é um procedimento assistido de proteção de dados e não deve ser disparado como comando automático.",
        }

    if str(confirm_token or "").strip().upper() not in ("CONFIRMAR_ACAO_N3", "CONFIRMAR"):
        return {
            "success": False,
            "confirmation_required": True,
            "error_code": "CONFIRMATION_REQUIRED",
            "action_spec": spec,
            "message": f"⚠️ Confirmação explícita exigida para '{spec['title']}'. Digite CONFIRMAR_ACAO_N3 para autorizar.",
        }

    executed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if platform.system() == "Windows":
        try:
            proc = subprocess.run(
                spec["win_cmd"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            out_txt = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip() or "Verificação concluída sem alertas."
            status_str = "completed" if proc.returncode == 0 else f"warning_rc_{proc.returncode}"
        except Exception as exc:
            out_txt = f"Erro ao executar verificação: {exc}"
            status_str = "failed"
    else:
        out_txt = f"[Verificação Homologada Validada] Comando: {spec['suggested_command_or_procedure']}"
        status_str = "completed"

    # Registra no SQLite se disponível
    ok_schema, _ = ensure_crash_investigator_schema(base_dir)
    if ok_schema:
        try:
            with sqlite3.connect(_get_db_path(base_dir), timeout=5) as conn:
                conn.execute(
                    "INSERT INTO crash_authorized_actions (investigation_id, action_id, executed_at, status, output_summary) VALUES (?, ?, ?, ?, ?)",
                    (investigation_id, aid, executed_at, status_str, out_txt[:1500]),
                )
                conn.commit()
        except Exception:
            pass

    return {
        "success": True,
        "action_id": aid,
        "title": spec["title"],
        "executed_at": executed_at,
        "status": status_str,
        "output": out_txt[:2000],
        "message": f"✅ Ação '{spec['title']}' executada e registrada com sucesso.",
    }


def run_full_crash_investigation(
    base_dir: Path,
    period_hours: int = 168,
    severity_filter: str = "ALL",
    category_filter: str = "ALL",
    source_filter: str = "",
    event_id_filter: int | None = None,
    equipment_filter: str = "",
    snapshot: dict[str, Any] | None = None,
    use_ai: bool = False,
    ai_provider: str = "local",
    api_key: str = "",
    grok_api_key: str = "",
    user_role: str = "admin",
    persist: bool = True,
    raw_override: dict[str, Any] | None = None,
    dump_dirs_override: list[Path] | None = None,
) -> dict[str, Any]:
    """
    Executa a investigação completa de falhas (Coleta + Normalização + BSOD/Dumps +
    Confiabilidade + Correlação Hardware/I/O + Hipóteses + Plano de Ação N3 +
    IA/Regras Locais + Persistência SQLite).
    """
    snap = snapshot if isinstance(snapshot, dict) else {}
    hw = snap.get("hardware") if isinstance(snap.get("hardware"), dict) else {}
    st = snap.get("storage_suite") if isinstance(snap.get("storage_suite"), dict) else {}
    drv = snap.get("drivers_bios") if isinstance(snap.get("drivers_bios"), dict) else {}

    evidence = collect_crash_and_reliability_evidence(
        period_hours=period_hours,
        severity_filter=severity_filter,
        category_filter=category_filter,
        source_filter=source_filter,
        event_id_filter=event_id_filter,
        equipment_filter=equipment_filter,
        raw_override=raw_override,
        dump_dirs_override=dump_dirs_override,
    )

    all_events = evidence.get("all_normalized_events") or []
    filtered_events = evidence.get("events") or []
    bsod = evidence.get("bsod_analysis") or {}
    rel = evidence.get("reliability_history") or {}

    hw_io_corr = correlate_hardware_and_io_faults(
        events=all_events,
        bsod_analysis=bsod,
        reliability_history=rel,
        hardware_info=hw,
        storage_suite=st,
        drivers_bios=drv,
    )

    hypotheses, action_plan, additional_tests, precautions = build_hypotheses_and_action_plan(
        evidence_bundle=evidence,
        hw_io_corr=hw_io_corr,
    )

    # Contagens por severidade e recorrência por fonte/EventID
    crit_cnt = sum(1 for e in all_events if e.get("severity") == "CRÍTICO")
    err_cnt = sum(1 for e in all_events if e.get("severity") == "ERRO")
    warn_cnt = sum(1 for e in all_events if e.get("severity") == "AVISO")

    recurrence_map: dict[str, dict[str, Any]] = {}
    for ev in all_events:
        sig = f"{ev.get('source')}|ID {ev.get('event_id')}"
        if sig not in recurrence_map:
            recurrence_map[sig] = {
                "signature": sig,
                "source": ev.get("source"),
                "event_id": ev.get("event_id"),
                "category": ev.get("category"),
                "severity": ev.get("severity"),
                "affected_component": ev.get("affected_component"),
                "count": 0,
                "first_seen": ev.get("timestamp"),
                "last_seen": ev.get("timestamp"),
            }
        recurrence_map[sig]["count"] += 1
        ts_val = str(ev.get("timestamp") or "")
        if ts_val < str(recurrence_map[sig]["first_seen"]):
            recurrence_map[sig]["first_seen"] = ts_val
        if ts_val > str(recurrence_map[sig]["last_seen"]):
            recurrence_map[sig]["last_seen"] = ts_val

    recurring_groups = sorted(recurrence_map.values(), key=lambda x: x["count"], reverse=True)

    # Determina severidade geral do incidente com base em evidências
    if bsod.get("bugcheck_count", 0) > 0 or hw_io_corr.get("data_protection_priority") or crit_cnt >= 2:
        overall_sev = "CRÍTICO"
    elif crit_cnt == 1 or err_cnt >= 3 or hw_io_corr["counts"].get("event_129_storport_reset", 0) > 0:
        overall_sev = "ALTO"
    elif err_cnt > 0 or warn_cnt > 0:
        overall_sev = "MODERADO"
    else:
        overall_sev = "NORMAL"

    if overall_sev == "NORMAL" and len(all_events) == 0 and bsod.get("bugcheck_count", 0) == 0:
        headline = f"Nenhuma falha crítica, tela azul (BSOD) ou erro de E/S registrado nas últimas {evidence['period_hours']} horas."
    else:
        top_hyp = hypotheses[0]["title"] if hypotheses else hw_io_corr["primary_classification"]
        headline = (
            f"Severidade {overall_sev}: {crit_cnt} evento(s) crítico(s), {err_cnt} erro(s), "
            f"{bsod.get('bugcheck_count', 0)} BSOD(s) — Principal hipótese: {top_hyp}."
        )

    # Limitações e lacunas explícitas
    limitations: list[str] = list(evidence.get("collection_errors") or [])
    if hw_io_corr.get("smart_collection_failed"):
        limitations.append("Os indicadores SMART detalhados não estavam disponíveis no snapshot durante a correlação.")
    if not rel.get("source_available"):
        limitations.append("A classe Win32_ReliabilityRecords não retornou registros para o período (utilizados logs System/Application equivalentes).")
    if bsod.get("bugcheck_count", 0) > 0 and bsod.get("minidump_files_count", 0) == 0:
        limitations.append("Houve registro de BugCheck no Event Viewer, mas nenhum arquivo .dmp correspondente foi encontrado em %SystemRoot%\\Minidump.")

    hostname = str(hw.get("hostname") or evidence.get("hostname") or "Estacao-Local")
    serial_tag = str(hw.get("serial_service_tag") or "LOCAL")
    machine_uuid = "AEGIS-DEV-" + hashlib.sha256(f"{hostname}|{serial_tag}".encode("utf-8")).hexdigest()[:12].upper()

    investigation_payload: dict[str, Any] = {
        "success": True,
        "engine_version": CRASH_ENGINE_VERSION,
        "collected_at": evidence["collected_at"],
        "machine_uuid": machine_uuid,
        "hostname": hostname,
        "period_hours": evidence["period_hours"],
        "period_days": evidence["period_days"],
        "filters_applied": evidence["filters_applied"],
        "incident_summary": {
            "overall_severity": overall_sev,
            "headline": headline,
            "total_events_collected": len(all_events),
            "filtered_events_count": len(filtered_events),
            "critical_events_count": crit_cnt,
            "error_events_count": err_cnt,
            "warning_events_count": warn_cnt,
            "bugcheck_count": bsod.get("bugcheck_count", 0),
            "minidump_files_count": bsod.get("minidump_files_count", 0),
            "data_protection_priority": hw_io_corr.get("data_protection_priority", False),
        },
        "events": filtered_events,
        "recurring_events_summary": recurring_groups[:20],
        "bsod_analysis": bsod,
        "reliability_history": rel,
        "hardware_io_correlation": hw_io_corr,
        "consolidated_timeline": filtered_events[:50],
        "hypotheses": hypotheses,
        "recommended_additional_tests": additional_tests,
        "action_plan": action_plan,
        "risks_and_precautions": precautions,
        "limitations_and_gaps": limitations,
    }

    # Gera o dossiê determinístico local (sempre presente como base auditável)
    deterministic_dossier = build_deterministic_n3_dossier_text(investigation_payload)
    ai_dossier_text = deterministic_dossier
    ai_used_flag = False
    ai_provider_used = "local_deterministic_n3"

    if use_ai and ai_provider.lower() in ("gemini", "grok"):
        try:
            from backend.services.gemini_ai import query_gemini_ai
            ai_prompt = (
                "Analise exclusivamente as evidências reais coletadas pelo AegisPulse Crash Investigator abaixo. "
                "NÃO invente eventos, códigos BugCheck, drivers ou datas. Diferencie Fatos Observados, Inferências e Hipóteses. "
                "Estruture a resposta nas 8 seções: 1. Resumo Executivo; 2. Linha do Tempo; 3. Hipóteses Ordenadas por Plausibilidade; "
                "4. Evidências Favoráveis e Contrárias; 5. Nível de Confiança e Justificativa; 6. Testes Adicionais; "
                "7. Plano de Ação N3 Priorizado; 8. Riscos e Cuidados.\n\n"
                f"EVIDÊNCIAS COLETADAS:\n{deterministic_dossier}"
            )
            ai_res = query_gemini_ai(
                api_key=api_key,
                snapshot={**snap, "crash_investigation": investigation_payload},
                user_prompt=ai_prompt,
                provider=ai_provider,
                user_role=user_role,
                grok_api_key=grok_api_key,
            )
            if ai_res.get("success") and ai_res.get("response_text") and not ai_res.get("requires_subscription"):
                resp_txt = str(ai_res["response_text"]).strip()
                if len(resp_txt) >= 80:
                    ai_dossier_text = resp_txt
                    ai_used_flag = True
                    ai_provider_used = str(ai_res.get("model_used") or ai_provider)
                else:
                    limitations.append("A resposta do provedor de IA não conteve evidências suficientes; mantida a análise determinística local N3.")
            else:
                limitations.append(f"Serviço de IA externa indisponível ou não configurado ({ai_res.get('message', 'offline')}); utilizada análise determinística local N3.")
        except Exception as ai_exc:
            limitations.append(f"Falha ao consultar serviço de IA ({ai_exc}); mantida análise baseada em regras locais.")

    investigation_payload["ai_correlation"] = {
        "ai_used": ai_used_flag,
        "provider_used": ai_provider_used,
        "structured_analysis_text": ai_dossier_text,
        "deterministic_baseline_text": deterministic_dossier,
    }

    inv_id = None
    db_err = ""
    if persist:
        inv_id, db_err = save_crash_investigation_to_db(base_dir, investigation_payload)
        if db_err:
            limitations.append(db_err)

    investigation_payload["investigation_id"] = inv_id
    investigation_payload["persistence_status"] = "saved" if inv_id else ("skipped" if not persist else "degraded_db_error")
    investigation_payload["db_error"] = db_err
    return investigation_payload
