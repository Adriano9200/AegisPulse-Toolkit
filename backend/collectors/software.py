#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/collectors/software.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
VERSÃO:  1.1.0
================================================================================
Descrição:
1. Inventaria todos os softwares instalados (com UTF-8 e UninstallString) para
   permitir a DESINSTALAÇÃO de qualquer programa direto pela interface;
2. Detecta softwares obsoletos via Winget (tratando corretamente o símbolo '<');
3. Escaneia e remove com segurança Bloatwares (Apps UWP pré-instalados no
   Windows 10/11) individualmente ou em lote.
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

KNOWN_BLOATWARE_PATTERNS = [
    {"pattern": "Microsoft.549981C3F5F10", "title": "Cortana Assistant", "desc": "Assistente de voz legada do Windows"},
    {"pattern": "Microsoft.BingNews", "title": "Microsoft News / Bing Notícias", "desc": "App de notícias pré-instalado"},
    {"pattern": "Microsoft.BingWeather", "title": "Microsoft Bing Clima", "desc": "App de previsão do tempo"},
    {"pattern": "Microsoft.Getstarted", "title": "Dicas do Windows (Tips)", "desc": "Pop-ups de sugestões e dicas"},
    {"pattern": "Microsoft.GetHelp", "title": "Obter Ajuda (Get Help)", "desc": "Assistente básico de suporte"},
    {"pattern": "Microsoft.MicrosoftSolitaireCollection", "title": "Microsoft Solitaire Collection", "desc": "Jogos de cartas pré-instalados com anúncios"},
    {"pattern": "Microsoft.MixedReality.Portal", "title": "Mixed Reality Portal", "desc": "Portal de realidade mista não utilizado"},
    {"pattern": "Microsoft.People", "title": "Microsoft People (Pessoas)", "desc": "Barra de contatos legada"},
    {"pattern": "Microsoft.SkypeApp", "title": "Skype UWP", "desc": "Versão pré-instalada do Skype"},
    {"pattern": "Microsoft.WindowsFeedbackHub", "title": "Hub de Comentários (Feedback Hub)", "desc": "Coletor de telemetria e feedback"},
    {"pattern": "Microsoft.WindowsMaps", "title": "Mapas do Windows", "desc": "App de mapas offline raramente usado em desktops"},
    {"pattern": "Microsoft.ZuneVideo", "title": "Filmes e TV (Zune Video)", "desc": "Player legado com loja de aluguel"},
    {"pattern": "Microsoft.ZuneMusic", "title": "Groove Música / Media Player UWP", "desc": "Player de música pré-instalado"},
    {"pattern": "Clipchamp.Clipchamp", "title": "Microsoft Clipchamp", "desc": "Editor de vídeo web pré-instalado"},
    {"pattern": "Microsoft.Todos", "title": "Microsoft To Do", "desc": "Lista de tarefas UWP"},
    {"pattern": "Microsoft.PowerAutomateDesktop", "title": "Power Automate Desktop", "desc": "Automação corporativa pré-instalada"},
    {"pattern": "Microsoft.YourPhone", "title": "Vincular ao Celular (Phone Link)", "desc": "Sincronização em segundo plano com smartphone"},
    {"pattern": "king.com.CandyCrush", "title": "Candy Crush (Promocional)", "desc": "Jogo promocional pré-instalado"},
    {"pattern": "SpotifyAB.SpotifyMusic", "title": "Spotify Store Edition", "desc": "App promocional pré-instalado"},
    {"pattern": "Disney.37853FC22B2CE", "title": "Disney+ Promocional", "desc": "Atalho/App promocional"},
]


def _run_ps_json(ps_script: str, timeout: int = 35):
    utf8_prefix = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", utf8_prefix + ps_script]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        out = res.stdout.strip()
        return json.loads(out) if out else None
    except Exception:
        return None


def collect_bloatware_apps() -> list:
    """Detecta quais Bloatwares UWP da lista segura estão presentes na máquina."""
    if platform.system() != "Windows":
        return [
            {"package_name": "Microsoft.BingNews", "title": "Microsoft News / Bing Notícias", "desc": "App de notícias pré-instalado"},
            {"package_name": "Microsoft.MicrosoftSolitaireCollection", "title": "Microsoft Solitaire Collection", "desc": "Jogos de cartas pré-instalados"},
        ]

    ps_query = r"""
    $ErrorActionPreference = 'SilentlyContinue'
    $installed = @(Get-AppxPackage | Select-Object Name, PackageFullName)
    $installed | ConvertTo-Json -Depth 2 -Compress
    """
    raw = _run_ps_json(ps_query, timeout=25)
    if isinstance(raw, dict):
        raw = [raw]
    installed_names = set()
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("Name"):
                installed_names.add(str(item.get("Name")))

    detected = []
    for bw in KNOWN_BLOATWARE_PATTERNS:
        pat = bw["pattern"].lower()
        for inst_name in installed_names:
            if pat in inst_name.lower():
                detected.append({
                    "package_name": inst_name,
                    "title": bw["title"],
                    "desc": bw["desc"],
                })
                break
    return detected


def remove_bloatware(package_names: list[str]) -> dict:
    """Remove os pacotes Appx (Bloatwares) selecionados para o usuário e provisionados."""
    if not package_names:
        return {"success": False, "message": "Nenhum bloatware selecionado para remoção.", "removed": []}

    if platform.system() != "Windows":
        return {
            "success": True,
            "message": f"[Simulação] {len(package_names)} bloatware(s) removido(s) com sucesso.",
            "removed": package_names,
        }

    removed = []
    errors = []
    for pkg in package_names:
        safe_pkg = pkg.replace("'", "").replace('"', "").strip()
        ps_cmd = f"""
        $ErrorActionPreference = 'SilentlyContinue'
        Get-AppxPackage -AllUsers *{safe_pkg}* | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue
        Get-AppxPackage *{safe_pkg}* | Remove-AppxPackage -ErrorAction SilentlyContinue
        Get-AppxProvisionedPackage -Online | Where-Object DisplayName -like '*{safe_pkg}*' | Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue
        """
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=40,
            )
            removed.append(safe_pkg)
        except Exception as exc:
            errors.append(f"{safe_pkg}: {exc}")

    return {
        "success": len(removed) > 0,
        "message": f"{len(removed)} aplicativo(s) de bloatware removido(s) com sucesso.",
        "removed": removed,
        "errors": errors,
    }


def collect_installed_software() -> dict:
    """Lista programas instalados, softwares obsoletos e bloatwares detectados."""
    installed = []
    if platform.system() == "Windows":
        ps_query = r"""
        $ErrorActionPreference = 'SilentlyContinue'
        $paths = @(
            'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
        )
        $apps = Get-ItemProperty $paths | Where-Object { $_.DisplayName -ne $null -and $_.SystemComponent -ne 1 } |
            Select-Object DisplayName, DisplayVersion, Publisher, InstallDate, UninstallString, QuietUninstallString, PSChildName |
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
                    "uninstall_cmd": (item.get("QuietUninstallString") or item.get("UninstallString") or "").strip(),
                    "reg_key": (item.get("PSChildName") or "").strip(),
                })
    else:
        installed = [
            {"name": "Google Chrome", "version": "129.0.6668.90", "publisher": "Google LLC", "install_date": "20260910", "uninstall_cmd": "winget", "reg_key": "Google.Chrome"},
            {"name": "7-Zip 26.04 (x64)", "version": "26.04", "publisher": "Igor Pavlov", "install_date": "20261014", "uninstall_cmd": "winget", "reg_key": "7zip.7zip"},
        ]

    outdated = check_outdated_winget()
    bloatware = collect_bloatware_apps()
    return {
        "total_installed": len(installed),
        "installed_software": installed[:300],
        "outdated_count": len(outdated),
        "outdated_software": outdated,
        "bloatware_count": len(bloatware),
        "bloatware_list": bloatware,
        "essential_catalog": ESSENTIAL_CATALOG,
    }


def check_outdated_winget() -> list:
    """Executa 'winget upgrade' tratando símbolos '<' nas colunas de versão."""
    if platform.system() != "Windows":
        return [
            {
                "name": "VLC media player",
                "id": "VideoLAN.VLC",
                "current_version": "3.0.23",
                "available_version": "3.0.24",
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
            cleaned_ln = ln.replace(" < ", " ")
            parts = cleaned_ln.split()
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


def run_winget_action(action: str, package_id: str = "", app_name: str = "") -> dict:
    """
    Executa instalação, atualização ou desinstalação via Winget:
    - 'upgrade_one': atualiza package_id
    - 'upgrade_all': atualiza todos os obsoletos
    - 'install': instala package_id
    - 'uninstall': desinstala pelo ID ou nome exato do programa
    """
    if platform.system() != "Windows":
        return {
            "success": True,
            "message": f"[Simulação] Operação Winget ({action}: {package_id or app_name}) concluída.",
            "output": "Executado em modo de validação.",
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
    elif action == "uninstall":
        target = package_id or app_name
        if not target:
            return {"success": False, "message": "Nome do programa não informado para desinstalação.", "output": ""}
        cmd = [
            "winget", "uninstall", "--name", target, "--silent",
            "--accept-source-agreements",
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
            "message": f"Operação ({action}) concluída com sucesso para '{package_id or app_name}'." if ok else f"Winget retornou código {res.returncode} (alguns desinstaladores exigem confirmação na tela).",
            "output": (res.stdout + "\n" + res.stderr).strip()[-2000:],
        }
    except Exception as exc:
        return {"success": False, "message": f"Erro ao executar Winget: {exc}", "output": ""}
