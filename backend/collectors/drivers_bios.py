#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/collectors/drivers_bios.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
VERSÃO:  1.1.0
================================================================================
"""

import json
import platform
import subprocess
from datetime import datetime


def _run_ps_json(ps_script: str, timeout: int = 40):
    utf8_prefix = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", utf8_prefix + ps_script]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        out = res.stdout.strip()
        return json.loads(out) if out else None
    except Exception:
        return None


def _get_vendor_support_url(manufacturer: str, serial: str) -> str:
    m = (manufacturer or "").lower()
    if "dell" in m:
        return "https://www.dell.com/support/home/pt-br"
    if "lenovo" in m:
        return "https://pcsupport.lenovo.com/br/pt"
    if "hp" in m or "hewlett" in m:
        return "https://support.hp.com/br-pt/drivers"
    if "asus" in m:
        return "https://www.asus.com/br/support/download-center/"
    if "acer" in m:
        return "https://www.acer.com/br-pt/support/drivers-and-manuals"
    if "msi" in m:
        return "https://br.msi.com/support/download"
    if "gigabyte" in m:
        return "https://www.gigabyte.com/br/Support"
    if "samsung" in m:
        return "https://www.samsung.com/br/support/"
    return "https://www.catalog.update.microsoft.com/"


def collect_drivers_and_bios() -> dict:
    """Coleta BIOS e Drivers instalados, filtrando drivers nativos Microsoft 2006."""
    if platform.system() == "Windows":
        ps_query = r"""
        $ErrorActionPreference = 'SilentlyContinue'
        $cs = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model
        $bios = Get-CimInstance Win32_BIOS | Select-Object Manufacturer, Name, SMBIOSBIOSVersion, Version, SerialNumber, ReleaseDate
        $pnpErrors = @(Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -ne 0 } | Select-Object Name, DeviceID, ConfigManagerErrorCode, Status)
        $drivers = @(Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceName -ne $null -and $_.DriverVersion -ne $null } |
            Select-Object DeviceName, DeviceClass, Manufacturer, DriverVersion, DriverDate, IsSigned, InfName |
            Sort-Object DeviceClass, DeviceName)

        @{
            Manufacturer = $cs.Manufacturer
            Model        = $cs.Model
            BIOS         = $bios
            PnPErrors    = $pnpErrors
            Drivers      = $drivers
        } | ConvertTo-Json -Depth 4 -Compress
        """
        raw = _run_ps_json(ps_query, timeout=45)
        if raw and isinstance(raw, dict):
            bios_raw = raw.get("BIOS") or {}
            rel_date_str = "N/D"
            bios_age_months = 0
            bios_outdated = False

            rel_raw = bios_raw.get("ReleaseDate")
            if isinstance(rel_raw, str) and "/Date(" in rel_raw:
                try:
                    ms = int(rel_raw.split("(")[1].split(")")[0].split("-")[0].split("+")[0])
                    dt = datetime.fromtimestamp(ms / 1000.0)
                    rel_date_str = dt.strftime("%Y-%m-%d")
                    bios_age_months = max(0, int((datetime.now() - dt).days / 30))
                    if bios_age_months >= 24:
                        bios_outdated = True
                except Exception:
                    pass

            sys_manuf = raw.get("Manufacturer") or bios_raw.get("Manufacturer") or "Fabricante"
            serial = bios_raw.get("SerialNumber") or ""
            vendor_url = _get_vendor_support_url(sys_manuf, serial)

            bios_info = {
                "manufacturer": bios_raw.get("Manufacturer") or "N/D",
                "name": bios_raw.get("Name") or "BIOS/UEFI",
                "smbios_version": bios_raw.get("SMBIOSBIOSVersion") or bios_raw.get("Version") or "N/D",
                "serial_number": serial or "N/D",
                "release_date": rel_date_str,
                "age_months": bios_age_months,
                "needs_review": bios_outdated,
                "status_label": "Verificar Atualização (> 2 anos)" if bios_outdated else "Atualizada / Recente",
                "vendor_support_url": vendor_url,
            }

            pnp_errors = []
            for err in (raw.get("PnPErrors") or []):
                if not isinstance(err, dict):
                    continue
                pnp_errors.append({
                    "device_name": err.get("Name") or "Dispositivo Desconhecido",
                    "device_id": err.get("DeviceID") or "N/D",
                    "error_code": err.get("ConfigManagerErrorCode") or -1,
                    "status": err.get("Status") or "Error",
                })

            driver_list = []
            outdated_count = 0
            critical_classes = {"DISPLAY", "NET", "MEDIA", "USB", "HDC", "SCSIADAPTER", "BLUETOOTH", "SYSTEM"}

            for drv in (raw.get("Drivers") or []):
                if not isinstance(drv, dict):
                    continue
                d_class = (drv.get("DeviceClass") or "OUTROS").upper()
                manuf_name = (drv.get("Manufacturer") or "Genérico").strip()
                d_date_raw = drv.get("DriverDate")
                d_date_str = "N/D"
                age_months = 0
                is_old = False
                status_text = "OK"

                if isinstance(d_date_raw, str) and "/Date(" in d_date_raw:
                    try:
                        ms = int(d_date_raw.split("(")[1].split(")")[0].split("-")[0].split("+")[0])
                        dt = datetime.fromtimestamp(ms / 1000.0)
                        d_date_str = dt.strftime("%Y-%m-%d")
                        age_months = max(0, int((datetime.now() - dt).days / 30))

                        is_ms_inbox = (
                            "microsoft" in manuf_name.lower()
                            and d_date_str.startswith("2006-06-")
                        )
                        if is_ms_inbox:
                            status_text = "Nativo do Windows (Inbox)"
                            is_old = False
                        elif d_class in critical_classes and age_months >= 36:
                            is_old = True
                            outdated_count += 1
                            status_text = "Revisar Versão (> 3 anos)"
                    except Exception:
                        pass

                driver_list.append({
                    "device_name": drv.get("DeviceName") or "Dispositivo",
                    "device_class": d_class,
                    "manufacturer": manuf_name,
                    "version": drv.get("DriverVersion") or "N/D",
                    "date": d_date_str,
                    "age_months": age_months,
                    "is_signed": bool(drv.get("IsSigned", True)),
                    "inf_name": drv.get("InfName") or "N/D",
                    "outdated_flag": is_old,
                    "status": status_text,
                })

            return {
                "bios": bios_info,
                "pnp_errors": pnp_errors,
                "drivers": driver_list[:200],
                "total_drivers": len(driver_list),
                "outdated_drivers_count": outdated_count,
                "error_devices_count": len(pnp_errors),
            }

    return {
        "bios": {
            "manufacturer": "Dell Inc.",
            "name": "UEFI BIOS Firmware",
            "smbios_version": "2.40.0",
            "serial_number": "58PJ0T2",
            "release_date": "2026-04-26",
            "age_months": 5,
            "needs_review": False,
            "status_label": "Atualizada / Recente",
            "vendor_support_url": "https://www.dell.com/support/home/pt-br",
        },
        "pnp_errors": [],
        "drivers": [
            {
                "device_name": "Bluetooth Device (RFCOMM Protocol TDI)",
                "device_class": "BLUETOOTH",
                "manufacturer": "Microsoft",
                "version": "10.0.26100.9278",
                "date": "2006-06-20",
                "age_months": 244,
                "is_signed": True,
                "inf_name": "tdibth.inf",
                "outdated_flag": False,
                "status": "Nativo do Windows (Inbox)",
            }
        ],
        "total_drivers": 1,
        "outdated_drivers_count": 0,
        "error_devices_count": 0,
    }


def scan_and_install_windows_driver_updates(install: bool = False) -> dict:
    """Pesquisa e opcionalmente instala atualizações de Drivers via Windows Update."""
    if platform.system() != "Windows":
        return {
            "success": True,
            "mode": "simulation",
            "message": "Busca de drivers Windows Update disponível em sistemas Windows.",
            "updates": [],
        }

    ps_script = f"""
    $ErrorActionPreference = 'Stop'
    try {{
        $session = New-Object -ComObject Microsoft.Update.Session
        $searcher = $session.CreateUpdateSearcher()
        $result = $searcher.Search("IsInstalled=0 and Type='Driver'")
        $updates = @()
        foreach ($u in $result.Updates) {{
            $updates += @{{
                Title = $u.Title
                DriverModel = $u.DriverModel
                DriverManufacturer = $u.DriverManufacturer
                DriverVerDate = if ($u.DriverVerDate) {{ $u.DriverVerDate.ToString('yyyy-MM-dd') }} else {{ 'N/D' }}
                IsMandatory = $u.IsMandatory
            }}
        }}
        $installedCount = 0
        if (${'true' if install else 'false'} -and $result.Updates.Count -gt 0) {{
            $downloader = $session.CreateUpdateDownloader()
            $downloader.Updates = $result.Updates
            $downloader.Download() | Out-Null
            $installer = $session.CreateUpdateInstaller()
            $installer.Updates = $result.Updates
            $installRes = $installer.Install()
            $installedCount = $result.Updates.Count
        }}
        @{{
            Success = $true
            FoundCount = $updates.Count
            InstalledCount = $installedCount
            Updates = $updates
        }} | ConvertTo-Json -Depth 3 -Compress
    }} catch {{
        @{{
            Success = $false
            Error = $_.Exception.Message
            Updates = @()
        }} | ConvertTo-Json -Compress
    }}
    """
    res = _run_ps_json(ps_script, timeout=120)
    if not res:
        return {
            "success": False,
            "message": "Não foi possível consultar o Windows Update (verifique conexão e privilégios de Administrador).",
            "updates": [],
        }
    return {
        "success": bool(res.get("Success")),
        "found_count": res.get("FoundCount", 0),
        "installed_count": res.get("InstalledCount", 0),
        "updates": res.get("Updates") or [],
        "message": res.get("Error") or f"{res.get('FoundCount', 0)} atualizações de driver encontradas no Windows Update.",
    }
