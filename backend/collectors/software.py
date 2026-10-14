#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/collectors/software.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
================================================================================
Descrição:
1. Inventaria todos os softwares instalados no computador (Registro 64-bit,
   32-bit e perfil do usuário).
2. Verifica softwares obsoletos com atualização disponível via Windows Package
   Manager (winget upgrade).
3. Permite atualizar um software específico, atualizar todos os obsoletos ou
   instalar pacotes essenciais pós-formatação via Winget.
"""

import json
import platform
import subprocess


ESSENTIAL_CATALOG = [
    {"id": "Google.Chrome", "name": "Google Chrome", "category": "Navegadores"},
    {"id": "Mozilla.Firefox", "name": "Mozilla Firefox", "category": "Navegadores"},
    {"id": "7zip.7zip", "name": "7-Zip", "category": "Utilitários"},
    {"id": "VideoLAN.VLC", "name": "VLC Media Player", "category": "Multimídia"},
    {"id": "Adobe.Acrobat.Reader.64-bit", "name": "Adobe Acrobat Reader DC", "category": "Documentos"},
    {"id": "TheDocumentFoundation.LibreOffice", "name": "LibreOffice", "category": "Documentos"},
    {"id": "AnyDeskSoftwareGmbH.AnyDesk", "name": "AnyDesk", "category": "Acesso Remoto"},
    {"id": "RustDesk.RustDesk", "name": "RustDesk (Open Source)", "category": "Acesso Remoto"},
    {"id": "CPUID.CPU-Z", "name": "CPU-Z", "category": "Diagnóstico"},
    {"id": "CPUID.HWMonitor", "name": "HWMonitor", "category": "Diagnóstico"},
    {"id": "CrystalDewWorld.CrystalDiskInfo", "name": "CrystalDiskInfo", "category": "Diagnóstico"},
    {"id": "Malwarebytes.Malwarebytes", "name": "Malwarebytes Anti-Malware", "category": "Segurança"},
]


def _run_ps_json(ps_script: str, timeout: int = 35):
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        out = res.stdout.strip()
        return json.loads(out) if out else None
    except Exception:
        return None


def collect_installed_software() -> dict:
    """Lista os programas instalados e verifica quais possuem atualização no Winget."""
    installed = []
    if platform.system() == "Windows":
        ps_query = r"""
        $ErrorActionPreference = 'SilentlyContinue'
        $paths = @(
            'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
        )
        $apps = Get-ItemProperty $paths | Where-Object { $_.DisplayName -ne $null } |
            Select-Object DisplayName, DisplayVersion, Publisher, InstallDate |
            Sort-Object DisplayName -Unique
        @($apps) | ConvertTo-Json -Depth 2 -Compress
        """
        raw = _run_ps_json(ps_query)
        if isinstance(raw, dict):
            raw = [raw]
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                installed.append({
                    "name": (item.get("DisplayName") or "").strip(),
                    "version": (item.get("DisplayVersion") or "N/D").strip(),
                    "publisher": (item.get("Publisher") or "N/D").strip(),
                    "install_date": (item.get("InstallDate") or "N/D").strip(),
                })
    else:
        installed = [
            {"name": "Google Chrome", "version": "129.0.6668.90", "publisher": "Google LLC", "install_date": "20260910"},
            {"name": "7-Zip 24.08 (x64)", "version": "24.08", "publisher": "Igor Pavlov", "install_date": "20260801"},
            {"name": "VLC media player", "version": "3.0.20", "publisher": "VideoLAN", "install_date": "20260512"},
        ]

    outdated = check_outdated_winget()
    return {
        "total_installed": len(installed),
        "installed_software": installed[:250],
        "outdated_count": len(outdated),
        "outdated_software": outdated,
        "essential_catalog": ESSENTIAL_CATALOG,
    }


def check_outdated_winget() -> list:
    """Executa 'winget upgrade' e extrai pacotes obsoletos com versão nova disponível."""
    if platform.system() != "Windows":
        return [
            {
                "name": "VLC media player",
                "id": "VideoLAN.VLC",
                "current_version": "3.0.20",
                "available_version": "3.0.21",
                "source": "winget",
            }
        ]

    try:
        res = subprocess.run(
            ["winget", "upgrade", "--include-unknown", "--accept-source-agreements"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
        )
        lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
        outdated = []
        parsing = False
        for ln in lines:
            if ln.startswith("---") and len(ln) > 15:
                parsing = True
                continue
            if not parsing:
                continue
            if "upgrades available" in ln.lower() or "atualizações disponíveis" in ln.lower():
                break
            parts = ln.split()
            if len(parts) >= 4 and parts[-1].lower() == "winget":
                source = parts[-1]
                avail_ver = parts[-2]
                curr_ver = parts[-3]
                pkg_id = parts[-4]
                pkg_name = " ".join(parts[:-4]) or pkg_id
                outdated.append({
                    "name": pkg_name,
                    "id": pkg_id,
                    "current_version": curr_ver,
                    "available_version": avail_ver,
                    "source": source,
                })
        return outdated
    except Exception:
        return []


def run_winget_action(action: str, package_id: str = "") -> dict:
    """
    Executa instalação ou atualização via Winget:
    - action == 'upgrade_one': atualiza package_id
    - action == 'upgrade_all': atualiza todos os obsoletos
    - action == 'install': instala package_id do catálogo
    """
    if platform.system() != "Windows":
        return {
            "success": True,
            "message": f"[Modo Simulação] Comando winget ({action} {package_id}) validado com sucesso.",
            "output": "Operação disponível nativamente em estações Windows 10/11 com Winget.",
        }

    if action == "upgrade_all":
        cmd = [
            "winget", "upgrade", "--all", "--silent",
            "--accept-package-agreements", "--accept-source-agreements",
        ]
    elif action == "upgrade_one" and package_id:
        cmd = [
            "winget", "upgrade", "--id", package_id, "--silent",
            "--accept-package-agreements", "--accept-source-agreements",
        ]
    elif action == "install" and package_id:
        cmd = [
            "winget", "install", "--id", package_id, "--silent",
            "--accept-package-agreements", "--accept-source-agreements",
        ]
    else:
        return {"success": False, "message": "Parâmetros inválidos para o Winget.", "output": ""}

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        ok = res.returncode == 0
        return {
            "success": ok,
            "message": "Operação Winget concluída." if ok else f"Winget retornou código {res.returncode}.",
            "output": (res.stdout + "\n" + res.stderr).strip()[-2000:],
        }
    except Exception as exc:
        return {"success": False, "message": f"Erro ao executar Winget: {exc}", "output": ""}
