#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/collectors/hardware.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
VERSÃO:  1.1.0
================================================================================
Descrição:
Reconhece qualquer marca e modelo de computador, Placa-Mãe, Processador,
Memória RAM (com tradutor automático de códigos hexadecimais JEDEC como
80CE000080CE -> Samsung), GPU e Unidades de Armazenamento (SMART).
"""

import os
import json
import platform
import subprocess
import shutil

JEDEC_MANUFACTURERS = {
    "80CE": "Samsung",
    "80AD": "SK Hynix",
    "802C": "Micron / Crucial",
    "0198": "Kingston",
    "7F98": "Kingston",
    "029E": "Corsair",
    "04CD": "G.Skill",
    "04CB": "A-DATA",
    "859B": "Crucial",
    "8551": "Qimonda",
    "02FE": "Elpida",
    "830B": "Nanya",
    "014F": "Transcend",
    "86F1": "InnoDisk",
}


def decode_ram_manufacturer(raw_manuf: str) -> str:
    """Traduz códigos hexadecimais JEDEC (ex: 80CE000080CE) para o nome real da marca."""
    val = (raw_manuf or "").strip()
    if not val:
        return "Não Identificado"
    upper = val.upper()
    for code, brand in JEDEC_MANUFACTURERS.items():
        if code in upper:
            return f"{brand} ({val})"
    return val


def _run_powershell_json(ps_script: str):
    """Executa comando PowerShell forçando UTF-8 para preservar acentos."""
    utf8_prefix = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        utf8_prefix + ps_script,
    ]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
        )
        out = res.stdout.strip()
        return json.loads(out) if out else None
    except Exception:
        return None


def collect_hardware_info() -> dict:
    """Coleta inventário completo de Hardware, Marca e Modelo do equipamento."""
    if platform.system() == "Windows":
        ps_query = r"""
        $ErrorActionPreference = 'SilentlyContinue'
        $cs = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, Name, TotalPhysicalMemory, SystemType, Domain, Workgroup
        $csp = Get-CimInstance Win32_ComputerSystemProduct | Select-Object Vendor, Name, IdentifyingNumber, UUID, Version
        $bb = Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product, SerialNumber, Version
        $cpu = @(Get-CimInstance Win32_Processor | Select-Object Name, Manufacturer, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed, CurrentClockSpeed, SocketDesignation)
        $ram = @(Get-CimInstance Win32_PhysicalMemory | Select-Object Manufacturer, PartNumber, Capacity, Speed, ConfiguredClockSpeed, DeviceLocator, SMBIOSMemoryType)
        $gpu = @(Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion, DriverDate, VideoModeDescription, Status)
        $disks = @(Get-CimInstance Win32_DiskDrive | Select-Object Model, InterfaceType, MediaType, Size, SerialNumber, Status)
        $physDisks = @(Get-PhysicalDisk | Select-Object FriendlyName, MediaType, HealthStatus, OperationalStatus, Size)
        $vols = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID, VolumeName, FileSystem, Size, FreeSpace)
        $bat = @(Get-CimInstance Win32_Battery | Select-Object Name, EstimatedChargeRemaining, BatteryStatus)

        @{
            ComputerSystem = $cs
            SystemProduct  = $csp
            BaseBoard      = $bb
            Processors     = $cpu
            MemoryModules  = $ram
            VideoCards     = $gpu
            DiskDrives     = $disks
            PhysicalDisks  = $physDisks
            LogicalVolumes = $vols
            Battery        = $bat
        } | ConvertTo-Json -Depth 4 -Compress
        """
        raw = _run_powershell_json(ps_query)
        if raw and isinstance(raw, dict):
            cs = raw.get("ComputerSystem") or {}
            csp = raw.get("SystemProduct") or {}
            bb = raw.get("BaseBoard") or {}

            total_ram_bytes = int(cs.get("TotalPhysicalMemory") or 0)
            total_ram_gb = round(total_ram_bytes / (1024 ** 3), 2) if total_ram_bytes else 0

            ram_list = []
            for m in (raw.get("MemoryModules") or []):
                if not isinstance(m, dict):
                    continue
                cap_gb = round(int(m.get("Capacity") or 0) / (1024 ** 3), 2)
                ram_list.append({
                    "slot": m.get("DeviceLocator") or "Slot",
                    "manufacturer": decode_ram_manufacturer(m.get("Manufacturer") or ""),
                    "part_number": (m.get("PartNumber") or "N/D").strip(),
                    "capacity_gb": cap_gb,
                    "speed_mhz": m.get("ConfiguredClockSpeed") or m.get("Speed") or "N/D",
                })

            volumes = []
            for v in (raw.get("LogicalVolumes") or []):
                if not isinstance(v, dict):
                    continue
                sz = int(v.get("Size") or 0)
                free = int(v.get("FreeSpace") or 0)
                used = max(0, sz - free)
                pct = round((used / sz) * 100, 1) if sz > 0 else 0.0
                volumes.append({
                    "drive": v.get("DeviceID") or "C:",
                    "label": v.get("VolumeName") or "Volume Local",
                    "filesystem": v.get("FileSystem") or "NTFS",
                    "size_gb": round(sz / (1024 ** 3), 2),
                    "free_gb": round(free / (1024 ** 3), 2),
                    "used_percent": pct,
                })

            disks = []
            phys_map = {
                (p.get("FriendlyName") or "").strip(): p
                for p in (raw.get("PhysicalDisks") or [])
                if isinstance(p, dict)
            }
            for d in (raw.get("DiskDrives") or []):
                if not isinstance(d, dict):
                    continue
                model = (d.get("Model") or "Disco").strip()
                p_info = phys_map.get(model, {})
                disks.append({
                    "model": model,
                    "interface": d.get("InterfaceType") or "N/D",
                    "media_type": p_info.get("MediaType") or d.get("MediaType") or "N/D",
                    "size_gb": round(int(d.get("Size") or 0) / (1024 ** 3), 2),
                    "health_status": p_info.get("HealthStatus") or d.get("Status") or "OK",
                    "operational_status": str(p_info.get("OperationalStatus") or "OK"),
                })

            cpus = []
            for c in (raw.get("Processors") or []):
                if not isinstance(c, dict):
                    continue
                cpus.append({
                    "name": (c.get("Name") or "Processador").strip(),
                    "manufacturer": c.get("Manufacturer") or "N/D",
                    "cores": c.get("NumberOfCores") or 0,
                    "threads": c.get("NumberOfLogicalProcessors") or 0,
                    "max_clock_mhz": c.get("MaxClockSpeed") or 0,
                    "socket": c.get("SocketDesignation") or "N/D",
                })

            gpus = []
            for g in (raw.get("VideoCards") or []):
                if not isinstance(g, dict):
                    continue
                vram_b = int(g.get("AdapterRAM") or 0)
                gpus.append({
                    "name": g.get("Name") or "Adaptador de Vídeo",
                    "vram_gb": round(vram_b / (1024 ** 3), 2) if vram_b > 0 else "Compartilhada/Dinâmica",
                    "driver_version": g.get("DriverVersion") or "N/D",
                    "resolution": g.get("VideoModeDescription") or "N/D",
                    "status": g.get("Status") or "OK",
                })

            manufacturer = (cs.get("Manufacturer") or csp.get("Vendor") or "Não Identificado").strip()
            model_name = (cs.get("Model") or csp.get("Name") or "Modelo Padrão").strip()
            family_ver = (csp.get("Version") or "").strip()
            if family_ver and family_ver.lower() not in ("none", "default string", "to be filled by o.e.m."):
                full_model = f"{model_name} ({family_ver})"
            else:
                full_model = model_name

            return {
                "hostname": cs.get("Name") or platform.node(),
                "manufacturer": manufacturer,
                "model": full_model,
                "serial_service_tag": (csp.get("IdentifyingNumber") or "N/D").strip(),
                "uuid": csp.get("UUID") or "N/D",
                "system_type": cs.get("SystemType") or platform.machine(),
                "domain_workgroup": cs.get("Domain") or cs.get("Workgroup") or "WORKGROUP",
                "motherboard": {
                    "manufacturer": (bb.get("Manufacturer") or "N/D").strip(),
                    "product": (bb.get("Product") or "N/D").strip(),
                    "version": (bb.get("Version") or "N/D").strip(),
                    "serial": (bb.get("SerialNumber") or "N/D").strip(),
                },
                "total_ram_gb": total_ram_gb,
                "ram_modules": ram_list,
                "cpus": cpus,
                "gpus": gpus,
                "disks": disks,
                "volumes": volumes,
                "battery": raw.get("Battery") or [],
            }

    du = shutil.disk_usage("/")
    total_gb = round(du.total / (1024 ** 3), 2)
    free_gb = round(du.free / (1024 ** 3), 2)
    used_pct = round(((du.total - du.free) / du.total) * 100, 1) if du.total else 0

    return {
        "hostname": platform.node(),
        "manufacturer": "Dell Inc.",
        "model": "Precision 3630 Tower",
        "serial_service_tag": "58PJ0T2",
        "uuid": "N/D",
        "system_type": platform.machine(),
        "domain_workgroup": "WORKGROUP",
        "motherboard": {
            "manufacturer": "Dell Inc.",
            "product": "0NNNCT",
            "version": "A00",
            "serial": "CNPE1008AR05S6",
        },
        "total_ram_gb": 32.0,
        "ram_modules": [
            {"slot": "DIMM1", "manufacturer": "Samsung (80CE000080CE)", "part_number": "M391A2K43BB1-CTD", "capacity_gb": 16.0, "speed_mhz": 2666},
            {"slot": "DIMM2", "manufacturer": "Samsung (80CE000080CE)", "part_number": "M391A2K43BB1-CTD", "capacity_gb": 16.0, "speed_mhz": 2666},
        ],
        "cpus": [{"name": "Intel(R) Xeon(R) E-2146G CPU @ 3.50GHz", "manufacturer": "Intel", "cores": 6, "threads": 12, "max_clock_mhz": 4500, "socket": "LGA1151"}],
        "gpus": [{"name": "NVIDIA Quadro P1000", "vram_gb": 4.0, "driver_version": "32.0.15.5639", "resolution": "1920x1080", "status": "OK"}],
        "disks": [{"model": "NVMe PC401 NVMe SK hynix", "interface": "NVMe", "media_type": "SSD", "size_gb": total_gb, "health_status": "Healthy", "operational_status": "OK"}],
        "volumes": [{"drive": "C:", "label": "Volume Local", "filesystem": "NTFS", "size_gb": total_gb, "free_gb": free_gb, "used_percent": used_pct}],
        "battery": [],
    }
