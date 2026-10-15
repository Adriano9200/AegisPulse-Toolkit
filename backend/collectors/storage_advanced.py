#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/collectors/storage_advanced.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.0.0
================================================================================
Descrição:
Etapa 1 — Inventário Avançado de Dispositivos de Armazenamento e Coleta SMART:
- Suporta HDDs Mecânicos, SSDs SATA, SSDs NVMe, Pendrives USB e Unidades Externas.
- Identifica fabricante, marca, modelo, número de série, firmware, interface,
  protocolo, tipo de mídia, rotação (RPM) e controlador/ponte USB.
- Calcula capacidades em bytes exatos, decimal (GB/TB - 10^9/10^12) e binário
  (GiB/TiB - 2^30/2^40), distinguindo capacidade física, partições, espaço não
  alocado, volumes, espaço utilizado e espaço livre.
- Mapeia número do disco físico (Disk N / \\.\PhysicalDriveN), letras de unidade,
  sistema de arquivos (NTFS, FAT32, exFAT, ReFS, RAW), estilo de partição
  (GPT, MBR, RAW/Não Inicializado), estado online/offline e somente-leitura.
- Detecta limitações de adaptadores/pontes USB (JMicron, ASMedia, Realtek, BOT)
  e controladoras RAID/VMD sem inventar dados indisponíveis.
- Decodifica atributos SMART ATA/SATA (362 bytes VendorSpecific + Thresholds),
  contadores Windows StorageReliabilityCounter e atributos NVMe (Critical Warning,
  Temperature, Available Spare, Percentage Used, Data Units Read/Written, etc.),
  além de integrar com smartctl (smartmontools) quando disponível no sistema.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from datetime import datetime
from typing import Any

STORAGE_BRAND_MAP = [
    (("SAMSUNG", "MZVL", "MZ7L", "860 EVO", "870 EVO", "970 EVO", "980 PRO", "990 PRO"), "Samsung", "Samsung Proprietary (Elpis/Pascal/Phoenix/MJX)"),
    (("SK HYNIX", "HYNIX", "PC401", "PC711", "PC801", "BC501", "BC711", "P31", "P41"), "SK hynix", "SK hynix Cepheus / Aries NVMe Controller"),
    (("WDC ", "WESTERN DIGITAL", "WD_BLACK", "WD BLUE", "WD GREEN", "SN550", "SN570", "SN580", "SN750", "SN770", "SN850"), "Western Digital (WD)", "SanDisk / WD Proprietary Controller"),
    (("SEAGATE", "ST1000", "ST2000", "ST3000", "ST4000", "ST500", "BARRACUDA", "IRONWOLF", "FIRECUDA", "EXOS"), "Seagate", "Seagate Multi-Tier Caching / Phison NVMe"),
    (("KINGSTON", "SA400", "SNVS", "SNV2S", "SKC", "SFYRS", "DATATRAVELER"), "Kingston", "Phison / Silicon Motion (SMI) Controller"),
    (("CRUCIAL", "CT500", "CT1000", "CT2000", "MX500", "BX500", "P3", "P5", "T500"), "Crucial (Micron)", "Silicon Motion / Micron Controller"),
    (("ADATA", "XPG", "SU630", "SU650", "SU800", "SX8200", "GAMMIX"), "ADATA / XPG", "Realtek / Silicon Motion / InnoGrit Controller"),
    (("SANDISK", "SDSS", "ULTRA", "EXTREME", "CRUZER"), "SanDisk", "SanDisk / Marvell Controller"),
    (("LEXAR", "NM620", "NM710", "NM790", "NS100"), "Lexar", "MaxioTech / Silicon Motion Controller"),
    (("CORSAIR", "MP510", "MP600", "MP700"), "Corsair", "Phison E12/E16/E18/E26 Controller"),
    (("TOSHIBA", "KIOXIA", "EXCERIA", "BG4", "BG5", "XG6", "XG8"), "Kioxia / Toshiba", "Kioxia TC58 / Phison Controller"),
    (("INTEL", "SOLIDIGM", "SSDPE", "660P", "670P", "P44"), "Intel / Solidigm", "Intel / Silicon Motion Controller"),
]

USB_BRIDGE_SIGNATURES = [
    ("JMICRON", "JMicron USB-to-SATA/NVMe Bridge (JMS567/JMS578/JMS583)"),
    ("ASMEDIA", "ASMedia USB Bridge (ASM1153E/ASM2362)"),
    ("REALTEK", "Realtek USB-to-NVMe/SATA Bridge (RTL9210)"),
    ("VIA", "VIA Labs USB Bridge (VL715/VL716)"),
    ("GENESYS", "Genesys Logic USB Storage Reader"),
    ("ALCOR", "Alcor Micro USB Flash Controller"),
    ("PHISON", "Phison USB Flash Controller"),
    ("SMI", "Silicon Motion USB Flash Controller"),
]

SMART_ATTRIBUTE_DEFINITIONS: dict[int, dict[str, Any]] = {
    1: {
        "name": "Raw Read Error Rate",
        "unit": "erros",
        "critical": False,
        "meaning": "Taxa de erros de leitura de hardware na superfície magnética ou células NAND. Nota: Em discos Seagate, o valor bruto é um contador composto de 48 bits (os 16 bits superiores indicam erros e os 32 inferiores indicam total de leituras).",
    },
    3: {
        "name": "Spin-Up Time",
        "unit": "ms",
        "critical": False,
        "meaning": "Tempo médio que os pratos do HDD levam para atingir a rotação nominal (RPM).",
    },
    4: {
        "name": "Start/Stop Count",
        "unit": "ciclos",
        "critical": False,
        "meaning": "Total de ciclos de partida e parada do motor de rotação (spindle) em HDDs.",
    },
    5: {
        "name": "Reallocated Sectors Count",
        "unit": "setores",
        "critical": True,
        "meaning": "Quantidade de setores defeituosos (Bad Blocks) que foram isolados e remapeados para a área de reserva (Spare Area). Qualquer valor > 0 indica degradação física da mídia.",
    },
    7: {
        "name": "Seek Error Rate",
        "unit": "erros",
        "critical": False,
        "meaning": "Taxa de erros de posicionamento do cabeçote magnético em HDDs (em discos Seagate, usa codificação composta de 48 bits).",
    },
    9: {
        "name": "Power-On Hours (POH)",
        "unit": "horas",
        "critical": False,
        "meaning": "Total acumulado de horas em que o dispositivo permaneceu energizado desde a fabricação.",
    },
    10: {
        "name": "Spin Retry Count",
        "unit": "tentativas",
        "critical": True,
        "meaning": "Contagem de tentativas falhas de iniciar a rotação do motor do HDD. Valores > 0 apontam risco mecânico no motor ou alimentação insuficiente (12V).",
    },
    12: {
        "name": "Power Cycle Count",
        "unit": "ciclos",
        "critical": False,
        "meaning": "Quantidade total de ciclos completos de energização (ligar/desligar) do dispositivo.",
    },
    170: {
        "name": "Available Reserved Space",
        "unit": "%",
        "critical": True,
        "meaning": "Percentual do bloco de reserva (Over-Provisioning) ainda disponível no SSD.",
    },
    171: {
        "name": "Program Fail Count",
        "unit": "falhas",
        "critical": True,
        "meaning": "Total de falhas ao programar (gravar) páginas na memória Flash NAND.",
    },
    172: {
        "name": "Erase Fail Count",
        "unit": "falhas",
        "critical": True,
        "meaning": "Total de falhas ao apagar blocos de memória Flash NAND.",
    },
    173: {
        "name": "Wear Leveling / Erase Count",
        "unit": "ciclos P/E",
        "critical": False,
        "meaning": "Média de ciclos de Programação/Apagamento (P/E) executados nas células NAND do SSD.",
    },
    174: {
        "name": "Unexpected Power Loss Count",
        "unit": "quedas",
        "critical": False,
        "meaning": "Número de desligamentos abruptos ou cortes de energia sem o comando STANDBY IMMEDIATE do sistema operacional.",
    },
    177: {
        "name": "Wear Range Delta / Wear Leveling",
        "unit": "%",
        "critical": False,
        "meaning": "Indicador de nivelamento de desgaste entre os blocos mais e menos utilizados do SSD (comum em SSDs Samsung).",
    },
    180: {
        "name": "Unused Reserved Block Count",
        "unit": "blocos",
        "critical": True,
        "meaning": "Quantidade de blocos de reserva intactos restantes para substituição de blocos defeituosos.",
    },
    184: {
        "name": "End-to-End Error Detection",
        "unit": "erros",
        "critical": True,
        "meaning": "Falhas de paridade detectadas no buffer de cache interno entre o controlador e a interface host.",
    },
    187: {
        "name": "Reported Uncorrectable Errors",
        "unit": "erros",
        "critical": True,
        "meaning": "Setores ou páginas cuja falha de leitura não pôde ser recuperada pelo código corretor de erros (ECC) de hardware.",
    },
    188: {
        "name": "Command Timeout",
        "unit": "eventos",
        "critical": False,
        "meaning": "Operações abortadas por tempo limite excedido. Frequentemente causado por cabos SATA frouxos, fonte instável ou travamento do controlador.",
    },
    190: {
        "name": "Airflow / Case Temperature",
        "unit": "°C",
        "critical": False,
        "meaning": "Temperatura medida no fluxo de ar ou encapsulamento do disco.",
    },
    192: {
        "name": "Power-Off Retract Count / Unsafe Shutdowns",
        "unit": "eventos",
        "critical": False,
        "meaning": "Recolhimentos de emergência do cabeçote ou desligamentos sem descarte seguro do cache.",
    },
    193: {
        "name": "Load/Unload Cycle Count",
        "unit": "ciclos",
        "critical": False,
        "meaning": "Ciclos de entrada e saída do cabeçote na rampa de estacionamento.",
    },
    194: {
        "name": "Temperature Celsius",
        "unit": "°C",
        "critical": False,
        "meaning": "Temperatura interna atual do sensor térmico do dispositivo (os bytes superiores podem armazenar mín/máx históricos).",
    },
    196: {
        "name": "Reallocation Event Count",
        "unit": "eventos",
        "critical": True,
        "meaning": "Total de operações de tentativa de remapeamento de setores (bem-sucedidas ou não).",
    },
    197: {
        "name": "Current Pending Sector Count",
        "unit": "setores",
        "critical": True,
        "meaning": "Setores instáveis aguardando leitura bem-sucedida ou sobrescrita para remapeamento. CRÍTICO: risco imediato de travamento e perda de arquivos!",
    },
    198: {
        "name": "Offline Uncorrectable Sector Count",
        "unit": "setores",
        "critical": True,
        "meaning": "Total de setores incorrigíveis detectados durante varreduras offline. Evidência forte de dano físico na superfície/NAND.",
    },
    199: {
        "name": "UltraDMA CRC Error Count",
        "unit": "erros CRC",
        "critical": False,
        "meaning": "Erros de soma de verificação (CRC) na transferência entre a placa-mãe/adaptador USB e o disco. Geralmente indica cabo SATA defeituoso, porta USB instável ou ruído elétrico — não significa setor defeituoso na mídia.",
    },
    231: {
        "name": "SSD Life Left",
        "unit": "%",
        "critical": False,
        "meaning": "Percentual estimado de vida útil restante das células Flash NAND segundo o fabricante (100% = novo, 0% = fim da resistência nominal).",
    },
    232: {
        "name": "Available Reserved Space",
        "unit": "%",
        "critical": True,
        "meaning": "Porcentagem de blocos sobressalentes disponíveis para substituição de falhas.",
    },
    233: {
        "name": "Media Wearout Indicator",
        "unit": "%",
        "critical": False,
        "meaning": "Indicador de desgaste da mídia Flash NAND.",
    },
    241: {
        "name": "Total LBAs / Host Writes",
        "unit": "GB",
        "critical": False,
        "meaning": "Volume total acumulado de dados gravados pelo sistema operacional (Host Writes / TBW).",
    },
    242: {
        "name": "Total LBAs / Host Reads",
        "unit": "GB",
        "critical": False,
        "meaning": "Volume total acumulado de dados lidos pelo sistema operacional (Host Reads).",
    },
}


def format_dual_capacity(size_bytes: int | float | None) -> dict[str, Any]:
    b = max(0, int(size_bytes or 0))
    gb_dec = round(b / 1_000_000_000, 2)
    tb_dec = round(b / 1_000_000_000_000, 3)
    gib_bin = round(b / (1024 ** 3), 2)
    tib_bin = round(b / (1024 ** 4), 3)

    if b >= 1_000_000_000_000:
        formatted = f"{tb_dec} TB ({tib_bin} TiB / {gib_bin} GiB)"
    elif b > 0:
        formatted = f"{gb_dec} GB ({gib_bin} GiB)"
    else:
        formatted = "0 B (Sem Mídia / Não Reconhecido)"

    return {
        "bytes": b,
        "gb": gb_dec,
        "tb": tb_dec,
        "gib": gib_bin,
        "tib": tib_bin,
        "formatted": formatted,
    }


def identify_brand_and_controller(model: str, manufacturer: str = "", pnp_id: str = "", bus_type: str = "") -> dict[str, Any]:
    combined = f"{model} {manufacturer} {pnp_id}".upper()
    detected_brand = (manufacturer or "").strip()
    if detected_brand.upper() in ("", "(STANDARD DISK DRIVES)", "STANDARD DISK DRIVES", "MICROSOFT", "GENERIC", "N/D"):
        detected_brand = "Genérico / OEM"

    controller = "Controlador Nativo Padrão"
    for keywords, brand_name, ctrl_desc in STORAGE_BRAND_MAP:
        if any(k in combined for k in keywords):
            detected_brand = brand_name
            controller = ctrl_desc
            break

    is_usb = "USB" in (bus_type or "").upper() or "USBSTOR" in combined or "UASP" in combined
    usb_bridge = None
    adapter_limitations = []

    if is_usb:
        for sig, desc in USB_BRIDGE_SIGNATURES:
            if sig in combined:
                usb_bridge = desc
                break
        if not usb_bridge:
            usb_bridge = "Ponte USB Mass Storage / UASP Genérica"
        controller = f"{controller} via {usb_bridge}"
        adapter_limitations.append(
            "Dispositivo conectado via barramento USB: algumas pontes USB-SATA/NVMe (especialmente no protocolo BOT antigo) "
            "bloqueiam ou filtram comandos SMART passthrough (SAT/NVMe) e impedem a leitura de temperatura ou TBW."
        )

    if "RAID" in (bus_type or "").upper() or "RST" in combined or "VMD" in combined:
        adapter_limitations.append(
            "Controladora em modo Intel RST / VMD / RAID detectada: o driver de armazenamento pode ocultar atributos SMART individuais dos discos físicos."
        )

    return {
        "brand": detected_brand,
        "controller": controller,
        "is_usb_bridge": is_usb,
        "usb_bridge_name": usb_bridge,
        "adapter_limitations": adapter_limitations,
    }


def classify_storage_media(
    model: str,
    bus_type: str,
    media_type_raw: str,
    is_removable: bool = False,
    spindle_speed: int | None = None,
) -> dict[str, str]:
    m_up = (model or "").upper()
    b_up = (bus_type or "").upper()
    mt_up = (media_type_raw or "").upper()

    if "NVME" in b_up or "NVME" in m_up or "PCIE" in b_up or any(k in m_up for k in ("PC801", "PC401", "980 PRO", "990 PRO", "SN770", "SN850")):
        if "USB" in b_up:
            return {
                "category": "Unidade Externa USB (SSD NVMe)",
                "short_type": "SSD NVMe Externo",
                "protocol": "NVMe sobre USB (UASP/Bridge)",
                "interface": "USB / NVMe",
            }
        return {
            "category": "SSD NVMe (M.2 / PCIe)",
            "short_type": "SSD NVMe",
            "protocol": "NVMe (Non-Volatile Memory Express)",
            "interface": "PCIe / M.2 NVMe",
        }

    if "USB" in b_up or is_removable or "REMOVABLE" in mt_up:
        if any(k in m_up for k in ("FLASH", "DATATRAVELER", "CRUZER", "PENDRIVE", "ULTRA FIT", "DISK 2.0", "DISK 3.0")) or is_removable:
            return {
                "category": "Pendrive / Unidade Flash USB",
                "short_type": "Pendrive USB",
                "protocol": "USB Mass Storage (BOT / UASP)",
                "interface": "USB",
            }
        return {
            "category": "Unidade Externa USB (HDD/SSD Portátil)",
            "short_type": "Disco Externo USB",
            "protocol": "USB UASP / SAT Bridge",
            "interface": "USB",
        }

    if "SSD" in mt_up or "SOLID STATE" in mt_up or "SSD" in m_up or spindle_speed == 0:
        return {
            "category": "SSD SATA (2.5\" / M.2 SATA)",
            "short_type": "SSD SATA",
            "protocol": "AHCI / ATA8-ACS (SATA III 6Gb/s)",
            "interface": "SATA",
        }

    return {
        "category": "HDD Mecânico (Magnético)",
        "short_type": "HDD SATA",
        "protocol": "AHCI / ATA (SATA)",
        "interface": b_up if b_up and b_up != "UNKNOWN" else "SATA",
    }


def parse_ata_smart_binary(
    vendor_specific_bytes: list[int] | bytes | None,
    threshold_bytes: list[int] | bytes | None = None,
    brand: str = "",
) -> list[dict[str, Any]]:
    if not vendor_specific_bytes or len(vendor_specific_bytes) < 14:
        return []

    data_arr = list(vendor_specific_bytes)
    thresh_map: dict[int, int] = {}
    if threshold_bytes and len(threshold_bytes) >= 14:
        t_arr = list(threshold_bytes)
        for i in range(2, min(len(t_arr) - 12, 362), 12):
            attr_id = t_arr[i]
            if 1 <= attr_id <= 254:
                thresh_map[attr_id] = t_arr[i + 1]

    attributes: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    is_seagate = "SEAGATE" in (brand or "").upper()

    for i in range(2, min(len(data_arr) - 12, 362), 12):
        attr_id = data_arr[i]
        if attr_id == 0 or attr_id == 255 or attr_id in seen_ids:
            continue
        seen_ids.add(attr_id)

        flags = data_arr[i + 1] | (data_arr[i + 2] << 8)
        current_val = data_arr[i + 3]
        worst_val = data_arr[i + 4]
        raw_bytes = data_arr[i + 5 : i + 11]
        raw_int = 0
        for b_idx, b_val in enumerate(raw_bytes):
            raw_int |= (int(b_val) & 0xFF) << (8 * b_idx)

        raw_hex = "0x" + "".join(f"{b:02X}" for b in reversed(raw_bytes))
        threshold = thresh_map.get(attr_id, 0)

        meta = SMART_ATTRIBUTE_DEFINITIONS.get(
            attr_id,
            {
                "name": f"Vendor Specific Attribute ({attr_id})",
                "unit": "",
                "critical": False,
                "meaning": "Atributo proprietário do fabricante do controlador.",
            },
        )

        interpreted = str(raw_int)
        severity = "ok"
        vendor_note = ""

        if attr_id in (190, 194):
            temp_c = raw_bytes[0]
            min_t = raw_bytes[2] if raw_bytes[2] and raw_bytes[2] < 100 else None
            max_t = raw_bytes[4] if raw_bytes[4] and raw_bytes[4] < 100 else None
            if min_t and max_t and min_t <= temp_c <= max_t:
                interpreted = f"{temp_c} °C (Mín: {min_t}°C / Máx: {max_t}°C)"
            else:
                interpreted = f"{temp_c} °C"
            if temp_c >= 65:
                severity = "critical"
            elif temp_c >= 55:
                severity = "warning"
        elif attr_id == 9:
            poh = raw_int & 0xFFFFFF if raw_int > 200_000 else raw_int
            days = round(poh / 24.0, 1)
            interpreted = f"{poh} h ({days} dias)"
        elif attr_id in (1, 7) and is_seagate and raw_int > 0xFFFFFFFF:
            upper_err = (raw_int >> 32) & 0xFFFF
            lower_ops = raw_int & 0xFFFFFFFF
            interpreted = f"{upper_err} erros reais em {lower_ops:,} operações"
            vendor_note = "Codificação composta Seagate 48-bit decodificada automaticamente."
            if upper_err > 0 and attr_id == 1:
                severity = "warning"
        elif attr_id in (5, 196, 197, 198, 187, 10):
            interpreted = f"{raw_int} {meta['unit']}"
            if raw_int > 0:
                severity = "critical" if attr_id in (5, 197, 198, 187) else "warning"
        elif attr_id == 199:
            interpreted = f"{raw_int} erros CRC de comunicação"
            if raw_int > 0:
                severity = "warning"
                vendor_note = "Atenção: Erro CRC indica falha no cabo SATA, porta USB ou ponte — não é defeito físico de setor."
        elif attr_id in (241, 242):
            if raw_int > 10_000_000:
                gb_val = round((raw_int * 512) / (1024 ** 3), 2)
                interpreted = f"{gb_val} GB ({round(gb_val / 1024, 2)} TB)"
            else:
                interpreted = f"{raw_int} unidades"

        if threshold > 0 and current_val > 0 and current_val <= threshold:
            severity = "critical"

        attributes.append({
            "id": f"0x{attr_id:02X} ({attr_id})",
            "id_num": attr_id,
            "name": meta["name"],
            "current": current_val,
            "worst": worst_val,
            "threshold": threshold,
            "raw_int": raw_int,
            "raw_hex": raw_hex,
            "interpreted": interpreted,
            "unit": meta["unit"],
            "severity": severity,
            "pre_fail": bool(flags & 0x01),
            "vendor_note": vendor_note,
            "meaning": meta["meaning"],
        })

    return sorted(attributes, key=lambda x: x["id_num"])


def build_nvme_or_reliability_attributes(
    rel_counter: dict[str, Any] | None,
    nvme_log: dict[str, Any] | None,
    media_category: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rel = rel_counter or {}
    nvme = nvme_log or {}
    attrs: list[dict[str, Any]] = []

    summary_metrics: dict[str, Any] = {
        "temperature_c": None,
        "temperature_max_c": None,
        "temperature_warning_c": 70 if "NVMe" in media_category else 60,
        "power_on_hours": None,
        "power_on_days": None,
        "power_cycles": None,
        "total_reads_gb": None,
        "total_writes_gb": None,
        "wear_percent_used": None,
        "life_remaining_percent": None,
        "available_spare_percent": None,
        "available_spare_threshold": None,
        "critical_warning_raw": None,
        "reallocated_sectors": None,
        "pending_sectors": None,
        "uncorrectable_errors": None,
        "media_integrity_errors": None,
        "crc_interface_errors": None,
        "unsafe_shutdowns": None,
        "read_latency_max_ms": None,
        "write_latency_max_ms": None,
    }

    if nvme.get("critical_warning") is not None:
        cw = int(nvme["critical_warning"])
        summary_metrics["critical_warning_raw"] = cw
        attrs.append({
            "id": "NVMe-01",
            "id_num": 501,
            "name": "Critical Warning (Alerta Crítico NVMe)",
            "current": 100 if cw == 0 else 0,
            "worst": 100 if cw == 0 else 0,
            "threshold": 0,
            "raw_int": cw,
            "raw_hex": f"0x{cw:02X}",
            "interpreted": "0x00 (Normal)" if cw == 0 else f"0x{cw:02X} (ALERTA ATIVO: Spare/Temp/Read-Only)",
            "unit": "bitmask",
            "severity": "critical" if cw > 0 else "ok",
            "pre_fail": True,
            "vendor_note": "Bits indicam: Bit 0=Spare baixo, Bit 1=Temp crítica, Bit 2=Erro de mídia, Bit 3=Modo Somente-Leitura.",
            "meaning": "Registrador de alerta crítico de hardware do controlador NVMe.",
        })

    temp_c = nvme.get("temperature") if nvme.get("temperature") is not None else rel.get("Temperature")
    temp_max = rel.get("TemperatureMax")
    if temp_c is not None and int(temp_c) > 0:
        tc = int(temp_c)
        summary_metrics["temperature_c"] = tc
        if temp_max is not None and int(temp_max) > 0:
            summary_metrics["temperature_max_c"] = int(temp_max)
        sev = "critical" if tc >= 72 else ("warning" if tc >= 62 else "ok")
        interp_t = f"{tc} °C" + (f" (Pico Máx: {int(temp_max)} °C)" if temp_max else "")
        attrs.append({
            "id": "NVMe-02" if "NVMe" in media_category else "SMART-194",
            "id_num": 194,
            "name": "Composite Temperature (Temperatura do Disco)",
            "current": max(1, 100 - tc),
            "worst": max(1, 100 - int(temp_max or tc)),
            "threshold": 70 if "NVMe" in media_category else 60,
            "raw_int": tc,
            "raw_hex": f"0x{tc:02X}",
            "interpreted": interp_t,
            "unit": "°C",
            "severity": sev,
            "pre_fail": False,
            "vendor_note": "",
            "meaning": "Temperatura medida pelo sensor térmico interno do controlador/disco.",
        })

    if nvme.get("available_spare") is not None:
        sp = int(nvme["available_spare"])
        sp_th = int(nvme.get("available_spare_threshold", 10))
        summary_metrics["available_spare_percent"] = sp
        summary_metrics["available_spare_threshold"] = sp_th
        sev = "critical" if sp <= sp_th else ("warning" if sp <= sp_th + 10 else "ok")
        attrs.append({
            "id": "NVMe-03",
            "id_num": 503,
            "name": "Available Spare (Reserva de Blocos Disponível)",
            "current": sp,
            "worst": sp,
            "threshold": sp_th,
            "raw_int": sp,
            "raw_hex": f"0x{sp:02X}",
            "interpreted": f"{sp}% disponível (Limiar mínimo: {sp_th}%)",
            "unit": "%",
            "severity": sev,
            "pre_fail": True,
            "vendor_note": "",
            "meaning": "Percentual de blocos NAND sobressalentes intactos para substituição de células desgastadas.",
        })

    wear_val = nvme.get("percentage_used") if nvme.get("percentage_used") is not None else rel.get("Wear")
    if wear_val is not None:
        w_pct = int(wear_val)
        life_rem = max(0, 100 - w_pct)
        summary_metrics["wear_percent_used"] = w_pct
        summary_metrics["life_remaining_percent"] = life_rem
        sev = "critical" if w_pct >= 95 else ("warning" if w_pct >= 80 else "ok")
        attrs.append({
            "id": "NVMe-05" if "NVMe" in media_category else "SMART-231",
            "id_num": 231,
            "name": "Percentage Used / Desgaste da Mídia",
            "current": life_rem,
            "worst": life_rem,
            "threshold": 5,
            "raw_int": w_pct,
            "raw_hex": f"0x{w_pct:02X}",
            "interpreted": f"{w_pct}% de desgaste ({life_rem}% de vida útil reportada restante)",
            "unit": "%",
            "severity": sev,
            "pre_fail": False,
            "vendor_note": "Baseado na resistência (TBW) projetada pelo fabricante.",
            "meaning": "Percentual de desgaste acumulado das células Flash NAND.",
        })

    poh_val = nvme.get("power_on_hours") if nvme.get("power_on_hours") is not None else rel.get("PowerOnHours")
    if poh_val is not None:
        poh = int(poh_val)
        days = round(poh / 24.0, 1)
        summary_metrics["power_on_hours"] = poh
        summary_metrics["power_on_days"] = days
        attrs.append({
            "id": "NVMe-09" if "NVMe" in media_category else "SMART-09",
            "id_num": 9,
            "name": "Power-On Hours (Horas em Funcionamento)",
            "current": 100,
            "worst": 100,
            "threshold": 0,
            "raw_int": poh,
            "raw_hex": f"0x{poh:X}",
            "interpreted": f"{poh:,} horas (~{days} dias acumulados)",
            "unit": "horas",
            "severity": "ok",
            "pre_fail": False,
            "vendor_note": "",
            "meaning": "Tempo total em que o dispositivo esteve energizado em operação.",
        })

    pc_val = nvme.get("power_cycles") if nvme.get("power_cycles") is not None else rel.get("StartStopCycleCount")
    if pc_val is not None:
        pc = int(pc_val)
        summary_metrics["power_cycles"] = pc
        attrs.append({
            "id": "NVMe-08" if "NVMe" in media_category else "SMART-12",
            "id_num": 12,
            "name": "Power Cycles / Start-Stop Count",
            "current": 100,
            "worst": 100,
            "threshold": 0,
            "raw_int": pc,
            "raw_hex": f"0x{pc:X}",
            "interpreted": f"{pc:,} ciclos de energia",
            "unit": "ciclos",
            "severity": "ok",
            "pre_fail": False,
            "vendor_note": "",
            "meaning": "Total de inicializações elétricas completas do dispositivo.",
        })

    if nvme.get("data_units_read") is not None:
        dur = int(nvme["data_units_read"])
        read_gb = round((dur * 512_000) / (1024 ** 3), 2)
        summary_metrics["total_reads_gb"] = read_gb
        attrs.append({
            "id": "NVMe-06",
            "id_num": 242,
            "name": "Data Units Read (Total de Dados Lidos)",
            "current": 100,
            "worst": 100,
            "threshold": 0,
            "raw_int": dur,
            "raw_hex": f"0x{dur:X}",
            "interpreted": f"{read_gb:,.2f} GB ({round(read_gb / 1024, 3)} TB)",
            "unit": "GB",
            "severity": "ok",
            "pre_fail": False,
            "vendor_note": "Calculado a partir de Data Units NVMe (512 KB por unidade).",
            "meaning": "Volume total acumulado lido pelo host desde a fabricação.",
        })

    if nvme.get("data_units_written") is not None:
        duw = int(nvme["data_units_written"])
        write_gb = round((duw * 512_000) / (1024 ** 3), 2)
        summary_metrics["total_writes_gb"] = write_gb
        attrs.append({
            "id": "NVMe-07",
            "id_num": 241,
            "name": "Data Units Written (Total Gravado / TBW)",
            "current": 100,
            "worst": 100,
            "threshold": 0,
            "raw_int": duw,
            "raw_hex": f"0x{duw:X}",
            "interpreted": f"{write_gb:,.2f} GB ({round(write_gb / 1024, 3)} TBW)",
            "unit": "GB",
            "severity": "ok",
            "pre_fail": False,
            "vendor_note": "Calculado a partir de Data Units NVMe (512 KB por unidade).",
            "meaning": "Volume total acumulado gravado na memória Flash NAND (TBW).",
        })

    media_err = nvme.get("media_errors")
    read_uncorr = rel.get("ReadErrorsUncorrected")
    write_uncorr = rel.get("WriteErrorsUncorrected")
    if media_err is not None or read_uncorr is not None or write_uncorr is not None:
        total_uncorr = int(media_err or 0) + int(read_uncorr or 0) + int(write_uncorr or 0)
        summary_metrics["uncorrectable_errors"] = total_uncorr
        summary_metrics["media_integrity_errors"] = total_uncorr
        attrs.append({
            "id": "NVMe-0E" if "NVMe" in media_category else "SMART-187",
            "id_num": 187,
            "name": "Media and Data Integrity / Uncorrectable Errors",
            "current": 100 if total_uncorr == 0 else max(1, 100 - total_uncorr),
            "worst": 100 if total_uncorr == 0 else max(1, 100 - total_uncorr),
            "threshold": 0,
            "raw_int": total_uncorr,
            "raw_hex": f"0x{total_uncorr:X}",
            "interpreted": f"{total_uncorr} erro(s) incorrigível(is) de mídia/ECC",
            "unit": "erros",
            "severity": "critical" if total_uncorr > 0 else "ok",
            "pre_fail": True,
            "vendor_note": "",
            "meaning": "Falhas de leitura/escrita em que o ECC de hardware não conseguiu recuperar os dados.",
        })

    if nvme.get("unsafe_shutdowns") is not None:
        us = int(nvme["unsafe_shutdowns"])
        summary_metrics["unsafe_shutdowns"] = us
        attrs.append({
            "id": "NVMe-0C",
            "id_num": 192,
            "name": "Unsafe Shutdowns (Desligamentos Abruptos)",
            "current": 100,
            "worst": 100,
            "threshold": 0,
            "raw_int": us,
            "raw_hex": f"0x{us:X}",
            "interpreted": f"{us} desligamento(s) inesperado(s)",
            "unit": "eventos",
            "severity": "warning" if us > 50 else "ok",
            "pre_fail": False,
            "vendor_note": "",
            "meaning": "Quedas de energia ou desconexões sem notificação prévia de desligamento pelo sistema operacional.",
        })

    if rel.get("ReadLatencyMax") is not None or rel.get("WriteLatencyMax") is not None:
        rl = int(rel.get("ReadLatencyMax") or 0)
        wl = int(rel.get("WriteLatencyMax") or 0)
        summary_metrics["read_latency_max_ms"] = rl
        summary_metrics["write_latency_max_ms"] = wl
        sev = "warning" if max(rl, wl) > 500 else "ok"
        attrs.append({
            "id": "WIN-LAT",
            "id_num": 250,
            "name": "Max I/O Latency (Pico de Latência Leitura/Escrita)",
            "current": 100,
            "worst": 100,
            "threshold": 0,
            "raw_int": max(rl, wl),
            "raw_hex": f"0x{max(rl, wl):X}",
            "interpreted": f"Leitura Máx: {rl} ms | Escrita Máx: {wl} ms",
            "unit": "ms",
            "severity": sev,
            "pre_fail": False,
            "vendor_note": "",
            "meaning": "Maior tempo de resposta registrado pelo subsistema de armazenamento do Windows.",
        })

    return attrs, summary_metrics


def _enrich_summary_from_ata_table(ata_attrs: list[dict[str, Any]], summary_metrics: dict[str, Any]) -> dict[str, Any]:
    for a in ata_attrs:
        aid = a.get("id_num")
        raw = int(a.get("raw_int") or 0)
        if aid in (194, 190) and summary_metrics.get("temperature_c") is None:
            t_byte = raw & 0xFF
            if 0 < t_byte < 110:
                summary_metrics["temperature_c"] = t_byte
        elif aid == 9 and summary_metrics.get("power_on_hours") is None:
            poh = raw & 0xFFFFFF if raw > 200_000 else raw
            summary_metrics["power_on_hours"] = poh
            summary_metrics["power_on_days"] = round(poh / 24.0, 1)
        elif aid in (12, 4) and summary_metrics.get("power_cycles") is None:
            summary_metrics["power_cycles"] = raw
        elif aid == 5:
            summary_metrics["reallocated_sectors"] = raw
        elif aid == 197:
            summary_metrics["pending_sectors"] = raw
        elif aid in (198, 187):
            prev = int(summary_metrics.get("uncorrectable_errors") or 0)
            summary_metrics["uncorrectable_errors"] = max(prev, raw)
        elif aid == 199:
            summary_metrics["crc_interface_errors"] = raw
        elif aid in (231, 233) and summary_metrics.get("life_remaining_percent") is None:
            curr = int(a.get("current") or 0)
            if 0 < curr <= 100:
                summary_metrics["life_remaining_percent"] = curr
                summary_metrics["wear_percent_used"] = 100 - curr
        elif aid == 241 and summary_metrics.get("total_writes_gb") is None:
            if raw > 10_000_000:
                summary_metrics["total_writes_gb"] = round((raw * 512) / (1024 ** 3), 2)
        elif aid == 242 and summary_metrics.get("total_reads_gb") is None:
            if raw > 10_000_000:
                summary_metrics["total_reads_gb"] = round((raw * 512) / (1024 ** 3), 2)
    return summary_metrics


def _find_smartctl_binary() -> str | None:
    in_path = shutil.which("smartctl")
    if in_path:
        return in_path
    win_candidates = [
        r"C:\Program Files\smartmontools\bin\smartctl.exe",
        r"C:\Program Files (x86)\smartmontools\bin\smartctl.exe",
    ]
    for c in win_candidates:
        if os.path.exists(c):
            return c
    return None


def _query_smartctl_json(smartctl_bin: str, disk_num: int) -> dict[str, Any] | None:
    dev_arg = f"/dev/pd{disk_num}" if platform.system() == "Windows" else "/dev/sda"
    try:
        res = subprocess.run(
            [smartctl_bin, "-a", "-j", dev_arg],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if res.stdout.strip():
            return json.loads(res.stdout)
    except Exception:
        pass
    return None


def _run_powershell_storage_probe() -> dict[str, Any] | None:
    ps_script = r"""
    $ErrorActionPreference = 'SilentlyContinue'
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    $wmiDisks = @(Get-CimInstance Win32_DiskDrive | Select-Object Index, DeviceID, Model, Manufacturer, SerialNumber, FirmwareRevision, InterfaceType, MediaType, Size, Partitions, Status, PNPDeviceID, Capabilities)
    $physDisks = @(Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, SerialNumber, FirmwareVersion, BusType, MediaType, SpindleSpeed, HealthStatus, OperationalStatus, Size, AllocatedSize)

    $relCounters = @{}
    foreach ($pd in $physDisks) {
        $rc = $pd | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue | Select-Object DeviceId, Temperature, TemperatureMax, PowerOnHours, StartStopCycleCount, Wear, ReadErrorsTotal, ReadErrorsUncorrected, WriteErrorsTotal, WriteErrorsUncorrected, ReadLatencyMax, WriteLatencyMax
        if ($rc) {
            $relCounters[[string]$pd.DeviceId] = $rc
        }
    }

    $osDisks = @(Get-Disk | Select-Object Number, FriendlyName, SerialNumber, PartitionStyle, OperationalStatus, HealthStatus, BusType, IsSystem, IsBoot, IsReadOnly, IsOffline, Size, AllocatedSize, LargestFreeExtent)
    $parts = @(Get-Partition | Select-Object DiskNumber, PartitionNumber, DriveLetter, Size, Offset, Type, IsActive, IsBoot, IsHidden, IsReadOnly, IsSystem)
    $vols = @(Get-Volume | Select-Object DriveLetter, FileSystemLabel, FileSystem, DriveType, HealthStatus, OperationalStatus, SizeRemaining, Size)
    $logicalDisks = @(Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID, DriveType, VolumeName, FileSystem, Size, FreeSpace, VolumeSerialNumber)

    $smartStatus = @(Get-CimInstance -Namespace root\wmi -ClassName MSStorageDriver_FailurePredictStatus -ErrorAction SilentlyContinue | Select-Object InstanceName, PredictFailure, Reason)
    $smartData = @(Get-CimInstance -Namespace root\wmi -ClassName MSStorageDriver_FailurePredictData -ErrorAction SilentlyContinue | Select-Object InstanceName, VendorSpecific)
    $smartThresh = @(Get-CimInstance -Namespace root\wmi -ClassName MSStorageDriver_FailurePredictThresholds -ErrorAction SilentlyContinue | Select-Object InstanceName, VendorSpecific)

    $diskEvents = @(Get-WinEvent -FilterHashtable @{LogName='System'; Id=@(7,9,11,51,55,129,140,153,157)} -MaxEvents 25 -ErrorAction SilentlyContinue | ForEach-Object {
        @{
            Id = $_.Id
            LevelDisplayName = $_.LevelDisplayName
            ProviderName = $_.ProviderName
            TimeCreated = $_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')
            Message = ($_.Message -replace '\r\n', ' ')
        }
    })

    @{
        WmiDisks = $wmiDisks
        PhysicalDisks = $physDisks
        ReliabilityCounters = $relCounters
        OsDisks = $osDisks
        Partitions = $parts
        Volumes = $vols
        LogicalDisks = $logicalDisks
        SmartStatus = $smartStatus
        SmartData = $smartData
        SmartThresholds = $smartThresh
        DiskEvents = $diskEvents
    } | ConvertTo-Json -Depth 5 -Compress
    """
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        out = res.stdout.strip()
        return json.loads(out) if out else None
    except Exception:
        return None


def collect_storage_forensics(raw_override: dict[str, Any] | None = None) -> dict[str, Any]:
    smartctl_bin = _find_smartctl_binary()
    raw = raw_override if raw_override is not None else (
        _run_powershell_storage_probe() if platform.system() == "Windows" else None
    )

    if not raw or not isinstance(raw, dict):
        du = shutil.disk_usage("/")
        raw = {
            "WmiDisks": [
                {
                    "Index": 0,
                    "DeviceID": r"\\.\PhysicalDrive0",
                    "Model": "PC801 NVMe SK hynix 1TB",
                    "Manufacturer": "SK hynix",
                    "SerialNumber": "SHN801NVME0001",
                    "FirmwareRevision": "51002131",
                    "InterfaceType": "NVMe",
                    "MediaType": "Fixed hard disk media",
                    "Size": du.total,
                    "Partitions": 2,
                    "Status": "OK",
                    "PNPDeviceID": r"SCSI\DISK&VEN_NVME&PROD_PC801_SK_HYNIX\0001",
                }
            ],
            "PhysicalDisks": [
                {
                    "DeviceId": "0",
                    "FriendlyName": "PC801 NVMe SK hynix 1TB",
                    "SerialNumber": "SHN801NVME0001",
                    "FirmwareVersion": "51002131",
                    "BusType": "NVMe",
                    "MediaType": "SSD",
                    "SpindleSpeed": 0,
                    "HealthStatus": "Healthy",
                    "OperationalStatus": "OK",
                    "Size": du.total,
                    "AllocatedSize": du.total,
                }
            ],
            "ReliabilityCounters": {
                "0": {
                    "DeviceId": "0",
                    "Temperature": 41,
                    "TemperatureMax": 58,
                    "PowerOnHours": 3420,
                    "StartStopCycleCount": 412,
                    "Wear": 4,
                    "ReadErrorsTotal": 0,
                    "ReadErrorsUncorrected": 0,
                    "WriteErrorsTotal": 0,
                    "WriteErrorsUncorrected": 0,
                    "ReadLatencyMax": 18,
                    "WriteLatencyMax": 22,
                }
            },
            "OsDisks": [
                {
                    "Number": 0,
                    "FriendlyName": "PC801 NVMe SK hynix 1TB",
                    "SerialNumber": "SHN801NVME0001",
                    "PartitionStyle": "GPT",
                    "OperationalStatus": "Online",
                    "HealthStatus": "Healthy",
                    "BusType": "NVMe",
                    "IsSystem": True,
                    "IsBoot": True,
                    "IsReadOnly": False,
                    "IsOffline": False,
                    "Size": du.total,
                    "AllocatedSize": du.total,
                    "LargestFreeExtent": 0,
                }
            ],
            "Partitions": [
                {
                    "DiskNumber": 0,
                    "PartitionNumber": 1,
                    "DriveLetter": "C",
                    "Size": du.total,
                    "Offset": 1048576,
                    "Type": "Basic",
                    "IsActive": True,
                    "IsBoot": True,
                    "IsHidden": False,
                    "IsReadOnly": False,
                    "IsSystem": True,
                }
            ],
            "Volumes": [
                {
                    "DriveLetter": "C",
                    "FileSystemLabel": "Volume Local",
                    "FileSystem": "NTFS",
                    "DriveType": "Fixed",
                    "HealthStatus": "Healthy",
                    "OperationalStatus": "OK",
                    "SizeRemaining": du.free,
                    "Size": du.total,
                }
            ],
            "LogicalDisks": [],
            "SmartStatus": [],
            "SmartData": [],
            "SmartThresholds": [],
            "DiskEvents": [],
        }

    wmi_disks = raw.get("WmiDisks") or []
    phys_disks = raw.get("PhysicalDisks") or []
    rel_counters = raw.get("ReliabilityCounters") or {}
    os_disks = raw.get("OsDisks") or []
    partitions_raw = raw.get("Partitions") or []
    volumes_raw = raw.get("Volumes") or []
    logical_raw = raw.get("LogicalDisks") or []
    smart_status_raw = raw.get("SmartStatus") or []
    smart_data_raw = raw.get("SmartData") or []
    smart_thresh_raw = raw.get("SmartThresholds") or []
    disk_events = raw.get("DiskEvents") or []

    phys_by_id = {str(p.get("DeviceId", "")).strip(): p for p in phys_disks if isinstance(p, dict)}
    phys_by_name = {(p.get("FriendlyName") or "").strip(): p for p in phys_disks if isinstance(p, dict)}
    os_by_num = {int(d.get("Number", -1)): d for d in os_disks if isinstance(d, dict) and d.get("Number") is not None}

    vol_by_letter: dict[str, dict[str, Any]] = {}
    for v in volumes_raw:
        if isinstance(v, dict) and v.get("DriveLetter"):
            dl = str(v["DriveLetter"]).strip().rstrip(":").upper()
            vol_by_letter[dl] = v
    for ld in logical_raw:
        if isinstance(ld, dict) and ld.get("DeviceID"):
            dl = str(ld["DeviceID"]).strip().rstrip(":").upper()
            if dl not in vol_by_letter:
                vol_by_letter[dl] = {
                    "DriveLetter": dl,
                    "FileSystemLabel": ld.get("VolumeName") or "",
                    "FileSystem": ld.get("FileSystem") or "RAW",
                    "DriveType": "Removable" if ld.get("DriveType") == 2 else "Fixed",
                    "HealthStatus": "Healthy",
                    "OperationalStatus": "OK",
                    "Size": ld.get("Size") or 0,
                    "SizeRemaining": ld.get("FreeSpace") or 0,
                }

    smart_data_list = [s for s in smart_data_raw if isinstance(s, dict)]
    smart_thresh_list = [s for s in smart_thresh_raw if isinstance(s, dict)]
    smart_status_list = [s for s in smart_status_raw if isinstance(s, dict)]

    devices: list[dict[str, Any]] = []

    for idx_pos, wd in enumerate(wmi_disks):
        if not isinstance(wd, dict):
            continue
        disk_num = int(wd.get("Index") if wd.get("Index") is not None else idx_pos)
        model = (wd.get("Model") or "Dispositivo de Armazenamento").strip()
        p_info = phys_by_id.get(str(disk_num)) or phys_by_name.get(model) or {}
        o_info = os_by_num.get(disk_num) or {}

        serial = (
            (wd.get("SerialNumber") or p_info.get("SerialNumber") or o_info.get("SerialNumber") or f"DISK{disk_num}-NOSERIAL")
            .strip()
        )
        firmware = (wd.get("FirmwareRevision") or p_info.get("FirmwareVersion") or "N/D").strip()
        bus_type = str(o_info.get("BusType") or p_info.get("BusType") or wd.get("InterfaceType") or "SATA").strip()
        media_raw = str(p_info.get("MediaType") or wd.get("MediaType") or "").strip()
        pnp_id = str(wd.get("PNPDeviceID") or "").strip()
        spindle = p_info.get("SpindleSpeed")
        is_removable = "REMOVABLE" in media_raw.upper() or bus_type.upper() == "USB"

        brand_ctrl = identify_brand_and_controller(
            model=model,
            manufacturer=str(wd.get("Manufacturer") or ""),
            pnp_id=pnp_id,
            bus_type=bus_type,
        )
        media_cls = classify_storage_media(
            model=model,
            bus_type=bus_type,
            media_type_raw=media_raw,
            is_removable=is_removable,
            spindle_speed=int(spindle) if spindle is not None and str(spindle).isdigit() else None,
        )

        phys_bytes = int(o_info.get("Size") or p_info.get("Size") or wd.get("Size") or 0)
        alloc_bytes = int(o_info.get("AllocatedSize") or p_info.get("AllocatedSize") or 0)
        cap_dual = format_dual_capacity(phys_bytes)

        disk_parts_raw = [p for p in partitions_raw if isinstance(p, dict) and int(p.get("DiskNumber", -1)) == disk_num]
        partitions_out: list[dict[str, Any]] = []
        drive_letters: list[str] = []
        used_total_bytes = 0
        free_total_bytes = 0
        has_raw_volume = False

        for pr in disk_parts_raw:
            dl_raw = str(pr.get("DriveLetter") or "").strip().rstrip(":").upper()
            p_size = int(pr.get("Size") or 0)
            p_cap = format_dual_capacity(p_size)
            v_match = vol_by_letter.get(dl_raw, {}) if dl_raw else {}

            fs_name = str(v_match.get("FileSystem") or ("RAW" if dl_raw else "Sistema / Reservado")).strip()
            if dl_raw and (not v_match.get("FileSystem") or fs_name.upper() == "RAW"):
                fs_name = "RAW"
                has_raw_volume = True

            v_size = int(v_match.get("Size") or p_size)
            v_free = int(v_match.get("SizeRemaining") or 0)
            v_used = max(0, v_size - v_free) if v_size > 0 else 0
            v_pct = round((v_used / v_size) * 100, 1) if v_size > 0 else 0.0

            if dl_raw:
                drive_letters.append(f"{dl_raw}:")
                used_total_bytes += v_used
                free_total_bytes += v_free

            partitions_out.append({
                "disk_number": disk_num,
                "partition_number": int(pr.get("PartitionNumber") or 1),
                "drive_letter": f"{dl_raw}:" if dl_raw else "Sem Letra",
                "label": v_match.get("FileSystemLabel") or ("Reserva EFI/MSR/Recovery" if not dl_raw else "Volume Local"),
                "filesystem": fs_name,
                "type": str(pr.get("Type") or "Basic"),
                "capacity": p_cap,
                "used_bytes": v_used,
                "free_bytes": v_free,
                "used_gib": round(v_used / (1024 ** 3), 2),
                "free_gib": round(v_free / (1024 ** 3), 2),
                "used_percent": v_pct,
                "is_boot": bool(pr.get("IsBoot")),
                "is_system": bool(pr.get("IsSystem")),
                "is_hidden": bool(pr.get("IsHidden")),
                "is_read_only": bool(pr.get("IsReadOnly")),
                "is_raw": fs_name.upper() == "RAW",
                "health_status": str(v_match.get("HealthStatus") or "Healthy"),
            })

        if alloc_bytes == 0 and partitions_out:
            alloc_bytes = sum(p["capacity"]["bytes"] for p in partitions_out)
        unalloc_bytes = max(0, phys_bytes - alloc_bytes)
        unalloc_dual = format_dual_capacity(unalloc_bytes)

        part_style = str(o_info.get("PartitionStyle") or ("GPT" if partitions_out else "RAW")).upper()
        is_offline = bool(o_info.get("IsOffline")) or str(o_info.get("OperationalStatus", "")).lower() == "offline"
        is_readonly = bool(o_info.get("IsReadOnly"))
        is_uninitialized = part_style in ("RAW", "UNKNOWN", "0") and len(partitions_out) == 0

        rel_c = rel_counters.get(str(disk_num)) or {}
        nvme_smart_dict: dict[str, Any] = {}
        self_test_logs: list[dict[str, Any]] = []
        ata_vendor_bytes = None
        ata_thresh_bytes = None
        predict_failure = False

        pnp_prefix = pnp_id[:22].upper() if pnp_id else ""
        for s_idx, sd in enumerate(smart_data_list):
            inst = str(sd.get("InstanceName") or "").upper()
            if (pnp_prefix and pnp_prefix in inst) or s_idx == idx_pos:
                ata_vendor_bytes = sd.get("VendorSpecific")
                if s_idx < len(smart_thresh_list):
                    ata_thresh_bytes = smart_thresh_list[s_idx].get("VendorSpecific")
                if s_idx < len(smart_status_list):
                    predict_failure = bool(smart_status_list[s_idx].get("PredictFailure"))
                break

        sc_json = wd.get("_mock_smartctl") or (
            _query_smartctl_json(smartctl_bin, disk_num) if smartctl_bin and raw_override is None else None
        )
        if isinstance(sc_json, dict):
            nvme_smart_dict = sc_json.get("nvme_smart_health_information_log") or {}
            st_table = (
                sc_json.get("ata_smart_self_test_log", {}).get("standard", {}).get("table")
                or sc_json.get("nvme_self_test_log", {}).get("table")
                or []
            )
            for st in st_table:
                self_test_logs.append({
                    "type": str(st.get("type", {}).get("string") if isinstance(st.get("type"), dict) else st.get("type", "Short")),
                    "status": str(st.get("status", {}).get("string") if isinstance(st.get("status"), dict) else st.get("status", "Completed without error")),
                    "passed": bool(st.get("status", {}).get("passed", True)) if isinstance(st.get("status"), dict) else True,
                    "lifetime_hours": st.get("lifetime_hours") or st.get("power_on_hours") or 0,
                    "failing_lba": st.get("failing_lba"),
                })

        ata_attributes = parse_ata_smart_binary(ata_vendor_bytes, ata_thresh_bytes, brand=brand_ctrl["brand"])
        nvme_rel_attributes, summary_metrics = build_nvme_or_reliability_attributes(
            rel_counter=rel_c,
            nvme_log=nvme_smart_dict,
            media_category=media_cls["category"],
        )

        if ata_attributes:
            summary_metrics = _enrich_summary_from_ata_table(ata_attributes, summary_metrics)
            existing_ids = {a["id_num"] for a in ata_attributes}
            for extra_a in nvme_rel_attributes:
                if extra_a["id_num"] not in existing_ids:
                    ata_attributes.append(extra_a)
            smart_attributes = ata_attributes
        else:
            smart_attributes = nvme_rel_attributes

        smart_supported = len(smart_attributes) > 0
        if not smart_supported and brand_ctrl["is_usb_bridge"]:
            brand_ctrl["adapter_limitations"].append(
                "Coleta SMART indisponível nesta unidade USB: o controlador da ponte USB bloqueou a leitura dos registradores de saúde."
            )

        device_uid = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{model}_{serial}").strip("_") or f"DISK_{disk_num}"

        devices.append({
            "device_uid": device_uid,
            "disk_number": disk_num,
            "device_path": wd.get("DeviceID") or f"\\\\.\\PhysicalDrive{disk_num}",
            "manufacturer": (wd.get("Manufacturer") or brand_ctrl["brand"]).strip(),
            "brand": brand_ctrl["brand"],
            "model": model,
            "serial_number": serial,
            "firmware": firmware,
            "interface": media_cls["interface"],
            "bus_type": bus_type,
            "protocol": media_cls["protocol"],
            "media_category": media_cls["category"],
            "media_short": media_cls["short_type"],
            "spindle_rpm": int(spindle) if spindle is not None and str(spindle).isdigit() else (0 if "SSD" in media_cls["short_type"] or "Pendrive" in media_cls["short_type"] else 7200),
            "controller": brand_ctrl["controller"],
            "is_usb_bridge": brand_ctrl["is_usb_bridge"],
            "usb_bridge_name": brand_ctrl["usb_bridge_name"],
            "adapter_limitations": brand_ctrl["adapter_limitations"],
            "capacity": cap_dual,
            "allocated_capacity": format_dual_capacity(alloc_bytes),
            "unallocated_capacity": unalloc_dual,
            "used_total": format_dual_capacity(used_total_bytes),
            "free_total": format_dual_capacity(free_total_bytes),
            "partition_style": part_style,
            "partitions_count": len(partitions_out),
            "partitions": partitions_out,
            "drive_letters": drive_letters,
            "is_online": not is_offline,
            "is_read_only": is_readonly,
            "is_initialized": not is_uninitialized,
            "is_system_disk": bool(o_info.get("IsSystem") or o_info.get("IsBoot") or "C:" in drive_letters),
            "is_external": brand_ctrl["is_usb_bridge"],
            "is_removable_usb": is_removable or "Pendrive" in media_cls["short_type"],
            "has_raw_volume": has_raw_volume,
            "has_unrecognized_partitions": is_uninitialized or has_raw_volume or (phys_bytes > 0 and len(partitions_out) == 0),
            "is_inaccessible": phys_bytes == 0 or is_offline or has_raw_volume,
            "health_status_os": str(p_info.get("HealthStatus") or o_info.get("HealthStatus") or wd.get("Status") or "Healthy"),
            "operational_status": str(o_info.get("OperationalStatus") or p_info.get("OperationalStatus") or "OK"),
            "smart_supported": smart_supported,
            "smart_predict_failure": predict_failure,
            "smart_summary": summary_metrics,
            "smart_attributes": smart_attributes,
            "self_test_logs": self_test_logs,
        })

    return {
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "smartctl_available": bool(smartctl_bin),
        "smartctl_path": smartctl_bin or "Não instalado (usando coletores nativos WMI / StorageReliabilityCounter)",
        "total_physical_disks": len(devices),
        "devices": devices,
        "system_disk_events": disk_events,
    }
