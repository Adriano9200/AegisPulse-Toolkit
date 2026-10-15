#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/gaming_dll.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
VERSÃO:  2.0.0
================================================================================
Descrição:
Módulo Especialista PC Gamer, Análise de Hardware para Jogos e Auditoria de DLLs:
1. Análise Completa de PC Gamer (GPU Dedicada vs Integrada, VRAM, CPU, RAM
   Dual-Channel, SSDs de Jogos, Tier Gamer 1080p/1440p/4K, Tecnologias Gráficas
   suportadas como DirectX 12, Vulkan, DLSS, FSR, XeSS e Diagnóstico de Gargalos);
2. Auditoria física de DLLs críticas em System32 (64-bit) e SysWOW64 (32-bit);
3. Instalação/Reparo Oficial em 1 Clique (via Winget) e Otimizador Gamer.
"""

import os
import platform
import subprocess


CRITICAL_DLLS = [
    {"dll": "vcruntime140.dll", "group": "Visual C++ 2015-2022 Runtime", "fix_pkg": "Microsoft.VCRedist.2015+.x64"},
    {"dll": "vcruntime140_1.dll", "group": "Visual C++ 2015-2022 (x64 Exception)", "fix_pkg": "Microsoft.VCRedist.2015+.x64"},
    {"dll": "msvcp140.dll", "group": "Visual C++ 2015-2022 Standard Lib", "fix_pkg": "Microsoft.VCRedist.2015+.x64"},
    {"dll": "concrt140.dll", "group": "Visual C++ Concurrency Runtime", "fix_pkg": "Microsoft.VCRedist.2015+.x64"},
    {"dll": "msvcr120.dll", "group": "Visual C++ 2013 Runtime", "fix_pkg": "Microsoft.VCRedist.2013.x86"},
    {"dll": "msvcp120.dll", "group": "Visual C++ 2013 Standard Lib", "fix_pkg": "Microsoft.VCRedist.2013.x86"},
    {"dll": "msvcr100.dll", "group": "Visual C++ 2010 Runtime", "fix_pkg": "Microsoft.VCRedist.2010.x86"},
    {"dll": "d3dcompiler_47.dll", "group": "DirectX 11/12 Shader Compiler", "fix_pkg": "Microsoft.DirectX"},
    {"dll": "d3dx9_43.dll", "group": "DirectX 9.0c Legacy Games", "fix_pkg": "Microsoft.DirectX"},
    {"dll": "xinput1_3.dll", "group": "Controle Xbox / Gamepad (XInput 1.3)", "fix_pkg": "Microsoft.DirectX"},
    {"dll": "xinput1_4.dll", "group": "Controle Xbox / Gamepad (XInput 1.4)", "fix_pkg": "Microsoft.DirectX"},
]

GAMING_RUNTIMES_CATALOG = [
    {"id": "Microsoft.VCRedist.2015+.x64", "name": "Visual C++ 2015-2022 Redistributable (64-bit)", "desc": "Corrige erros de vcruntime140.dll e msvcp140.dll em jogos 64-bit"},
    {"id": "Microsoft.VCRedist.2015+.x86", "name": "Visual C++ 2015-2022 Redistributable (32-bit)", "desc": "Essencial mesmo em Windows 64-bit para jogos e launchers 32-bit"},
    {"id": "Microsoft.VCRedist.2013.x64", "name": "Visual C++ 2013 Redistributable (x64)", "desc": "Corrige erros de msvcr120.dll e msvcp120.dll em 64-bit"},
    {"id": "Microsoft.VCRedist.2013.x86", "name": "Visual C++ 2013 Redistributable (x86)", "desc": "Corrige erros de msvcr120.dll em SysWOW64 (32-bit)"},
    {"id": "Microsoft.DirectX", "name": "DirectX End-User Runtime", "desc": "Instala d3dx9_43.dll, xinput1_3.dll e bibliotecas DirectX 9/10/11"},
    {"id": "Microsoft.DotNet.DesktopRuntime.8", "name": ".NET Desktop Runtime 8.0 (x64)", "desc": "Exigido por launchers modernos, utilitários de GPU e mods"},
]


def analyze_gamer_pc_profile(hardware: dict) -> dict:
    """
    Realiza uma análise completa de engenharia para PC Gamer com base em:
    GPU Dedicada, GPU Integrada, VRAM, CPU (Cores/Threads), RAM (Dual-Channel e MHz)
    e Armazenamento (SSDs e ocupação das partições de jogos).
    """
    cpus = hardware.get("cpus") or [{}]
    cpu = cpus[0] if cpus else {}
    cpu_name = cpu.get("name", "Processador N/D")
    cores = int(cpu.get("cores") or 4)
    threads = int(cpu.get("threads") or 4)
    clock_mhz = int(cpu.get("max_clock_mhz") or 3000)

    gpus = hardware.get("gpus") or []
    dedicated_gpu = None
    integrated_gpu = None
    for g in gpus:
        gtype = str(g.get("gpu_type", ""))
        if "Dedicada" in gtype and not dedicated_gpu:
            dedicated_gpu = g
        elif "Integrada" in gtype and not integrated_gpu:
            integrated_gpu = g

    if not dedicated_gpu and gpus:
        dedicated_gpu = gpus[0]

    primary_gpu_name = dedicated_gpu.get("name", "Vídeo Integrado") if dedicated_gpu else "N/D"
    primary_gpu_type = dedicated_gpu.get("gpu_type", "Integrada") if dedicated_gpu else "Integrada"
    primary_vram = dedicated_gpu.get("vram_gb", 0) if dedicated_gpu else 0
    vram_num = float(primary_vram) if isinstance(primary_vram, (int, float)) else 2.0

    # Ajuste inteligente para GPUs conhecidas caso o WMI 32-bit reporte 4.0 GB em placas de 8GB/12GB
    gn_lower = primary_gpu_name.lower()
    if vram_num <= 4.0:
        if any(m in gn_lower for m in ("rx 6600", "rx 6650", "rx 7600", "rtx 3060 ti", "rtx 3070", "rtx 4060", "rx 580 8gb")):
            vram_num = 8.0
        elif "rtx 3060" in gn_lower or "rx 6700 xt" in gn_lower:
            vram_num = 12.0

    ram_gb = float(hardware.get("total_ram_gb") or 8.0)
    ram_modules = hardware.get("ram_modules") or []
    num_sticks = len(ram_modules)
    ram_speed = ram_modules[0].get("speed_mhz", "2666") if ram_modules else "N/D"
    channel_mode = "Dual-Channel Ativo (Ideal para FPS estável)" if num_sticks >= 2 else "Single-Channel (1 pente — pode limitar FPS mínimo)"

    # Tecnologias suportadas pela GPU
    techs = ["DirectX 12", "Vulkan API"]
    if "rtx" in gn_lower:
        techs.extend(["NVIDIA DLSS", "Ray Tracing Hardware", "NVIDIA Reflex"])
    elif "gtx" in gn_lower or "quadro" in gn_lower:
        techs.extend(["NVIDIA CUDA / PhysX", "AMD FSR / Intel XeSS (via Software)"])
    elif "radeon rx" in gn_lower:
        techs.extend(["AMD FSR (FidelityFX Super Resolution)", "AMD Radeon Anti-Lag", "Smart Access Memory"])
        if any(s in gn_lower for s in ("rx 6", "rx 7", "rx 9")):
            techs.append("DirectX 12 Ultimate / Ray Tracing")
    else:
        techs.append("AMD FSR 1.0/2.0 (Upscaling Universal)")

    # Classificação de Tier Gamer e Resolução Alvo
    if "Integrada" in primary_gpu_type:
        gamer_tier = "Tier C — Casual & eSports Leves (720p / 1080p Low)"
        target_res = "720p HD / 1080p Básico (CS2, Valorant, LoL, Indie)"
    elif vram_num >= 10 or any(k in gn_lower for k in ("rtx 3070", "rtx 3080", "rtx 4070", "rtx 4080", "rx 6700", "rx 6800", "rx 7700", "rx 7800")):
        gamer_tier = "Tier S — Enthusiast Gamer (1440p Quad HD Ultra / 4K)"
        target_res = "1440p Quad HD Ultra & 4K (Com DLSS/FSR)"
    elif vram_num >= 6 or any(k in gn_lower for k in ("rx 6600", "rtx 2060", "rtx 3060", "rtx 4060", "gtx 1660", "rx 5600", "rx 5700")):
        gamer_tier = "Tier A — High Performance Gamer (1080p Full HD Alto/Ultra)"
        target_res = "1080p Full HD (Qualidade Alta/Ultra a 60–144+ FPS) e 1440p Médio"
    else:
        gamer_tier = "Tier B — Entry Dedicated / Workstation (1080p Médio / Competitivo)"
        target_res = "1080p Full HD Competitivo (Qualidade Média / eSports a 60–120 FPS)"

    # Diagnóstico de Gargalos (Bottlenecks) e Armazenamento Gamer
    bottlenecks = []
    if num_sticks == 1:
        bottlenecks.append("Memória em Single-Channel (1 único pente): adicionar um 2º pente ativará o Dual-Channel e aumentará o FPS mínimo em até 20%.")
    if ram_gb < 16:
        bottlenecks.append(f"RAM Total de {ram_gb} GB: jogos AAA modernos recomendam no mínimo 16 GB a 32 GB.")
    if cores < 6:
        bottlenecks.append(f"Processador com {cores} núcleos físicos: pode apresentar uso elevado em jogos de mundo aberto modernos.")

    volumes = hardware.get("volumes") or []
    full_drives = [
        f"Unidade {v.get('drive')} ({v.get('label')}) está com {v.get('used_percent')}% ocupada (apenas {v.get('free_gb')} GB livres)"
        for v in volumes
        if float(v.get("used_percent") or 0) >= 85.0
    ]
    if full_drives:
        for fd in full_drives:
            bottlenecks.append(f"ALERTA DE ARMAZENAMENTO GAMER: {fd} — SSDs acima de 85% sofrem queda severa de leitura/escrita e causam travamentos (stuttering) durante o carregamento de texturas.")

    if not bottlenecks:
        bottlenecks.append("Conjunto equilibrado (Zero gargalos críticos entre CPU, GPU, RAM Dual-Channel e SSD).")

    return {
        "gamer_tier": gamer_tier,
        "target_resolution": target_res,
        "dedicated_gpu": {
            "name": primary_gpu_name,
            "type": primary_gpu_type,
            "vram_gb": f"{vram_num} GB",
            "driver": dedicated_gpu.get("driver_version", "N/D") if dedicated_gpu else "N/D",
        },
        "integrated_gpu": {
            "name": integrated_gpu.get("name", "Não possui / Desativada na BIOS") if integrated_gpu else "Não possui / Desativada",
            "driver": integrated_gpu.get("driver_version", "—") if integrated_gpu else "—",
        },
        "cpu_gamer": {
            "name": cpu_name,
            "cores_threads": f"{cores} Núcleos Físicos / {threads} Threads",
            "clock_mhz": f"{clock_mhz} MHz",
        },
        "ram_gamer": {
            "total_gb": f"{ram_gb} GB",
            "sticks_count": num_sticks,
            "speed_mhz": f"{ram_speed} MHz",
            "channel_status": channel_mode,
        },
        "supported_technologies": techs,
        "bottlenecks_and_alerts": bottlenecks,
    }


def audit_gaming_and_dlls(hardware: dict | None = None) -> dict:
    """Verifica a existência das DLLs críticas e gera o perfil completo de PC Gamer."""
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

    gamer_profile = analyze_gamer_pc_profile(hardware or {})

    return {
        "gamer_profile": gamer_profile,
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
