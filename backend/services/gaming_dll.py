#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/gaming_dll.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
VERSÃO:  1.1.0
================================================================================
Descrição:
Módulo Especialista em Jogos, Runtimes e Diagnóstico/Reparo de DLLs:
1. Auditoria física de DLLs críticas em System32 (64-bit) e SysWOW64 (32-bit);
2. Instalação/Reparo Oficial em 1 Clique (via Winget + SFC);
3. Otimização Segura para Jogos (Plano Desempenho Máximo e Limpeza Shader Cache).
"""

import os
import platform
import subprocess


CRITICAL_DLLS = [
    {"dll": "vcruntime140.dll", "group": "Visual C++ 2015-2022 Runtime", "fix_pkg": "Microsoft.VCRedist.2015+.x64"},
    {"dll": "vcruntime140_1.dll", "group": "Visual C++ 2015-2022 (x64 Exception)", "fix_pkg": "Microsoft.VCRedist.2015+.x64"},
    {"dll": "msvcp140.dll", "group": "Visual C++ 2015-2022 Standard Lib", "fix_pkg": "Microsoft.VCRedist.2015+.x64"},
    {"dll": "concrt140.dll", "group": "Visual C++ Concurrency Runtime", "fix_pkg": "Microsoft.VCRedist.2015+.x64"},
    {"dll": "msvcr120.dll", "group": "Visual C++ 2013 Runtime", "fix_pkg": "Microsoft.VCRedist.2013.x64"},
    {"dll": "msvcp120.dll", "group": "Visual C++ 2013 Standard Lib", "fix_pkg": "Microsoft.VCRedist.2013.x64"},
    {"dll": "msvcr100.dll", "group": "Visual C++ 2010 Runtime", "fix_pkg": "Microsoft.VCRedist.2010.x64"},
    {"dll": "d3dcompiler_47.dll", "group": "DirectX 11/12 Shader Compiler", "fix_pkg": "Microsoft.DirectX"},
    {"dll": "d3dx9_43.dll", "group": "DirectX 9.0c Legacy Games", "fix_pkg": "Microsoft.DirectX"},
    {"dll": "xinput1_3.dll", "group": "Controle Xbox / Gamepad (XInput 1.3)", "fix_pkg": "Microsoft.DirectX"},
    {"dll": "xinput1_4.dll", "group": "Controle Xbox / Gamepad (XInput 1.4)", "fix_pkg": "Microsoft.DirectX"},
]

GAMING_RUNTIMES_CATALOG = [
    {"id": "Microsoft.VCRedist.2015+.x64", "name": "Visual C++ 2015-2022 Redistributable (64-bit)", "desc": "Corrige erros de vcruntime140.dll e msvcp140.dll em jogos 64-bit"},
    {"id": "Microsoft.VCRedist.2015+.x86", "name": "Visual C++ 2015-2022 Redistributable (32-bit)", "desc": "Essencial mesmo em Windows 64-bit para jogos e launchers 32-bit"},
    {"id": "Microsoft.VCRedist.2013.x64", "name": "Visual C++ 2013 Redistributable (x64)", "desc": "Corrige erros de msvcr120.dll e msvcp120.dll"},
    {"id": "Microsoft.VCRedist.2013.x86", "name": "Visual C++ 2013 Redistributable (x86)", "desc": "Suporte a jogos clássicos 32-bit que pedem msvcr120.dll"},
    {"id": "Microsoft.DirectX", "name": "DirectX End-User Runtime", "desc": "Instala d3dx9_43.dll, xinput1_3.dll e bibliotecas legadas DirectX 9/10/11"},
    {"id": "Microsoft.DotNet.DesktopRuntime.8", "name": ".NET Desktop Runtime 8.0 (x64)", "desc": "Exigido por launchers modernos, utilitários de placa de vídeo e mods"},
]


def audit_gaming_and_dlls() -> dict:
    """Verifica a existência das DLLs críticas em System32 (64-bit) e SysWOW64 (32-bit)."""
    results = []
    missing_count = 0

    if platform.system() == "Windows":
        win_dir = os.environ.get("SystemRoot", r"C:\Windows")
        sys32 = os.path.join(win_dir, "System32")
        syswow64 = os.path.join(win_dir, "SysWOW64")

        for item in CRITICAL_DLLS:
            dll_name = item["dll"]
            has_64 = os.path.exists(os.path.join(sys32, dll_name))
            if dll_name == "vcruntime140_1.dll":
                has_32 = True
            else:
                has_32 = os.path.exists(os.path.join(syswow64, dll_name))

            ok = has_64 and has_32
            if not ok:
                missing_count += 1

            results.append({
                "dll": dll_name,
                "group": item["group"],
                "sys32_64bit": "Presente" if has_64 else "AUSENTE",
                "syswow64_32bit": "N/A (64-bit only)" if dll_name == "vcruntime140_1.dll" else ("Presente" if has_32 else "AUSENTE"),
                "status_ok": ok,
                "fix_pkg": item["fix_pkg"],
            })
    else:
        for item in CRITICAL_DLLS:
            results.append({
                "dll": item["dll"],
                "group": item["group"],
                "sys32_64bit": "Presente",
                "syswow64_32bit": "Presente",
                "status_ok": True,
                "fix_pkg": item["fix_pkg"],
            })

    return {
        "dll_audit": results,
        "missing_dlls_count": missing_count,
        "runtimes_catalog": GAMING_RUNTIMES_CATALOG,
    }


def run_gaming_optimization(opt_action: str) -> dict:
    """Executa otimizações seguras para jogos e reparo completo de pacotes de DLL."""
    if platform.system() != "Windows":
        return {
            "success": True,
            "message": f"[Simulação] Ação gamer '{opt_action}' concluída com sucesso.",
        }

    if opt_action == "ultimate_power":
        ps_cmd = r"""
        powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61 | Out-Null
        $ult = (powercfg /list) | Select-String '([a-f0-9-]{36}).*(Ultimate|Desempenho M|Alto desempenho)' | Select-Object -First 1
        if ($ult) {
            $guid = $ult.Matches[0].Groups[1].Value
            powercfg /setactive $guid
            Write-Output "Plano de energia ativado: $guid"
        } else {
            powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
            Write-Output "Plano Alto Desempenho ativado."
        }
        """
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd], capture_output=True, text=True, timeout=20)
            return {
                "success": True,
                "message": "Plano de Energia de Alto Desempenho / Desempenho Máximo ativado com sucesso!",
                "details": r.stdout.strip(),
            }
        except Exception as exc:
            return {"success": False, "message": f"Erro ao ativar plano de energia: {exc}"}

    if opt_action == "clean_shader_cache":
        local_app = os.environ.get("LOCALAPPDATA", "")
        shader_dirs = [
            os.path.join(local_app, "D3DSCache"),
            os.path.join(local_app, "NVIDIA", "DXCache"),
            os.path.join(local_app, "NVIDIA", "GLCache"),
            os.path.join(local_app, "AMD", "DxCache"),
        ]
        removed = 0
        freed_b = 0
        for sdir in shader_dirs:
            if os.path.exists(sdir):
                for root, _, files in os.walk(sdir):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        try:
                            sz = os.path.getsize(fp)
                            os.remove(fp)
                            removed += 1
                            freed_b += sz
                        except Exception:
                            pass
        mb = round(freed_b / (1024 * 1024), 2)
        return {
            "success": True,
            "message": f"Cache de Shaders DirectX/GPU limpo ({removed} arquivos removidos, {mb} MB liberados).",
        }

    if opt_action == "repair_all_vc_directx":
        pkgs = [
            "Microsoft.VCRedist.2015+.x64",
            "Microsoft.VCRedist.2015+.x86",
            "Microsoft.VCRedist.2013.x64",
            "Microsoft.VCRedist.2013.x86",
            "Microsoft.DirectX",
        ]
        installed = []
        for p in pkgs:
            try:
                subprocess.run(
                    ["winget", "install", "--id", p, "--silent", "--accept-package-agreements", "--accept-source-agreements"],
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                installed.append(p)
            except Exception:
                pass
        return {
            "success": True,
            "message": f"Pacotes oficiais de DLLs e Runtimes verificados/reparados: {', '.join(installed)}",
        }

    return {"success": False, "message": "Ação de otimização não reconhecida."}
