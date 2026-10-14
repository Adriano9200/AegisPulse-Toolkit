#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/network_tools.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
VERSÃO:  1.1.0
================================================================================
Descrição:
Módulo completo de Diagnóstico e Otimização de Rede & Internet:
1. Inventário de Adaptadores de Rede ativos (IPv4, MAC, Gateway, DNS, Velocidade);
2. Teste de Latência (Ping) para Gateway, Cloudflare (1.1.1.1) e Google (8.8.8.8);
3. Teste de Velocidade de Download HTTP (Speedtest seguro via Cloudflare CDN);
4. Recuperador de Perfis e Senhas de Wi-Fi salvas no Windows (netsh wlan);
5. Trocador Rápido de DNS em 1 clique (Cloudflare 1.1.1.1, Google 8.8.8.8,
   Cloudflare Security 1.1.1.2 anti-malware ou DHCP Automático).
"""

import json
import time
import platform
import subprocess
import urllib.request


DNS_PRESETS = {
    "cloudflare": {"name": "Cloudflare DNS (Ultra Rápido / Gamer)", "primary": "1.1.1.1", "secondary": "1.0.0.1"},
    "google": {"name": "Google Public DNS (Alta Estabilidade)", "primary": "8.8.8.8", "secondary": "8.8.4.4"},
    "cloudflare_security": {"name": "Cloudflare Security (Bloqueio de Malware/Phishing)", "primary": "1.1.1.2", "secondary": "1.0.0.2"},
    "dhcp": {"name": "Automático da Operadora / Roteador (DHCP)", "primary": "DHCP", "secondary": ""},
}


def _run_ps_json(ps_script: str, timeout: int = 30):
    utf8_prefix = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", utf8_prefix + ps_script]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        out = res.stdout.strip()
        return json.loads(out) if out else None
    except Exception:
        return None


def collect_network_diagnostics() -> dict:
    """Coleta adaptadores de rede ativos, IP, Gateway, DNS e testa latência."""
    adapters = []
    ping_results = []

    if platform.system() == "Windows":
        ps_query = r"""
        $ErrorActionPreference = 'SilentlyContinue'
        $configs = @(Get-NetIPConfiguration | Where-Object { $_.NetAdapter.Status -eq 'Up' } | ForEach-Object {
            @{
                InterfaceAlias = $_.InterfaceAlias
                Description    = $_.InterfaceDescription
                MacAddress     = $_.NetAdapter.MacAddress
                LinkSpeed      = $_.NetAdapter.LinkSpeed
                IPv4Address    = ($_.IPv4Address.IPAddress -join ', ')
                Gateway        = ($_.IPv4DefaultGateway.NextHop -join ', ')
                DNSServers     = ($_.DnsServer.ServerAddresses -join ', ')
            }
        })

        $pings = @()
        foreach ($target in @(
            @{ Name = 'Cloudflare DNS (1.1.1.1)'; Host = '1.1.1.1' },
            @{ Name = 'Google Public DNS (8.8.8.8)'; Host = '8.8.8.8' },
            @{ Name = 'Google Brasil (google.com.br)'; Host = 'google.com.br' }
        )) {
            $p = Test-Connection -ComputerName $target.Host -Count 2 -ErrorAction SilentlyContinue
            if ($p) {
                $avg = [math]::Round(($p | Measure-Object -Property ResponseTime -Average).Average, 1)
                $pings += @{ Target = $target.Name; Host = $target.Host; Reachable = $true; LatencyMs = $avg }
            } else {
                $pings += @{ Target = $target.Name; Host = $target.Host; Reachable = $false; LatencyMs = -1 }
            }
        }

        @{
            Adapters = $configs
            Pings    = $pings
        } | ConvertTo-Json -Depth 3 -Compress
        """
        raw = _run_ps_json(ps_query, timeout=35)
        if raw and isinstance(raw, dict):
            adapters = raw.get("Adapters") or []
            if isinstance(adapters, dict):
                adapters = [adapters]
            ping_results = raw.get("Pings") or []
            if isinstance(ping_results, dict):
                ping_results = [ping_results]
    else:
        adapters = [
            {
                "InterfaceAlias": "Ethernet",
                "Description": "Intel(R) Ethernet Connection I219-LM",
                "MacAddress": "00-1A-2B-3C-4D-5E",
                "LinkSpeed": "1 Gbps",
                "IPv4Address": "192.168.1.100",
                "Gateway": "192.168.1.1",
                "DNSServers": "1.1.1.1, 8.8.8.8",
            }
        ]
        ping_results = [
            {"Target": "Cloudflare DNS (1.1.1.1)", "Host": "1.1.1.1", "Reachable": True, "LatencyMs": 12.0},
            {"Target": "Google Public DNS (8.8.8.8)", "Host": "8.8.8.8", "Reachable": True, "LatencyMs": 18.5},
        ]

    return {
        "adapters": adapters,
        "pings": ping_results,
        "dns_presets": DNS_PRESETS,
    }


def apply_dns_preset(preset_key: str) -> dict:
    """Altera o DNS de todos os adaptadores ativos para o preset escolhido."""
    preset = DNS_PRESETS.get(preset_key)
    if not preset:
        return {"success": False, "message": "Preset de DNS inválido."}

    if platform.system() != "Windows":
        return {
            "success": True,
            "message": f"[Simulação] DNS configurado para: {preset['name']}",
        }

    if preset_key == "dhcp":
        ps_cmd = r"""
        Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | ForEach-Object {
            Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ResetServerAddresses
        }
        ipconfig /flushdns | Out-Null
        """
    else:
        p1 = preset["primary"]
        p2 = preset["secondary"]
        ps_cmd = f"""
        Get-NetAdapter | Where-Object {{ $_.Status -eq 'Up' }} | ForEach-Object {{
            Set-DnsClientServerAddress -InterfaceIndex $_.ifIndex -ServerAddresses ('{p1}','{p2}')
        }}
        ipconfig /flushdns | Out-Null
        """

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
        )
        ok = res.returncode == 0
        return {
            "success": ok,
            "message": f"DNS atualizado com sucesso para {preset['name']} ({preset['primary']})." if ok else "Falha ao alterar DNS (execute como Administrador).",
        }
    except Exception as exc:
        return {"success": False, "message": f"Erro ao aplicar DNS: {exc}"}


def recover_wifi_passwords() -> dict:
    """Recupera todas as redes Wi-Fi salvas no Windows e suas respectivas senhas."""
    if platform.system() != "Windows":
        return {
            "success": True,
            "profiles": [
                {"ssid": "WiFi_Escritorio_5G", "password": "(Disponível em notebooks/PCs Windows com Wi-Fi)"},
            ],
            "message": "1 perfil Wi-Fi demonstrativo.",
        }

    ps_script = r"""
    $ErrorActionPreference = 'SilentlyContinue'
    $profiles = (netsh wlan show profiles) | Select-String ':\s+(.+)$' | ForEach-Object { $_.Matches[0].Groups[1].Value.Trim() }
    $results = @()
    foreach ($p in $profiles) {
        if ($p) {
            $details = netsh wlan show profile name="$p" key=clear
            $keyLine = $details | Select-String '(Key Content|Conte.*do da Chave)\s*:\s*(.+)$'
            $pwd = if ($keyLine) { $keyLine.Matches[0].Groups[2].Value.Trim() } else { '(Sem senha / Aberta ou Corporativa)' }
            $results += @{ ssid = $p; password = $pwd }
        }
    }
    @($results) | ConvertTo-Json -Depth 2 -Compress
    """
    raw = _run_ps_json(ps_script, timeout=30)
    if isinstance(raw, dict):
        raw = [raw]
    profiles = raw if isinstance(raw, list) else []
    return {
        "success": True,
        "count": len(profiles),
        "profiles": profiles,
        "message": f"{len(profiles)} perfil(is) Wi-Fi encontrado(s) neste computador." if profiles else "Nenhum perfil Wi-Fi encontrado (este computador usa apenas cabo Ethernet ou não possui placa Wi-Fi).",
    }


def run_download_speedtest() -> dict:
    """Mede a velocidade real de download (Mbps) baixando um bloco de teste de 10 MB."""
    test_url = "https://speed.cloudflare.com/__down?bytes=10000000"
    try:
        req = urllib.request.Request(test_url, headers={"User-Agent": "AegisPulse-SpeedTest/1.1"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        elapsed = max(0.05, time.perf_counter() - t0)
        bits = len(data) * 8
        mbps = round((bits / elapsed) / 1_000_000, 2)
        return {
            "success": True,
            "download_mbps": mbps,
            "bytes_downloaded": len(data),
            "elapsed_seconds": round(elapsed, 2),
            "message": f"Velocidade medida: {mbps} Mbps ({round(len(data)/(1024*1024), 1)} MB em {round(elapsed, 2)}s via Cloudflare CDN).",
        }
    except Exception as exc:
        return {
            "success": False,
            "download_mbps": 0.0,
            "message": f"Não foi possível concluir o teste de velocidade: {exc}",
        }
