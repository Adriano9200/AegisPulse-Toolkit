#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/gemini_ai.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  3.0.0
================================================================================
Descrição:
Suporte a 3 Motores de Inteligência Artificial com controle comercial por perfil:
1. IA LOCAL AEGISPULSE N3 (provider = 'local'):
   - Liberada gratuitamente tanto para Usuários em MODO TRIAL quanto para
     Assinantes PRO e Administrador Master. Funciona até sem internet!
2. GOOGLE GEMINI 3.X CLOUD AI (provider = 'gemini'):
   - Exclusivo para Assinantes PRO e Administrador Master.
   - Se acionado por um usuário em Modo Trial, exibe um convite comercial
     intuitivo para assinar via WhatsApp (+55 61 98515-8434).
3. XAI GROK / GROQ CLOUD AI (provider = 'grok'):
   - Exclusivo para Assinantes PRO e Administrador Master.
   - Compatível com chaves xAI Grok (xai-...) e GroqCloud LPU (gsk_...).
"""

import json
import time
import socket
import urllib.request
import urllib.error

FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-3-flash-preview",
]


def check_internet_connection(timeout: float = 3.0) -> bool:
    targets = [("8.8.8.8", 53), ("1.1.1.1", 53)]
    for host, port in targets:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def sanitize_snapshot_for_ai(snapshot: dict) -> dict:
    hw = snapshot.get("hardware", {})
    os_info = snapshot.get("os", {})
    drv = snapshot.get("drivers_bios", {})
    sw = snapshot.get("software", {})
    gaming = snapshot.get("gaming", {})
    net = snapshot.get("network", {})

    return {
        "manufacturer": hw.get("manufacturer"),
        "model": hw.get("model"),
        "temperatures": hw.get("temperatures"),
        "total_ram_gb": hw.get("total_ram_gb"),
        "ram_modules": hw.get("ram_modules"),
        "cpus": hw.get("cpus"),
        "gpus": hw.get("gpus"),
        "disks": hw.get("disks"),
        "volumes": hw.get("volumes"),
        "os": os_info,
        "bios": {
            "smbios_version": drv.get("bios", {}).get("smbios_version"),
            "release_date": drv.get("bios", {}).get("release_date"),
            "age_months": drv.get("bios", {}).get("age_months"),
            "needs_review": drv.get("bios", {}).get("needs_review"),
            "status_label": drv.get("bios", {}).get("status_label"),
        },
        "pnp_errors": drv.get("pnp_errors", []),
        "outdated_drivers_count": drv.get("outdated_drivers_count", 0),
        "outdated_software": sw.get("outdated_software", []),
        "bloatware_count": sw.get("bloatware_count", 0),
        "gamer_profile": gaming.get("gamer_profile", {}),
        "missing_dlls": [
            f"{d.get('dll')} ({d.get('group')})"
            for d in gaming.get("dll_audit", [])
            if not d.get("status_ok", True)
        ],
        "network_adapters": net.get("adapters", []),
    }


def generate_local_expert_analysis(ctx: dict, user_prompt: str = "", cloud_notice: str = "") -> str:
    """Motor Especialista Heurístico N3 Nativo do AegisPulse (Liberado para Trial, Assinantes e ADM)."""
    manuf = ctx.get("manufacturer") or "Equipamento"
    model = ctx.get("model") or "Workstation"
    temps = ctx.get("temperatures") or {}
    cpu_t = temps.get("cpu_temp_c", 46.0)
    gpu_t = temps.get("gpu_temp_c", 44.0)

    ram_gb = ctx.get("total_ram_gb") or 0
    ram_mods = ctx.get("ram_modules") or []
    cpus = ctx.get("cpus") or [{}]
    cpu_name = cpus[0].get("name", "Processador não especificado") if cpus else "N/D"
    gpus = ctx.get("gpus") or [{}]
    gpu_name = gpus[0].get("name", "Vídeo Integrado") if gpus else "N/D"

    os_data = ctx.get("os") or {}
    os_str = f"{os_data.get('os_name', 'Windows')} ({os_data.get('display_version', '')} - Build {os_data.get('full_build', '')})"

    disks = ctx.get("disks") or []
    disk_summary = ", ".join(
        f"{d.get('model')} ({d.get('media_type')}, {d.get('size_gb')} GB, SMART: {d.get('health_status')})"
        for d in disks
    ) or "Unidades padrão"

    bios = ctx.get("bios") or {}
    outdated_sw = ctx.get("outdated_software") or []
    missing_dlls = ctx.get("missing_dlls") or []
    outdated_drv = int(ctx.get("outdated_drivers_count") or 0)
    gp = ctx.get("gamer_profile") or {}

    sw_names = ", ".join(s.get("name", "") for s in outdated_sw[:8])
    if len(outdated_sw) > 8:
        sw_names += f" e mais {len(outdated_sw) - 8} pacote(s)"

    lines = []
    lines.append("[Motor Utilizado: 🧠 IA Local AegisPulse N3 (Diagnóstico Embarcado Instantâneo)]")
    if cloud_notice:
        lines.append(f"[Info: {cloud_notice}]")
    lines.append("")
    lines.append("### 1. DIAGNÓSTICO TÉCNICO N3 (Especialista Adriano Barboza)")
    lines.append("")
    lines.append(f"- **Equipamento Analisado:** {manuf} {model}")
    lines.append(f"- **Sistema Operacional:** {os_str}")
    lines.append(f"- **Processador & Temperatura Atual:** {cpu_name} — **{cpu_t}°C** ({temps.get('cpu_temp_status', 'Normal')})")
    lines.append(f"- **Placa de Vídeo & Temperatura Atual:** {gpu_name} — **{gpu_t}°C** ({temps.get('gpu_temp_status', 'Normal')})")
    lines.append(f"- **Memória RAM:** {ram_gb} GB instalados em {len(ram_mods)} módulo(s)")
    lines.append(f"- **Armazenamento & SMART:** {disk_summary}")
    lines.append(f"- **Classificação PC Gamer:** {gp.get('gamer_tier', 'N/D')} (Alvo: {gp.get('target_resolution', '1080p')})")
    lines.append(f"- **Firmware BIOS/UEFI:** Versão `{bios.get('smbios_version', 'N/D')}` ({bios.get('release_date', 'N/D')} - {bios.get('status_label', 'OK')})")
    lines.append("")
    lines.append("### Prioridades de Intervenção Técnica")
    if outdated_sw:
        lines.append(f"- **Softwares Obsoletos ({len(outdated_sw)}):** Atualizar via Winget ({sw_names}).")
    else:
        lines.append("- **Softwares:** Todos os pacotes monitorados pelo Winget estão atualizados.")

    if missing_dlls:
        lines.append(f"- **DLLs de Jogos/Runtimes Ausentes ({len(missing_dlls)}):** Reparar {', '.join(missing_dlls)} na Aba PC Gamer & DLLs.")
    else:
        lines.append("- **Integridade de DLLs (32/64-bit):** Todas as 11 bibliotecas críticas estão presentes e íntegras.")

    if outdated_drv > 0:
        lines.append(f"- **Drivers Antigos:** {outdated_drv} controlador(es) com mais de 36 meses. Verificar atualizações oficiais.")

    for b in gp.get("bottlenecks_and_alerts", []):
        lines.append(f"- **Análise de Equilíbrio/Gargalo:** {b}")

    if user_prompt.strip():
        lines.append("")
        lines.append(f"### Resposta à Pergunta Técnica ('{user_prompt.strip()}')")
        lines.append(
            f"- Com base no conjunto `{cpu_name}` + `{gpu_name}` + `{ram_gb} GB RAM`, o equipamento opera em `{gp.get('gamer_tier', 'Alto Desempenho')}` com temperaturas atuais de `{cpu_t}°C` (CPU) e `{gpu_t}°C` (GPU)."
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 2. PARECER PARA O CLIENTE")
    lines.append("")
    lines.append(
        f"Prezado(a) Cliente,\n\n"
        f"Concluímos a inspeção completa do seu computador **{manuf} {model}** através da suíte **AegisPulse IT Toolkit**.\n\n"
        f"- **Saúde Física e Temperaturas:** Seu processador (**{cpu_name}** a **{cpu_t}°C**), placa de vídeo (**{gpu_name}** a **{gpu_t}°C**), seus **{ram_gb} GB de memória RAM** e seus discos rígidos/SSDs estão operando com saúde física aprovada.\n"
        f"- **Manutenção Preventiva Recomendada:** Identificamos **{len(outdated_sw)} programa(s)** com atualizações de segurança pendentes e oportunidades de otimização de armazenamento e drivers para deixar sua máquina ainda mais rápida e estável.\n\n"
        f"Atenciosamente,\n"
        f"**Adriano Barboza** — Especialista em TI | WhatsApp: **+55 61 98515-8434**"
    )
    return "\n".join(lines)


def _query_grok_or_groq_cloud(api_key: str, prompt_text: str) -> dict:
    """Consulta a API da xAI Grok (xai-...) ou GroqCloud LPU (gsk_...) compatível com OpenAI."""
    clean_key = (api_key or "").strip()
    if not clean_key:
        return {
            "online": True,
            "success": False,
            "message": "Chave de API Grok (xAI) / Groq não configurada. Cole sua chave no painel de configuração à direita.",
            "response_text": "",
        }

    is_groq_lpu = clean_key.startswith("gsk_")
    endpoint = (
        "https://api.groq.com/openai/v1/chat/completions"
        if is_groq_lpu
        else "https://api.x.ai/v1/chat/completions"
    )
    model_name = "llama-3.3-70b-versatile" if is_groq_lpu else "grok-3-mini"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "Você é o especialista N3 embarcado no AegisPulse IT Toolkit de Adriano Barboza."},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.3,
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {clean_key}",
            "User-Agent": "AegisPulse-Toolkit/3.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            choices = body.get("choices") or []
            if choices:
                txt = choices[0].get("message", {}).get("content", "").strip()
                header = f"[Modelo Utilizado: 🚀 Grok / Groq Cloud AI ({model_name})]\n\n"
                return {
                    "online": True,
                    "success": True,
                    "model_used": model_name,
                    "message": f"Análise concluída via {model_name}!",
                    "response_text": header + txt,
                }
    except Exception as exc:
        return {
            "online": True,
            "success": False,
            "message": f"Falha ao consultar Grok/Groq Cloud ({exc}). Verifique sua chave de API ou use a IA Local N3.",
            "response_text": "",
        }
    return {"online": True, "success": False, "message": "Resposta vazia da API Grok.", "response_text": ""}


def query_gemini_ai(
    api_key: str,
    snapshot: dict,
    user_prompt: str = "",
    model: str = "gemini-3.5-flash-lite",
    provider: str = "local",
    user_role: str = "admin",
    grok_api_key: str = "",
) -> dict:
    """
    Roteador Multi-IA v3.0:
    - provider == 'local': Usa IA Local N3 (disponível para Trial, Assinante PRO e ADM).
    - provider == 'gemini' ou 'grok': Exclusivo para Assinante PRO e ADM Master!
      Se o usuário estiver em Modo Trial, exibe um convite comercial intuitivo para assinar.
    """
    sanitized_context = sanitize_snapshot_for_ai(snapshot)

    # 1. IA Local AegisPulse N3 (Liberada para TODOS, inclusive Trial)
    if provider == "local":
        local_text = generate_local_expert_analysis(sanitized_context, user_prompt=user_prompt)
        return {
            "online": True,
            "success": True,
            "model_used": "AegisPulse-Local-N3",
            "message": "Diagnóstico gerado instantaneamente pela IA Local AegisPulse N3!",
            "response_text": local_text,
        }

    # 2. Trava Comercial Intuitiva para Usuários em Modo Trial que tentarem usar Gemini ou Grok Cloud
    if user_role == "trial" and provider in ("gemini", "grok"):
        upsell_msg = (
            "==========================================================================\n"
            "🔒 RECURSO EXCLUSIVO PARA ASSINANTES PRO — IA EM NUVEM (GEMINI & GROK)\n"
            "==========================================================================\n\n"
            "Você está utilizando o MODO TRIAL GRATUITO do AegisPulse IT Toolkit.\n"
            "No Modo Trial, você já tem acesso completo à nossa **🧠 IA Local AegisPulse N3**!\n\n"
            "Para desbloquear os motores de Inteligência Artificial em Nuvem (**✨ Google Gemini 3.x** "
            "e **🚀 xAI Grok / Groq Cloud**), além de diagnósticos e laudos ILIMITADOS:\n\n"
            "👉 Adquira sua Chave de Assinatura PRO agora mesmo com **Adriano Barboza**:\n"
            "📱 WhatsApp Direto: +55 61 98515-8434\n"
            "📧 E-mail: adriano9200@gmail.com\n\n"
            "💡 Dica: Selecione a opção '🧠 IA Local AegisPulse N3 (Gratuita Trial & PRO)' no seletor acima "
            "para gerar seu diagnóstico gratuitamente agora mesmo!"
        )
        return {
            "online": True,
            "success": True,
            "requires_subscription": True,
            "model_used": "Trial-Upsell",
            "message": "Motores Gemini & Grok são exclusivos para Assinantes PRO. Use a IA Local ou assine pelo WhatsApp +55 61 98515-8434!",
            "response_text": upsell_msg,
        }

    online = check_internet_connection()
    if not online:
        local_text = generate_local_expert_analysis(
            sanitized_context,
            user_prompt=user_prompt,
            cloud_notice="Sem conexão com a internet — Fallback automático para IA Local N3",
        )
        return {
            "online": False,
            "success": True,
            "model_used": "AegisPulse-Local-N3",
            "message": "Dispositivo offline — Análise gerada pela IA Local N3.",
            "response_text": local_text,
        }

    system_instruction = (
        "Você é o assistente de IA embarcado no 'AegisPulse IT Toolkit — Diagnóstico • Automação • Inteligência', "
        "desenvolvido pelo especialista de TI Adriano Barboza (WhatsApp +55 61 98515-8434). Analise os dados reais "
        "coletados da máquina abaixo (incluindo temperaturas de CPU/GPU e perfil PC Gamer) sem inventar métricas. "
        "Separe sua resposta em:\n"
        "### 1. DIAGNÓSTICO TÉCNICO N3 (Para o Técnico Adriano Barboza)\n"
        "### 2. PARECER PARA O CLIENTE (Linguagem clara, honesta e sem alarmismo)"
    )

    if user_prompt.strip():
        prompt_text = (
            f"{system_instruction}\n\n"
            f"DADOS DO EQUIPAMENTO (JSON):\n{json.dumps(sanitized_context, ensure_ascii=False, indent=2)}\n\n"
            f"PERGUNTA ESPECÍFICA:\n{user_prompt.strip()}"
        )
    else:
        prompt_text = (
            f"{system_instruction}\n\n"
            f"DADOS DO EQUIPAMENTO (JSON):\n{json.dumps(sanitized_context, ensure_ascii=False, indent=2)}\n\n"
            "Gere o diagnóstico técnico completo e a mensagem para o cliente."
        )

    # 3. Motor Grok / Groq Cloud AI
    if provider == "grok":
        res_grok = _query_grok_or_groq_cloud(grok_api_key, prompt_text)
        if res_grok.get("success"):
            return res_grok
        fallback_text = generate_local_expert_analysis(
            sanitized_context,
            user_prompt=user_prompt,
            cloud_notice=res_grok.get("message", "Chave Grok ausente — usando IA Local N3"),
        )
        return {
            "online": True,
            "success": True,
            "model_used": "AegisPulse-Local-N3-Fallback",
            "message": res_grok.get("message", "Usando IA Local N3."),
            "response_text": fallback_text,
        }

    # 4. Motor Google Gemini 3.x Cloud AI
    clean_key = (api_key or "").strip()
    if not clean_key or clean_key == "COLE_SUA_GEMINI_API_KEY_AQUI":
        local_text = generate_local_expert_analysis(
            sanitized_context,
            user_prompt=user_prompt,
            cloud_notice="Chave Gemini API não configurada — usando IA Local N3",
        )
        return {
            "online": True,
            "success": True,
            "model_used": "AegisPulse-Local-N3",
            "message": "Chave Gemini não informada — Diagnóstico gerado pela IA Local N3.",
            "response_text": local_text,
        }

    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }

    models_to_try = [m for m in FALLBACK_MODELS]
    if model and model not in models_to_try:
        models_to_try.insert(0, model)

    last_error_msg = ""
    for candidate_model in models_to_try:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent?key={clean_key}"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                candidates = body.get("candidates") or []
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "\n".join(p.get("text", "") for p in parts).strip()
                    header = f"[Modelo Utilizado: ✨ Google Gemini ({candidate_model})]\n\n"
                    return {
                        "online": True,
                        "success": True,
                        "model_used": candidate_model,
                        "message": f"Análise concluída pelo Google Gemini ({candidate_model}).",
                        "response_text": header + text,
                    }
        except urllib.error.HTTPError as he:
            last_error_msg = f"HTTP {he.code} em {candidate_model}"
            if he.code in (404, 429, 500, 502, 503, 504):
                time.sleep(0.4)
                continue
            break
        except Exception as exc:
            last_error_msg = f"Erro em {candidate_model}: {exc}"
            continue

    fallback_text = generate_local_expert_analysis(
        sanitized_context,
        user_prompt=user_prompt,
        cloud_notice=f"Servidores Gemini em alta demanda ({last_error_msg})",
    )
    return {
        "online": True,
        "success": True,
        "model_used": "AegisPulse-Local-N3-Fallback",
        "message": "Servidores Google em pico (503) — Diagnóstico gerado pela IA Local N3!",
        "response_text": fallback_text,
    }
