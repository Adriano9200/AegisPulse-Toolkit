#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/gemini_ai.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
================================================================================
Descrição:
Integração nativa com a API do Google Gemini quando o computador está conectado
à internet.
- Verifica conectividade online antes de chamar a API;
- Sanitiza identificadores sensíveis antes do envio (Privacidade por Padrão);
- Gera parecer técnico N3 (para o técnico Adriano Barboza) e resumo em linguagem
  acessível para o cliente final;
- Suporta chat interativo contextualizado com os dados da máquina atual.
"""

import json
import socket
import urllib.request
import urllib.error


def check_internet_connection(timeout: float = 3.0) -> bool:
    """Verifica se o computador possui conexão ativa com a internet."""
    targets = [("8.8.8.8", 53), ("1.1.1.1", 53)]
    for host, port in targets:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def sanitize_snapshot_for_ai(snapshot: dict) -> dict:
    """Remove seriais privados e UUIDs antes de enviar o contexto para a API."""
    hw = snapshot.get("hardware", {})
    os_info = snapshot.get("os", {})
    drv = snapshot.get("drivers_bios", {})
    sw = snapshot.get("software", {})

    return {
        "manufacturer": hw.get("manufacturer"),
        "model": hw.get("model"),
        "total_ram_gb": hw.get("total_ram_gb"),
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
        },
        "pnp_errors": drv.get("pnp_errors", []),
        "outdated_drivers_count": drv.get("outdated_drivers_count", 0),
        "outdated_software": sw.get("outdated_software", []),
    }


def query_gemini_ai(
    api_key: str,
    snapshot: dict,
    user_prompt: str = "",
    model: str = "gemini-2.5-flash",
) -> dict:
    """Consulta a API REST do Google Gemini com o diagnóstico da máquina."""
    online = check_internet_connection()
    if not online:
        return {
            "online": False,
            "success": False,
            "message": "Dispositivo sem conexão com a internet. O módulo Gemini AI requer conectividade ativa.",
            "response_text": "",
        }

    clean_key = (api_key or "").strip()
    if not clean_key or clean_key == "COLE_SUA_GEMINI_API_KEY_AQUI":
        return {
            "online": True,
            "success": False,
            "message": "Chave de API do Gemini não configurada. Insira sua Gemini API Key na aba 'IA Gemini & Config'.",
            "response_text": "",
        }

    sanitized_context = sanitize_snapshot_for_ai(snapshot)

    system_instruction = (
        "Você é o assistente de IA embarcado no 'AegisPulse IT Toolkit', criado pelo "
        "especialista de TI Adriano Barboza. Analise os dados reais coletados da máquina "
        "abaixo sem inventar métricas. Separe sua resposta em:\n"
        "1. DIAGNÓSTICO TÉCNICO (para o técnico Adriano Barboza): avaliação de hardware, "
        "saúde dos discos, idade da BIOS, erros de drivers, softwares obsoletos e prioridades.\n"
        "2. PARECER PARA O CLIENTE (linguagem clara, honesta e sem alarmismo): resumo "
        "pronto para enviar ao cliente explicando o estado do computador e as melhorias recomendadas."
    )

    if user_prompt.strip():
        prompt_text = (
            f"{system_instruction}\n\n"
            f"DADOS DO EQUIPAMENTO (JSON):\n{json.dumps(sanitized_context, ensure_ascii=False, indent=2)}\n\n"
            f"PERGUNTA ESPECÍFICA DO TÉCNICO ADRIANO BARBOZA:\n{user_prompt.strip()}"
        )
    else:
        prompt_text = (
            f"{system_instruction}\n\n"
            f"DADOS DO EQUIPAMENTO (JSON):\n{json.dumps(sanitized_context, ensure_ascii=False, indent=2)}\n\n"
            "Gere o diagnóstico técnico completo e a mensagem para o cliente."
        )

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt_text}]
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2048,
        },
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            candidates = body.get("candidates") or []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "\n".join(p.get("text", "") for p in parts).strip()
                return {
                    "online": True,
                    "success": True,
                    "message": "Análise concluída pelo Google Gemini.",
                    "response_text": text,
                }
            return {
                "online": True,
                "success": False,
                "message": "A API do Gemini retornou uma resposta vazia.",
                "response_text": "",
            }
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="replace")
        return {
            "online": True,
            "success": False,
            "message": f"Erro HTTP {he.code} ao consultar a API do Gemini. Verifique sua API Key.",
            "response_text": err_body[:500],
        }
    except Exception as exc:
        return {
            "online": True,
            "success": False,
            "message": f"Falha na comunicação com o Gemini: {exc}",
            "response_text": "",
        }
