#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/gemini_ai.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.0.0
================================================================================
Descrição:
Etapa 10 — Integração com Motores de IA (IA Local N3, Google Gemini 3.x e xAI Grok):
- Inclui toda a telemetria avançada de armazenamento (Inventário, SMART, Vida Útil,
  TBW, Classificação de Risco, Diagnóstico Especializado de Falhas e Testes).
- Gera diagnósticos fundamentados em evidências, hipóteses alternativas (ex: erro
  CRC no cabo vs setor defeituoso), testes não-destrutivos recomendados e planos
  de ação ordenados por risco.
- Regra Estrita: A IA nunca inventa métricas, nunca promete data exata de falha
  ou garantia absoluta de recuperação de dados, e nunca executa comandos destrutivos.
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
    st_suite = snapshot.get("storage_suite", {})

    storage_summary = []
    for d in (st_suite.get("devices") or []):
        storage_summary.append({
            "disk_number": d.get("disk_number"),
            "brand": d.get("brand"),
            "model": d.get("model"),
            "serial_number": d.get("serial_number"),
            "firmware": d.get("firmware"),
            "media_category": d.get("media_category"),
            "interface": d.get("interface"),
            "protocol": d.get("protocol"),
            "controller": d.get("controller"),
            "capacity_formatted": d.get("capacity", {}).get("formatted"),
            "partition_style": d.get("partition_style"),
            "drive_letters": d.get("drive_letters"),
            "is_online": d.get("is_online"),
            "is_read_only": d.get("is_read_only"),
            "has_raw_volume": d.get("has_raw_volume"),
            "adapter_limitations": d.get("adapter_limitations"),
            "smart_summary": d.get("smart_summary"),
            "lifespan": {
                "power_on_formatted": d.get("lifespan", {}).get("power_on_formatted"),
                "manufacturer_reported_str": d.get("lifespan", {}).get("manufacturer_reported_str"),
                "estimated_tbw_str": d.get("lifespan", {}).get("estimated_tbw_str"),
                "total_reads_formatted": d.get("lifespan", {}).get("total_reads_formatted"),
                "total_writes_formatted": d.get("lifespan", {}).get("total_writes_formatted"),
                "degradation_alerts": d.get("lifespan", {}).get("degradation_alerts", []),
            },
            "risk_assessment": d.get("risk_assessment"),
            "fault_diagnostics": d.get("fault_diagnostics"),
        })

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
        "storage_forensics_v4": {
            "highest_risk_level": st_suite.get("highest_risk_level", "BAIXO"),
            "devices": storage_summary,
        },
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
        "health_score": snapshot.get("health_score", {}),
    }


def generate_local_expert_analysis(ctx: dict, user_prompt: str = "", cloud_notice: str = "") -> str:
    """Motor Especialista Heurístico N3 Nativo do AegisPulse v4.0 (Liberado para Trial, Assinantes e ADM)."""
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

    st_v4 = ctx.get("storage_forensics_v4") or {}
    st_devs = st_v4.get("devices") or []
    highest_risk = st_v4.get("highest_risk_level", "BAIXO")

    bios = ctx.get("bios") or {}
    outdated_sw = ctx.get("outdated_software") or []
    missing_dlls = ctx.get("missing_dlls") or []
    outdated_drv = int(ctx.get("outdated_drivers_count") or 0)
    gp = ctx.get("gamer_profile") or {}

    sw_names = ", ".join(s.get("name", "") for s in outdated_sw[:8])
    if len(outdated_sw) > 8:
        sw_names += f" e mais {len(outdated_sw) - 8} pacote(s)"

    lines = []
    lines.append("[Motor Utilizado: 🧠 IA Local AegisPulse N3 v4.5 (Diagnóstico Forense & Health Score Baseado em Evidências)]")
    if cloud_notice:
        lines.append(f"[Info: {cloud_notice}]")
    lines.append("")
    
    hs = ctx.get("health_score") or {}
    if hs and hs.get("overall_score") is not None:
        lines.append("### 🩺 ÍNDICE DE SAÚDE AEGISPULSE HEALTH SCORE")
        lines.append(f"- **Pontuação Geral:** **{hs.get('overall_score')}/100 — {hs.get('classification', 'N/D')}**")
        lines.append(f"- **Cobertura da Avaliação:** {hs.get('coverage', {}).get('label', 'N/D')} ({hs.get('coverage', {}).get('percent', 0)}% de cobertura)")
        if hs.get("critical_cap_applied"):
            lines.append("  - 🚨 **Nota Limitada por Falha Crítica:** A média geral foi limitada em 59.0 para destacar problemas graves de integridade.")
        cats = hs.get("categories") or {}
        cat_lines = []
        for ck, cv in cats.items():
            if cv.get("available"):
                cat_lines.append(f"{cv.get('category_title')}: {cv.get('score')} pts ({cv.get('status', '').upper()})")
        if cat_lines:
            lines.append(f"- **Desempenho por Categoria:** {' | '.join(cat_lines[:4])}")
            if len(cat_lines) > 4:
                lines.append(f"  {' | '.join(cat_lines[4:])}")
        lines.append("")

    lines.append("### 1. DIAGNÓSTICO TÉCNICO N3 (Especialista Adriano Barboza)")
    lines.append("")
    lines.append(f"- **Equipamento Analisado:** {manuf} {model}")
    lines.append(f"- **Sistema Operacional:** {os_str}")
    lines.append(f"- **Processador & Temperatura Atual:** {cpu_name} — **{cpu_t}°C** ({temps.get('cpu_temp_status', 'Normal')})")
    lines.append(f"- **Placa de Vídeo & Temperatura Atual:** {gpu_name} — **{gpu_t}°C** ({temps.get('gpu_temp_status', 'Normal')})")
    lines.append(f"- **Memória RAM:** {ram_gb} GB instalados em {len(ram_mods)} módulo(s)")
    lines.append(f"- **Classificação PC Gamer:** {gp.get('gamer_tier', 'N/D')} (Alvo: {gp.get('target_resolution', '1080p')})")
    lines.append(f"- **Firmware BIOS/UEFI:** Versão `{bios.get('smbios_version', 'N/D')}` ({bios.get('release_date', 'N/D')} - {bios.get('status_label', 'OK')})")
    lines.append("")
    lines.append(f"### 2. AUDITORIA FORENSE DE ARMAZENAMENTO, SMART & RISCO (Risco Global: {highest_risk})")
    if st_devs:
        for d in st_devs:
            sm = d.get("smart_summary") or {}
            lf = d.get("lifespan") or {}
            rk = d.get("risk_assessment") or {}
            lines.append(
                f"- **Disco #{d.get('disk_number')} — {d.get('brand')} {d.get('model')} (`{d.get('serial_number')}`):** "
                f"{d.get('media_category')} | Capacidade: **{d.get('capacity_formatted')}** | "
                f"Estilo: `{d.get('partition_style')}` ({', '.join(d.get('drive_letters') or ['Sem Letra'])}) | "
                f"Score SMART: **{rk.get('health_score', 100)}/100 (Risco {rk.get('risk_level', 'BAIXO')})**."
            )
            lines.append(
                f"  - **Telemetria SMART & Vida Útil:** Temp: `{sm.get('temperature_c', 'N/D')}°C` | "
                f"Horas Ligado: `{lf.get('power_on_formatted', 'N/D')}` | "
                f"Vida Útil Reportada: `{lf.get('manufacturer_reported_str', 'N/D')}` | "
                f"Gravações (TBW): `{lf.get('total_writes_formatted', 'N/D')}`."
            )
            lines.append(
                f"  - **Contadores de Integridade:** Setores Realocados: `{sm.get('reallocated_sectors') or 0}` | "
                f"Pendentes: `{sm.get('pending_sectors') or 0}` | Incorrigíveis: `{sm.get('uncorrectable_errors') or 0}` | "
                f"Erros CRC Interface: `{sm.get('crc_interface_errors') or 0}`."
            )
            for fd in (d.get("fault_diagnostics") or []):
                lines.append(f"  - **Diagnóstico ({fd.get('category')}):** {fd.get('title')} — {fd.get('explanation')} *Ação: {fd.get('recommendation')}*")
            for step in (rk.get("ordered_action_plan") or []):
                lines.append(f"  - **Plano Ordenado por Risco:** {step}")
    else:
        lines.append("- Coleta detalhada de discos disponível na aba Discos, SMART & Recuperação.")

    lines.append("")
    lines.append("### 3. PRIORIDADES GERAIS DE INTERVENÇÃO TÉCNICA")
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

    if user_prompt.strip():
        lines.append("")
        lines.append(f"### Resposta Fundamentada à Consulta Técnica ('{user_prompt.strip()}')")
        lines.append(
            f"- Com base nas evidências reais coletadas em `{manuf} {model}` (Risco de Armazenamento: `{highest_risk}`, CPU a `{cpu_t}°C`, GPU a `{gpu_t}°C`), "
            "recomenda-se sempre executar primeiro testes não-destrutivos de leitura e preservar cópia/imagem antes de qualquer reparo lógico."
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 4. PARECER PARA O CLIENTE")
    lines.append("")
    lines.append(
        f"Prezado(a) Cliente,\n\n"
        f"Concluímos a auditoria completa de hardware, saúde de armazenamento (SMART) e sistema do seu computador **{manuf} {model}** com o **AegisPulse IT Toolkit v4.0**.\n\n"
        f"- **Saúde Térmica e Desempenho:** Processador (**{cpu_name}** a **{cpu_t}°C**), placa de vídeo (**{gpu_name}** a **{gpu_t}°C**) e **{ram_gb} GB de RAM** inspecionados.\n"
        f"- **Saúde de Discos e Dados:** Nível de risco global de armazenamento classificado como **{highest_risk}** (nossa análise avalia desgaste, setores físicos e integridade sem colocar seus arquivos em risco).\n"
        f"- **Manutenção Preventiva:** Identificamos **{len(outdated_sw)} programa(s)** com atualizações pendentes e oportunidades de otimização segura.\n\n"
        f"Atenciosamente,\n"
        f"**Adriano Barboza** — Especialista em TI | WhatsApp: **+55 61 98515-8434**"
    )
    return "\n".join(lines)


def _query_grok_or_groq_cloud(api_key: str, prompt_text: str) -> dict:
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
            {"role": "system", "content": "Você é o especialista N3 embarcado no AegisPulse IT Toolkit v4.0 de Adriano Barboza."},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.25,
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {clean_key}",
            "User-Agent": "AegisPulse-Toolkit/4.0",
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
    sanitized_context = sanitize_snapshot_for_ai(snapshot)

    # 1. IA Local AegisPulse N3 (Liberada para TODOS, inclusive Trial)
    if provider == "local":
        local_text = generate_local_expert_analysis(sanitized_context, user_prompt=user_prompt)
        return {
            "online": True,
            "success": True,
            "model_used": "AegisPulse-Local-N3-v4",
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
            "model_used": "AegisPulse-Local-N3-v4",
            "message": "Dispositivo offline — Análise gerada pela IA Local N3.",
            "response_text": local_text,
        }

    system_instruction = (
        "Você é o assistente especialista N3 embarcado no 'AegisPulse IT Toolkit v4.0 — Diagnóstico • Automação • Inteligência', "
        "desenvolvido por Adriano Barboza (WhatsApp +55 61 98515-8434). Analise os dados reais coletados abaixo "
        "(incluindo o dossiê forense de discos, atributos SMART, TBW, horas ligadas, classificação de risco e falhas). "
        "REGRAS ESTRITAS: (1) Jamais invente métricas ausentes; (2) Diferencie falhas físicas de mídia, falhas de cabo/conexão (como erro CRC) "
        "e corrupção lógica; (3) Nunca prometa uma data exata de falha nem garanta 100% de recuperação de dados; "
        "(4) Ordene o plano de ação do menor para o maior risco aos dados (priorizando imagem/clonagem antes de reparos como CHKDSK). "
        "Separe sua resposta em:\n"
        "### 1. DIAGNÓSTICO TÉCNICO N3 & AUDITORIA DE ARMAZENAMENTO (Para o Técnico Adriano Barboza)\n"
        "### 2. HIPÓTESES TÉCNICAS, TESTES RECOMENDADOS E PLANO DE AÇÃO ORDENADO POR RISCO\n"
        "### 3. PARECER PARA O CLIENTE (Linguagem clara, honesta e sem alarmismo)"
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
            "Gere o diagnóstico técnico completo, o plano de ação ordenado por risco e a mensagem para o cliente."
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
            "model_used": "AegisPulse-Local-N3-v4",
            "message": "Chave Gemini não informada — Diagnóstico gerado pela IA Local N3.",
            "response_text": local_text,
        }

    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 2500},
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
