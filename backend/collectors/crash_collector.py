#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/collectors/crash_collector.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  5.5.0
================================================================================
Descrição:
Coletor Técnico Não-Bloqueante do AegisPulse Crash Investigator:
- 2.1. Eventos do Windows (System, Application, Kernel-Power, WHEA-Logger,
       Disco/NTFS/StorPort, Drivers/Display TDR, Serviços e Windows Update).
- 2.2. Investigação de Telas Azuis (BSOD), códigos de parada (BugCheck) e
       inspeção segura de metadados de Minidumps e MEMORY.DMP.
- 2.3. Histórico de Confiabilidade do Windows (Win32_ReliabilityRecords).
- Respeita permissões do SO, trata timeouts sem travar a interface e separa
  rigorosamente a Mensagem Original (Fato) da Interpretação Técnica do Sistema.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Dicionário de Códigos de Parada (BugCheck / BSOD) com significado técnico e cautela diagnóstica
BUGCHECK_KNOWLEDGE_BASE: dict[str, dict[str, str]] = {
    "0x0000009f": {
        "name": "DRIVER_POWER_STATE_FAILURE",
        "meaning": "Um driver de dispositivo ficou em estado de energia inconsistente ou não respondeu a uma transição de suspensão/hibernação/desligamento (IRP de energia).",
        "caution": "Frequentemente associado a gerenciamento de energia PCIe ASPM, drivers de vídeo/Wi-Fi ou controladoras USB/NVMe em transição de estado D0/D3.",
    },
    "0x00000116": {
        "name": "VIDEO_TDR_FAILURE",
        "meaning": "O subsistema gráfico (DirectX Kernel) detectou que a GPU parou de responder e a tentativa de reinicializar o driver de vídeo (Timeout Detection and Recovery) falhou.",
        "caution": "A menção a nvlddmkm.sys, amdkmdag.sys ou igdkmd64.sys indica o subsistema onde o timeout ocorreu, mas a causa pode ser superaquecimento, queda de tensão PCIe (PSU), overclock ou driver.",
    },
    "0x00000124": {
        "name": "WHEA_UNCORRECTABLE_ERROR",
        "meaning": "Erro de hardware de baixo nível reportado pela arquitetura WHEA (Processador, Cache L1/L2/L3, controlador de memória, barramento PCIe ou NVMe).",
        "caution": "Exige correlação com os eventos WHEA-Logger (IDs 1, 17, 18, 19) e temperaturas/tensões antes de concluir substituição de CPU ou placa-mãe.",
    },
    "0x0000007a": {
        "name": "KERNEL_DATA_INPAGE_ERROR",
        "meaning": "O kernel do Windows não conseguiu ler uma página de memória virtual a partir do arquivo de paginação (pagefile.sys) no disco.",
        "caution": "Correlacione com os Eventos 51, 129 e 153 e atributos SMART (ID 197 Setores Pendentes / ID 199 CRC). Pode decorrer de falha de leitura no disco ou desconexão momentânea da controladora.",
    },
    "0x000000f4": {
        "name": "CRITICAL_OBJECT_TERMINATION",
        "meaning": "Um processo ou thread essencial para a operação do Windows (como csrss.exe, wininit.exe ou smss.exe) foi encerrado inesperadamente.",
        "caution": "Frequentemente causado por falha de leitura de E/S no disco do sistema (bloqueando a paginação do processo crítico) ou corrupção de arquivos de sistema.",
    },
    "0x000000ef": {
        "name": "CRITICAL_PROCESS_DIED",
        "meaning": "Um processo crítico do sistema operacional encerrou sua execução de forma anormal.",
        "caution": "Verifique se houve eventos de disco (51/153) ou atualizações/drivers instalados imediatamente antes do incidente.",
    },
    "0x0000001a": {
        "name": "MEMORY_MANAGEMENT",
        "meaning": "Erro severo na gerência de memória virtual/física (tabela de páginas, PTE corrompido ou falha de bit em RAM/pagefile).",
        "caution": "Pode ser provocado tanto por instabilidade de módulos RAM/XMP quanto por corrupção no pagefile.sys em disco com setores instáveis.",
    },
    "0x0000003b": {
        "name": "SYSTEM_SERVICE_EXCEPTION",
        "meaning": "Uma rotina de serviço do sistema (chamada de sistema em modo kernel) gerou uma exceção não tratada (ex: violação de acesso 0xC0000005).",
        "caution": "Módulos de kernel como ntoskrnl.exe ou win32kfull.sys nos dumps costumam ser a vítima que sofreu a exceção, não necessariamente o driver causador.",
    },
    "0x00000050": {
        "name": "PAGE_FAULT_IN_NONPAGED_AREA",
        "meaning": "O sistema referenciou um endereço de memória inválido na área não-paginada do kernel.",
        "caution": "Comum em conflitos de drivers de terceiros (antivírus, anti-cheat, filtros de armazenamento) ou falha de memória RAM.",
    },
    "0x000000d1": {
        "name": "DRIVER_IRQL_NOT_LESS_OR_EQUAL",
        "meaning": "Um driver em modo kernel tentou acessar memória paginável enquanto operava em nível de interrupção (IRQL) elevado (DISPATCH_LEVEL ou superior).",
        "caution": "Verifique se há um driver de rede, armazenamento ou USB de terceiros listado na pilha do minidump.",
    },
    "0x00000133": {
        "name": "DPC_WATCHDOG_VIOLATION",
        "meaning": "Uma rotina de chamada de procedimento adiado (DPC) permaneceu em execução acima do tempo máximo permitido em nível de interrupção elevado.",
        "caution": "Muito comum quando um driver de armazenamento NVMe/SATA ou placa de vídeo fica aguardando resposta de hardware em timeout (correlacione com Event ID 129/153).",
    },
    "0x00000139": {
        "name": "KERNEL_SECURITY_CHECK_FAILURE",
        "meaning": "Falha na verificação de integridade de estruturas críticas de dados do kernel (__fastfail).",
        "caution": "Pode resultar de incompatibilidade de driver ou corrupção de pilha/buffer em modo kernel.",
    },
}

# Módulos nativos do Kernel/SO que frequentemente aparecem como "vítimas" nos dumps e NÃO devem ser acusados automaticamente
OS_VICTIM_KERNEL_MODULES = {
    "ntoskrnl.exe",
    "ntkrnlmp.exe",
    "win32k.sys",
    "win32kfull.sys",
    "win32kbase.sys",
    "fltmgr.sys",
    "ci.dll",
    "hal.dll",
    "storport.sys",
    "stornvme.sys",
    "storahci.sys",
    "ntfs.sys",
    "ndis.sys",
    "tcpip.sys",
    "dxgkrnl.sys",
    "dxgmms2.sys",
    "watchdog.sys",
    "Wdf01000.sys".lower(),
}


def interpret_windows_event(source: str, event_id: int, message: str, level_name: str) -> dict[str, str]:
    """
    Classifica um evento do Windows e produz uma Interpretação Técnica contextual
    estritamente separada da descrição original do evento.
    """
    src_up = str(source or "").upper()
    msg_up = str(message or "").upper()
    eid = int(event_id or 0)

    if eid == 41 and "KERNEL-POWER" in src_up:
        return {
            "category": "kernel_power",
            "component": "Subsistema de Energia / Inicialização (Kernel-Power)",
            "technical_interpretation": (
                "O sistema reiniciou sem um desligamento limpo prévio. O Event ID 41 isolado confirma apenas a interrupção abrupta; "
                "para determinar a causa, verifique se há um BugCheck (BSOD) no mesmo horário ou se o código de parada foi 0x0 "
                "(indicando perda súbita de alimentação elétrica, botão Reset/Power pressionado ou desarme da fonte PSU)."
            ),
        }
    if eid == 6008:
        return {
            "category": "kernel_power",
            "component": "Serviço de Log de Eventos (Desligamento Inesperado)",
            "technical_interpretation": (
                "Confirma que o encerramento anterior do sistema operacional não seguiu a sequência normal de encerramento de serviços."
            ),
        }
    if eid == 1074:
        return {
            "category": "kernel_power",
            "component": "Gerenciador de Sessão / Reinicialização (User32)",
            "technical_interpretation": (
                "Reinicialização ou desligamento solicitado por processo ou usuário (ex: Windows Update ou ação manual). Útil para descartar queda acidental de energia."
            ),
        }
    if "WHEA" in src_up or eid in (1, 17, 18, 19, 20, 46, 47) and "WHEA" in (src_up + msg_up):
        is_corr = eid in (17, 19) or "CORRECTED" in msg_up or "CORRIGIDO" in msg_up
        return {
            "category": "whea_hardware",
            "component": "Arquitetura de Erros de Hardware (WHEA-Logger — CPU / PCIe / Memória)",
            "technical_interpretation": (
                "Erro de hardware corrigido (Corrected Hardware Error) no barramento PCIe (AER) ou cache. Se recorrente em alta frequência, pode causar degradação de desempenho ou evoluir para falha não-corrigida; verifique gerenciamento de energia PCIe (ASPM) e encaixe físico."
                if is_corr
                else "Alerta de erro severo de hardware reportado pelo processador, controlador de memória ou barramento PCIe (Uncorrected Hardware Error). Exige correlação com temperaturas, tensões e integridade do slot PCIe/M.2."
            ),
        }
    if eid == 129 or "RESET TO DEVICE" in msg_up or "REDEFINIÇÃO PARA O DISPOSITIVO" in msg_up:
        return {
            "category": "storage_io",
            "component": "Controladora de Armazenamento (StorPort / AHCI / NVMe / USB)",
            "technical_interpretation": (
                "A controladora de armazenamento emitiu um comando de Reset porque o dispositivo não respondeu a uma requisição de E/S dentro do tempo limite. "
                "NOTA TÉCNICA: Um Evento 129 isolado NÃO prova automaticamente que o SSD/HDD está fisicamente defeituoso — pode ser causado por estado de economia de energia (APST/DIPM), driver da controladora, ponte USB lenta ou setor pendente."
            ),
        }
    if eid == 153:
        return {
            "category": "storage_io",
            "component": "Subsistema de Disco (Retentativa de E/S em Endereço LBA)",
            "technical_interpretation": (
                "Uma operação de leitura ou escrita no endereço lógico (LBA) informado falhou na primeira tentativa e precisou ser repetida pelo driver de armazenamento. "
                "Quando recorrente no mesmo disco, correlacione com o Atributo SMART 197 (Setores Pendentes) e 199 (Erros CRC)."
            ),
        }
    if eid == 51:
        return {
            "category": "storage_io",
            "component": "Gerenciador de Memória / Paginação em Disco (Event 51)",
            "technical_interpretation": (
                "Erro detectado no dispositivo durante uma operação de paginação (leitura/escrita de memória virtual ou cache de sistema de arquivos). "
                "Em unidades USB externas ou discos com setores pendentes, costuma ocorrer durante picos de transferência ou desconexões momentâneas."
            ),
        }
    if eid in (7, 154):
        return {
            "category": "storage_io",
            "component": "Mídia Física de Armazenamento (Bloco Defeituoso / Falha de Hardware I/O)",
            "technical_interpretation": (
                "Indício forte de falha de leitura/escrita em bloco físico ou falha de transferência de hardware na unidade indicada. Priorize a preservação e backup imediato dos dados."
            ),
        }
    if eid in (55, 98, 140):
        return {
            "category": "storage_io",
            "component": "Sistema de Arquivos NTFS / Volume Lógico",
            "technical_interpretation": (
                "Inconsistência detectada na estrutura lógica do sistema de arquivos (NTFS) ou falha ao liberar dados do buffer para o volume. "
                "Antes de executar reparos lógicos (CHKDSK), verifique sempre a saúde física SMART do disco."
            ),
        }
    if eid == 157:
        return {
            "category": "storage_io",
            "component": "Barramento USB / Hot-Plug de Armazenamento (Remoção Surpresa)",
            "technical_interpretation": (
                "O disco foi desconectado abruptamente sem remoção segura pelo sistema operacional (comum em cabos USB com mau contato, queda de tensão 5V em portas frontais ou reinício da ponte USB)."
            ),
        }
    if eid == 1001 and ("BUGCHECK" in msg_up or "WER-SYSTEMERRORREPORTING" in src_up or "REINICIALIZADO APÓS UMA VERIFICAÇÃO DE ERRO" in msg_up):
        return {
            "category": "bsod_bugcheck",
            "component": "Kernel do Sistema Operacional (BugCheck / Tela Azul BSOD)",
            "technical_interpretation": (
                "Registro oficial de parada crítica do kernel (BSOD) com código BugCheck e parâmetros de memória. Deve ser analisado em conjunto com o arquivo de minidump correspondente."
            ),
        }
    if eid == 4101 or ("DISPLAY" in src_up and ("PAROU DE RESPONDER" in msg_up or "STOPPED RESPONDING" in msg_up)):
        return {
            "category": "driver_device",
            "component": "Subsistema Gráfico / Driver de Vídeo (TDR — Event 4101)",
            "technical_interpretation": (
                "O driver de vídeo parou de responder momentaneamente e foi recuperado pelo Windows (Timeout Detection and Recovery). "
                "Causas plausíveis incluem instabilidade do driver gráfico, temperatura elevada da GPU, limite de energia da fonte (PSU) ou conflito de aceleração de hardware."
            ),
        }
    if eid in (219, 7000, 7009, 7023, 7031, 7034):
        return {
            "category": "driver_device" if eid == 219 else "app_service_fault",
            "component": "Gerenciador de Controle de Serviços / Carregamento de Driver",
            "technical_interpretation": (
                "Falha no carregamento de um driver PnP ou encerramento inesperado de um serviço de sistema em segundo plano."
            ),
        }
    if eid in (1000, 1002) and ("APPLICATION" in src_up or "ERROR" in src_up or "HANG" in src_up):
        return {
            "category": "app_service_fault",
            "component": "Aplicativo em Modo Usuário (Application Error / Hang)",
            "technical_interpretation": (
                "Falha ou congelamento restrito a um processo em modo usuário (ex: exceção 0xC0000005 ou falta de biblioteca runtime). "
                "Salvo se acompanhado de erros de disco/memória, falhas isoladas de aplicativos não indicam defeito físico de hardware."
            ),
        }
    if eid in (19, 20, 43, 11707, 11724, 20001) or "UPDATE" in src_up or "MSIINSTALLER" in src_up:
        return {
            "category": "update_install",
            "component": "Windows Update / Instalação de Pacote ou Driver",
            "technical_interpretation": (
                "Registro de instalação, atualização ou falha de pacote/driver. Importante para verificar correlação temporal caso os incidentes tenham começado logo após uma alteração de software/driver."
            ),
        }

    return {
        "category": "system_general",
        "component": source or "Subsistema do Windows",
        "technical_interpretation": (
            "Evento registrado no log do sistema. Deve ser avaliado em conjunto com a frequência de repetição e demais indicadores do equipamento."
        ),
    }


def _extract_bugcheck_code_from_text(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"0x[0-9a-fA-F]{8}", text)
    if m:
        return m.group(0).lower()
    m2 = re.search(r"0x[0-9a-fA-F]{1,8}", text)
    if m2:
        try:
            val = int(m2.group(0), 16)
            return f"0x{val:08x}"
        except ValueError:
            return m2.group(0).lower()
    return None


def inspect_dump_files_safely(dump_dirs: list[Path] | None = None) -> dict[str, Any]:
    """
    Inspeciona com segurança os caminhos convencionais de Minidump e MEMORY.DMP,
    sem presumir que existem e sem modificar configurações do sistema.
    Extrai metadados reais e módulos (.sys/.dll) referenciados nos primeiros 256 KB
    do cabeçalho/stack do minidump, diferenciando vítimas do kernel de suspeitos prováveis.
    """
    sys_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    candidate_dirs = dump_dirs if dump_dirs is not None else [
        sys_root / "Minidump",
        sys_root / "LiveKernelReports",
    ]
    full_memory_dmp = (dump_dirs[0].parent / "MEMORY.DMP") if (dump_dirs and len(dump_dirs) > 0) else (sys_root / "MEMORY.DMP")

    found_dumps: list[dict[str, Any]] = []
    access_errors: list[str] = []
    all_probable_suspects: set[str] = set()
    all_victim_modules: set[str] = set()

    for d_dir in candidate_dirs:
        if not d_dir.exists():
            continue
        try:
            for entry in sorted(d_dir.rglob("*.dmp"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:15]:
                try:
                    st = entry.stat()
                    mod_time = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    # Lê apenas uma janela segura inicial (até 256 KB) para identificar assinatura PAGEDUMP/MDMP e nomes de módulos .sys/.dll
                    raw_head = b""
                    with open(entry, "rb") as f:
                        raw_head = f.read(262144)

                    # Extrai nomes ASCII e UTF-16LE de drivers (*.sys)
                    ascii_mods = set(re.findall(rb"([A-Za-z0-9_\-]{3,32}\.sys)", raw_head, flags=re.IGNORECASE))
                    utf16_mods = set(re.findall(rb"(?:[A-Za-z0-9_\-]\x00){3,32}\.\x00s\x00y\x00s\x00", raw_head, flags=re.IGNORECASE))

                    decoded_mods: set[str] = set()
                    for am in ascii_mods:
                        decoded_mods.add(am.decode("ascii", errors="ignore").lower())
                    for um in utf16_mods:
                        decoded_mods.add(um.decode("utf-16le", errors="ignore").lower())

                    victim_mods = sorted(m for m in decoded_mods if m in OS_VICTIM_KERNEL_MODULES)
                    suspect_mods = sorted(m for m in decoded_mods if m not in OS_VICTIM_KERNEL_MODULES)

                    all_victim_modules.update(victim_mods)
                    all_probable_suspects.update(suspect_mods)

                    found_dumps.append({
                        "filename": entry.name,
                        "path": str(entry),
                        "size_bytes": st.st_size,
                        "size_kb": round(st.st_size / 1024.0, 1),
                        "modified_at": mod_time,
                        "valid_signature": raw_head[:4] in (b"PAGE", b"PAGD", b"MDMP"),
                        "involved_victim_modules": victim_mods[:10],
                        "probable_suspect_modules": suspect_mods[:10],
                        "confirmed_cause_from_dump": (
                            "Não confirmada isoladamente sem análise completa de símbolos (WinDbg) — módulos listados indicam participação na pilha de chamadas."
                        ),
                    })
                except PermissionError:
                    access_errors.append(f"Permissão insuficiente para ler o arquivo de dump: {entry}")
                except OSError as oe:
                    access_errors.append(f"Erro de leitura em {entry.name}: {oe}")
        except PermissionError:
            access_errors.append(f"Permissão negada ao listar diretório de dumps: {d_dir}")
        except OSError as oe:
            access_errors.append(f"Não foi possível inspecionar {d_dir}: {oe}")

    full_dmp_info = None
    if full_memory_dmp.exists():
        try:
            st_full = full_memory_dmp.stat()
            full_dmp_info = {
                "filename": "MEMORY.DMP",
                "path": str(full_memory_dmp),
                "size_mb": round(st_full.st_size / (1024 * 1024), 2),
                "modified_at": datetime.fromtimestamp(st_full.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            }
        except OSError:
            pass

    return {
        "checked_paths": [str(p) for p in candidate_dirs] + [str(full_memory_dmp)],
        "minidump_files_count": len(found_dumps),
        "minidumps": found_dumps,
        "full_memory_dump": full_dmp_info,
        "involved_os_victim_modules": sorted(all_victim_modules),
        "probable_third_party_or_hw_suspects": sorted(all_probable_suspects),
        "access_errors": access_errors,
    }


def _run_powershell_crash_probe(period_hours: int = 168) -> dict[str, Any] | None:
    """
    Executa coleta não-bloqueante via PowerShell dos logs de eventos do Windows,
    registros de BugCheck/WER, configuração CrashControl e Win32_ReliabilityRecords.
    """
    if platform.system() != "Windows":
        return None

    hours = max(1, min(int(period_hours or 168), 2160))
    ps_script = f"""
    $ErrorActionPreference = 'SilentlyContinue'
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $startTime = (Get-Date).AddHours(-{hours})
    $collectionErrors = @()

    # 1. Eventos Críticos, Erros e Avisos Relevantes do Log System
    $sysEvents = @()
    try {{
        $rawSys = @(Get-WinEvent -FilterHashtable @{{ LogName='System'; StartTime=$startTime; Level=@(1,2,3) }} -MaxEvents 140 -ErrorAction Stop | Where-Object {{
            $_.Id -in @(1,7,9,11,17,18,19,20,41,43,46,47,51,55,98,129,140,153,154,157,219,1001,1074,4101,6008,7000,7009,7023,7031,7034) -or
            $_.ProviderName -match 'Kernel-Power|WHEA|BugCheck|WER-SystemErrorReporting|disk|ntfs|stornvme|storahci|storport|Display'
        }})
        foreach ($e in $rawSys) {{
            $sysEvents += @{{
                LogName = 'System'
                Id = [int]$e.Id
                Level = [int]$e.Level
                LevelDisplayName = [string]$e.LevelDisplayName
                ProviderName = [string]$e.ProviderName
                MachineName = [string]$e.MachineName
                TimeCreated = $e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
                Message = (($e.Message -replace '\r\n', ' ') -replace '\s+', ' ').Trim()
            }}
        }}
    }} catch {{
        $collectionErrors += "Aviso ao consultar Log System: $($_.Exception.Message)"
    }}

    # 2. Eventos de Falhas de Aplicativos, WER e Instalações no Log Application
    $appEvents = @()
    try {{
        $rawApp = @(Get-WinEvent -FilterHashtable @{{ LogName='Application'; StartTime=$startTime; Level=@(1,2,3,4) }} -MaxEvents 80 -ErrorAction Stop | Where-Object {{
            $_.Id -in @(1000,1001,1002,11707,11724)
        }})
        foreach ($e in $rawApp) {{
            $appEvents += @{{
                LogName = 'Application'
                Id = [int]$e.Id
                Level = [int]$e.Level
                LevelDisplayName = [string]$e.LevelDisplayName
                ProviderName = [string]$e.ProviderName
                MachineName = [string]$e.MachineName
                TimeCreated = $e.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
                Message = (($e.Message -replace '\r\n', ' ') -replace '\s+', ' ').Trim()
            }}
        }}
    }} catch {{
        $collectionErrors += "Aviso ao consultar Log Application: $($_.Exception.Message)"
    }}

    # 3. Histórico de Confiabilidade (Win32_ReliabilityRecords)
    $relRecords = @()
    try {{
        $rawRel = @(Get-CimInstance -ClassName Win32_ReliabilityRecords -ErrorAction Stop | Select-Object -First 60 SourceName, EventIdentifier, ProductName, Message, TimeGenerated, Logfile)
        foreach ($r in $rawRel) {{
            if ($r.TimeGenerated -ge $startTime) {{
                $relRecords += @{{
                    SourceName = [string]$r.SourceName
                    EventIdentifier = [int]$r.EventIdentifier
                    ProductName = [string]$r.ProductName
                    TimeGenerated = $r.TimeGenerated.ToString('yyyy-MM-dd HH:mm:ss')
                    Message = (($r.Message -replace '\r\n', ' ') -replace '\s+', ' ').Trim()
                }}
            }}
        }}
    }} catch {{
        $collectionErrors += "Fonte Win32_ReliabilityRecords indisponível ou restrita nesta edição do Windows."
    }}

    # 4. Configuração de CrashDump (Somente-Leitura)
    $crashCfg = @{{}}
    try {{
        $cc = Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\CrashControl' -ErrorAction Stop
        $crashCfg = @{{
            CrashDumpEnabled = $cc.CrashDumpEnabled
            MinidumpDir = [string]$cc.MinidumpDir
            DumpFile = [string]$cc.DumpFile
        }}
    }} catch {{}}

    @{{
        Hostname = $env:COMPUTERNAME
        SystemEvents = $sysEvents
        ApplicationEvents = $appEvents
        ReliabilityRecords = $relRecords
        CrashControlConfig = $crashCfg
        CollectionErrors = $collectionErrors
    }} | ConvertTo-Json -Depth 5 -Compress
    """
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=22,
        )
        out = (proc.stdout or "").strip()
        if out:
            return json.loads(out)
    except subprocess.TimeoutExpired:
        return {"CollectionErrors": ["Timeout (22s) atingido ao consultar logs de eventos do Windows."]}
    except Exception as exc:
        return {"CollectionErrors": [f"Falha ao executar coletor de eventos do Windows: {exc}"]}
    return None


def collect_crash_and_reliability_evidence(
    period_hours: int = 168,
    severity_filter: str = "ALL",
    category_filter: str = "ALL",
    source_filter: str = "",
    event_id_filter: int | None = None,
    equipment_filter: str = "",
    raw_override: dict[str, Any] | None = None,
    dump_dirs_override: list[Path] | None = None,
) -> dict[str, Any]:
    """
    Coleta, normaliza e filtra todas as evidências de eventos do Windows, BSOD/Dumps
    e Histórico de Confiabilidade sem inventar eventos simulados quando não há ocorrências.
    """
    hours = max(1, int(period_hours or 168))
    raw = raw_override if raw_override is not None else _run_powershell_crash_probe(period_hours=hours)
    if not isinstance(raw, dict):
        raw = {
            "Hostname": platform.node() or "Estacao-Local",
            "SystemEvents": [],
            "ApplicationEvents": [],
            "ReliabilityRecords": [],
            "CrashControlConfig": {},
            "CollectionErrors": (
                []
                if platform.system() == "Windows"
                else ["Ambiente de execução não-Windows detectado: logs nativos EventLog/WMI não aplicáveis sem fixture."]
            ),
        }

    hostname = str(raw.get("Hostname") or platform.node() or "Estacao-Local")
    collection_errors: list[str] = list(raw.get("CollectionErrors") or [])
    if raw.get("PermissionDenied"):
        collection_errors.append("Permissões insuficientes para ler determinados canais do Event Viewer (execute como Administrador para acesso completo ao canal System/Security).")
    if raw.get("CorruptedLog"):
        collection_errors.append("Um ou mais arquivos de log (.evtx) reportaram erro de leitura ou corrupção estrutural.")

    raw_events = list(raw.get("SystemEvents") or []) + list(raw.get("ApplicationEvents") or [])
    normalized_events: list[dict[str, Any]] = []
    bugcheck_incidents: list[dict[str, Any]] = []

    sev_map = {1: "CRÍTICO", 2: "ERRO", 3: "AVISO", 4: "INFORMAÇÃO"}

    for ev in raw_events:
        if not isinstance(ev, dict):
            continue
        eid = int(ev.get("Id") or 0)
        src = str(ev.get("ProviderName") or ev.get("Source") or "Windows").strip()
        lvl_num = int(ev.get("Level") or 3)
        sev_label = str(ev.get("Severity") or sev_map.get(lvl_num, "AVISO")).upper()
        if "CRIT" in sev_label or lvl_num == 1:
            sev_norm = "CRÍTICO"
        elif "ERR" in sev_label or lvl_num == 2:
            sev_norm = "ERRO"
        elif "WARN" in sev_label or "AVIS" in sev_label or lvl_num == 3:
            sev_norm = "AVISO"
        else:
            sev_norm = "INFORMAÇÃO"

        ts = str(ev.get("TimeCreated") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        eq = str(ev.get("MachineName") or hostname)
        orig_msg = str(ev.get("Message") or "Sem descrição textual retornada pelo provedor.").strip()

        interp = interpret_windows_event(src, eid, orig_msg, sev_norm)
        cat = interp["category"]

        # Detecta se é um evento de BugCheck / BSOD
        if cat == "bsod_bugcheck" or (eid == 1001 and "0x" in orig_msg.lower()) or (eid == 41 and "bugcheckcode" in orig_msg.lower() and "bugcheckcode 0" not in orig_msg.lower()):
            bc_code = _extract_bugcheck_code_from_text(orig_msg) or "0x00000000"
            kb_entry = BUGCHECK_KNOWLEDGE_BASE.get(bc_code.lower(), {
                "name": "BUGCHECK_STOP_ERROR",
                "meaning": "Parada crítica do kernel (Tela Azul / BSOD) registrada pelo Windows Error Reporting.",
                "caution": "Verifique os módulos envolvidos no minidump e os eventos de hardware/E/S imediatamente anteriores.",
            })
            bugcheck_incidents.append({
                "timestamp": ts,
                "bugcheck_code": bc_code.upper(),
                "bugcheck_name": kb_entry["name"],
                "technical_meaning": kb_entry["meaning"],
                "diagnostic_caution": kb_entry["caution"],
                "source_event_id": eid,
                "original_message": orig_msg,
            })

        normalized_events.append({
            "timestamp": ts,
            "source": src,
            "event_id": eid,
            "severity": sev_norm,
            "category": cat,
            "equipment": eq,
            "affected_component": interp["component"],
            "original_message": orig_msg,
            "technical_interpretation": interp["technical_interpretation"],
        })

    # Ordena cronologicamente (mais recentes primeiro)
    normalized_events.sort(key=lambda x: x["timestamp"], reverse=True)

    # Aplica filtros solicitados pelo usuário
    sev_f = (severity_filter or "ALL").strip().upper()
    cat_f = (category_filter or "ALL").strip().lower()
    src_f = (source_filter or "").strip().lower()
    eq_f = (equipment_filter or "").strip().lower()

    filtered_events: list[dict[str, Any]] = []
    for item in normalized_events:
        if sev_f not in ("ALL", "TODOS", "") and item["severity"] != sev_f:
            continue
        if cat_f not in ("all", "todos", "") and item["category"].lower() != cat_f:
            continue
        if src_f and src_f not in item["source"].lower():
            continue
        if event_id_filter is not None and int(event_id_filter) > 0 and item["event_id"] != int(event_id_filter):
            continue
        if eq_f and eq_f not in item["equipment"].lower():
            continue
        filtered_events.append(item)

    # Inspeção de arquivos de Minidump e MEMORY.DMP
    dump_info = inspect_dump_files_safely(dump_dirs=dump_dirs_override)
    if dump_info.get("access_errors"):
        collection_errors.extend(dump_info["access_errors"])

    # Padrões de repetição entre códigos de parada BSOD
    bc_counts: dict[str, int] = {}
    for b in bugcheck_incidents:
        code_k = f"{b['bugcheck_code']} ({b['bugcheck_name']})"
        bc_counts[code_k] = bc_counts.get(code_k, 0) + 1

    bsod_guidance: list[str] = []
    if len(bugcheck_incidents) == 0 and dump_info["minidump_files_count"] == 0:
        bsod_guidance.append(
            "Nenhum registro de BugCheck (BSOD) ou arquivo de minidump (.dmp) foi localizado no período/caminhos verificados. "
            "Caso o computador esteja desligando ou reiniciando sem gravar minidump, isso pode indicar: "
            "(1) perda súbita de energia (PSU/tomada/botão Reset); ou (2) falha crítica de escrita no disco onde fica o pagefile.sys (impedindo o Windows de gravar o dump durante a tela azul)."
        )
        bsod_guidance.append(
            "Recomendação para habilitar coleta futura de Minidumps (sem alteração automática): em 'Propriedades do Sistema -> Avançado -> Inicialização e Recuperação -> Configurações', "
            "selecione 'Despejo de memória pequeno (256 KB)' em '%SystemRoot%\\Minidump' e mantenha pelo menos 2 GB de arquivo de paginação (pagefile.sys) no volume C:."
        )
    elif dump_info["minidump_files_count"] > 0 and not dump_info["probable_third_party_or_hw_suspects"]:
        bsod_guidance.append(
            "Arquivo(s) de minidump localizado(s), porém apenas módulos genéricos do kernel do Windows (ex: ntoskrnl.exe) foram identificados nos cabeçalhos. "
            "Como módulos de kernel frequentemente são apenas a vítima da exceção, recomenda-se análise detalhada de símbolos no WinDbg (!analyze -v) combinada com os testes de RAM e armazenamento."
        )

    # Processamento do Histórico de Confiabilidade (Win32_ReliabilityRecords)
    rel_raw = list(raw.get("ReliabilityRecords") or [])
    app_failures: list[dict[str, Any]] = []
    os_hw_failures: list[dict[str, Any]] = []
    installs_updates: list[dict[str, Any]] = []

    for r in rel_raw:
        if not isinstance(r, dict):
            continue
        r_src = str(r.get("SourceName") or "")
        r_msg = str(r.get("Message") or "")
        r_prod = str(r.get("ProductName") or "")
        r_time = str(r.get("TimeGenerated") or "")
        r_id = int(r.get("EventIdentifier") or 0)
        entry = {
            "timestamp": r_time,
            "source": r_src,
            "event_id": r_id,
            "product": r_prod,
            "message": r_msg,
        }
        low_comb = (r_src + " " + r_msg).lower()
        if any(w in low_comb for w in ("install", "instal", "update", "atualiza", "msiinstaller", "windowsupdate")):
            installs_updates.append(entry)
        elif any(w in low_comb for w in ("windows", "bugcheck", "livekernelevent", "hardware", "shut down", "deslig")):
            os_hw_failures.append(entry)
        else:
            app_failures.append(entry)

    # Também incorpora instalações/updates capturados pelos eventos caso Win32_ReliabilityRecords esteja vazio
    for ev in normalized_events:
        if ev["category"] == "update_install":
            installs_updates.append({
                "timestamp": ev["timestamp"],
                "source": ev["source"],
                "event_id": ev["event_id"],
                "product": ev["affected_component"],
                "message": ev["original_message"],
            })

    return {
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hostname": hostname,
        "period_hours": hours,
        "period_days": round(hours / 24.0, 1),
        "filters_applied": {
            "severity": sev_f,
            "category": cat_f,
            "source": src_f,
            "event_id": event_id_filter,
            "equipment": eq_f,
        },
        "total_events_collected": len(normalized_events),
        "filtered_events_count": len(filtered_events),
        "events": filtered_events,
        "all_normalized_events": normalized_events,
        "bsod_analysis": {
            "bugcheck_count": len(bugcheck_incidents),
            "bugcheck_incidents": bugcheck_incidents,
            "recurring_bugcheck_patterns": bc_counts,
            "minidump_files_count": dump_info["minidump_files_count"],
            "minidumps": dump_info["minidumps"],
            "full_memory_dump": dump_info["full_memory_dump"],
            "involved_os_victim_modules": dump_info["involved_os_victim_modules"],
            "probable_third_party_or_hw_suspects": dump_info["probable_third_party_or_hw_suspects"],
            "checked_dump_paths": dump_info["checked_paths"],
            "technical_guidance": bsod_guidance,
        },
        "reliability_history": {
            "source_available": len(rel_raw) > 0 or len(installs_updates) > 0,
            "total_records": len(rel_raw),
            "app_failures_count": len(app_failures),
            "os_hardware_failures_count": len(os_hw_failures),
            "installations_updates_count": len(installs_updates),
            "app_failures": app_failures[:25],
            "os_hardware_failures": os_hw_failures[:25],
            "installations_updates": installs_updates[:25],
        },
        "collection_errors": collection_errors,
    }
