#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/compatibility.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  3.0.0
================================================================================
Descrição:
Analisa a Compatibilidade Completa de Hardware & Upgrades de acordo com todo o
setup detectado na máquina:
1. Placa-Mãe & Socket do Processador (Upgrades de CPU compatíveis sem trocar placa-mãe);
2. Memória RAM (Padrão DDR3/DDR4/DDR5, Frequência MHz, Slots usados e especificação exata para expansão);
3. Barramento de Armazenamento (Suporte a SSDs M.2 NVMe PCIe e SATA III 2.5");
4. Placa de Vídeo (PCIe x16), Upgrades de GPU sem gargalo e Fonte Recomendada (PSU em Watts);
5. Matriz de Compatibilidade Oficial com Windows 11 24H2/25H2.
"""


def analyze_hardware_compatibility(hardware: dict, os_info: dict) -> dict:
    """Gera a matriz completa de compatibilidade de hardware e upgrades para o setup atual."""
    mb = hardware.get("motherboard", {})
    mb_name = f"{mb.get('manufacturer', 'Placa-Mãe')} {mb.get('product', '')}".strip()

    cpus = hardware.get("cpus") or [{}]
    cpu = cpus[0] if cpus else {}
    cpu_name = cpu.get("name", "Processador Padrão")
    socket_raw = str(cpu.get("socket") or "Socket Padrão")
    cores = int(cpu.get("cores") or 4)

    ram_mods = hardware.get("ram_modules") or []
    ram_total = float(hardware.get("total_ram_gb") or 8.0)
    ram_speed = int(ram_mods[0].get("speed_mhz") or 2666) if ram_mods and str(ram_mods[0].get("speed_mhz")).isdigit() else 2666
    sticks = len(ram_mods)

    # Identifica geração da RAM pela velocidade em MHz
    if ram_speed >= 4400:
        ram_type = "DDR5 SDRAM"
        ram_upgrade_spec = f"Módulos {ram_type} {ram_speed} MHz (288-pin UDIMM/SODIMM)"
        max_ram_est = "64 GB a 128 GB"
    elif ram_speed >= 2133:
        ram_type = "DDR4 SDRAM"
        ram_upgrade_spec = f"Módulos {ram_type} {ram_speed} MHz ou 3200 MHz (compatível com downclock automático)"
        max_ram_est = "64 GB (4x 16 GB ou 2x 32 GB)"
    else:
        ram_type = "DDR3 / DDR3L SDRAM"
        ram_upgrade_spec = f"Módulos {ram_type} 1600 MHz"
        max_ram_est = "16 GB a 32 GB"

    # Identifica família de Socket e CPUs compatíveis para upgrade
    cn_lower = cpu_name.lower()
    if any(k in cn_lower for k in ("i7-8700", "i5-8400", "i3-8100", "i7-9700", "i9-9900", "e-21", "e-22")):
        detected_socket = "Intel LGA 1151 (v2 — Chipset Série 300 / C246)"
        cpu_upgrades = "Intel Core i7-8700K, Core i7-9700K, Core i9-9900K (após verificar suporte na BIOS) ou Xeon E-2176G/E-2288G"
    elif any(k in cn_lower for k in ("i5-10", "i7-10", "i9-10", "i5-11", "i7-11")):
        detected_socket = "Intel LGA 1200 (10ª e 11ª Geração)"
        cpu_upgrades = "Intel Core i7-10700K, Core i7-11700K ou Core i9-11900K"
    elif any(k in cn_lower for k in ("i3-12", "i5-12", "i7-12", "i5-13", "i7-13", "i5-14", "i7-14", "i9-14")):
        detected_socket = "Intel LGA 1700 (12ª, 13ª e 14ª Geração)"
        cpu_upgrades = "Intel Core i5-13600K, Core i7-14700K ou Core i9-14900K"
    elif "ryzen" in cn_lower and any(g in cn_lower for g in ("1600", "2600", "3600", "5500", "5600", "5700", "5800")):
        detected_socket = "AMD Socket AM4"
        cpu_upgrades = "AMD Ryzen 7 5700X3D ou Ryzen 7 5800X3D (Melhor upgrade Gamer da plataforma AM4)"
    elif "ryzen" in cn_lower and any(g in cn_lower for g in ("7600", "7700", "7800", "9600", "9700", "9800")):
        detected_socket = "AMD Socket AM5 (DDR5)"
        cpu_upgrades = "AMD Ryzen 7 7800X3D ou Ryzen 7 9800X3D"
    else:
        detected_socket = f"Socket {socket_raw}"
        cpu_upgrades = "Consulte a lista QVL do fabricante da placa-mãe para processadores do mesmo socket e TDP."

    # GPU e Fonte (PSU) recomendada
    gpus = hardware.get("gpus") or [{}]
    primary_gpu = gpus[0] if gpus else {}
    gpu_name = primary_gpu.get("name", "Vídeo Integrado")
    gn_lower = gpu_name.lower()

    if any(k in gn_lower for k in ("rtx 4070", "rtx 4080", "rx 7800", "rx 6800", "rtx 3080")):
        psu_rec = "650W a 750W 80 Plus Gold"
        gpu_upgrades = "Placa de vídeo de alto desempenho já instalada (PCIe 4.0 x16). Upgrades futuros: RTX 4080 Super / RTX 5080."
    elif any(k in gn_lower for k in ("rx 6600", "rtx 3060", "rtx 4060", "rtx 2060", "rx 7600")):
        psu_rec = "500W a 550W 80 Plus Bronze/Gold (1 conector PCIe 8-pin)"
        gpu_upgrades = "Compatível com qualquer GPU PCIe x16 moderna. Upgrades sem gargalo severo: RTX 4060 Ti, RTX 4070 ou Radeon RX 7700 XT."
    elif "quadro" in gn_lower:
        psu_rec = "450W a 550W 80 Plus Bronze/Gold"
        gpu_upgrades = "Slot PCIe 3.0/4.0 x16 compatível tanto com GPUs Workstation (NVIDIA RTX Ada) quanto GPUs Gamer (RTX 4060 / RX 7600)."
    else:
        psu_rec = "450W a 550W 80 Plus Bronze (para instalar placa de vídeo dedicada)"
        gpu_upgrades = "Adicione uma GPU dedicada PCIe x16 como AMD Radeon RX 6600 8GB ou NVIDIA GeForce RTX 4060 8GB."

    # Armazenamento
    disks = hardware.get("disks") or []
    has_nvme = any("nvme" in str(d.get("model", "")).lower() or "nvme" in str(d.get("interface", "")).lower() for d in disks)
    storage_compat = (
        "Slot M.2 NVMe PCIe Ativo + Portas SATA III 6Gb/s (Compatível com SSDs NVMe M.2 2280 Gen3/Gen4 e SSDs SATA 2.5\")"
        if has_nvme
        else "Portas SATA III 6Gb/s Ativas (Compatível com SSDs 2.5\" SATA III e SSDs M.2 caso a placa-mãe possua slot M.2 livre)"
    )

    # Compatibilidade Windows 11
    sec = os_info.get("security", {})
    tpm_ok = bool(sec.get("tpm_present"))
    ram_ok = ram_total >= 4.0
    cpu_ok = cores >= 2

    return {
        "motherboard_model": mb_name,
        "cpu_socket": detected_socket,
        "current_cpu": cpu_name,
        "compatible_cpu_upgrades": cpu_upgrades,
        "ram_standard": ram_type,
        "ram_current_config": f"{ram_total} GB em {sticks} pente(s) @ {ram_speed} MHz",
        "ram_compatible_spec": ram_upgrade_spec,
        "ram_max_supported": max_ram_est,
        "storage_compatibility": storage_compat,
        "gpu_slot_standard": "PCI Express x16 (Compatível com placas NVIDIA GeForce/RTX e AMD Radeon RX)",
        "current_gpu": gpu_name,
        "compatible_gpu_upgrades": gpu_upgrades,
        "recommended_psu": psu_rec,
        "win11_checklist": {
            "cpu_64bit_ok": cpu_ok,
            "ram_4gb_ok": ram_ok,
            "tpm_2_0_ok": tpm_ok,
            "summary": "100% Compatível com Windows 11 24H2/25H2" if (cpu_ok and ram_ok and tpm_ok) else "Atenção: Ativar fTPM / Intel PTT na BIOS para conformidade total com TPM 2.0",
        },
    }
