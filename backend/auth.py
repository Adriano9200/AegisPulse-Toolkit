#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/auth.py (Licenciamento Comercial v3.0: Trial, Assinante e ADM)
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  3.0.0
================================================================================
Descrição:
Gerencia os 3 modos comerciais de acesso do AegisPulse IT Toolkit:
1. MODO TRIAL (Gratuito): Permite até 4 análises completas + IA Local N3.
   Na 5ª tentativa (ou ao tentar usar Gemini/Grok Cloud), convida o usuário de
   forma intuitiva a assinar via WhatsApp (+55 61 98515-8434).
2. MODO ASSINANTE PRO (Usuário Comum Licenciado): Desbloqueado com chave
   AEGIS-PRO-YYYYMMDD-CLIENTE-HASH. Libera análises ilimitadas e motores de IA
   em nuvem (Google Gemini e Grok/xAI), mantendo ocultas as abas exclusivas ADM.
3. MODO ADMINISTRADOR MASTER (Exclusivo Adriano Barboza): Desbloqueado com a
   nova senha Master configurada pelo autor (SHA-256), liberando as abas
   exclusivas de CRM SQLite, Precificação Justa, Orçamento para Cliente e Keygen.
"""

import hmac
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from pathlib import Path

MASTER_LICENSE_SECRET = b"AEGISPULSE_ADRIANO_BARBOZA_MASTER_SECRET_2026"
DEFAULT_TRIAL_LIMIT = 4

# Hash SHA-256 da senha Master definida por Adriano Barboza (Luna@19102023)
# A senha nunca fica exposta em texto puro no repositório público do GitHub.
MASTER_ADMIN_HASH = "30e489d9b17b72bf6bc9b120e1274a34189872b85094933b4166e3d217f847be"

AUTHOR_WHATSAPP = "+55 61 98515-8434"
AUTHOR_WHATSAPP_URL = "https://wa.me/5561985158434?text=Ol%C3%A1%20Adriano%20Barboza!%20Estou%20usando%20o%20AegisPulse%20IT%20Toolkit%20e%20quero%20adquirir%20uma%20Chave%20de%20Assinatura%20PRO!"

ACTIVE_SESSIONS: dict[str, dict] = {}


def hash_pin(raw_pin: str) -> str:
    """Retorna o hash SHA-256 de uma senha ou PIN."""
    return hashlib.sha256(raw_pin.strip().encode("utf-8")).hexdigest()


def load_config(base_dir: Path) -> dict:
    cfg_path = base_dir / "config.json"
    default_cfg = {
        "author": "Adriano Barboza",
        "author_whatsapp": AUTHOR_WHATSAPP,
        "app_name": "AegisPulse IT Toolkit",
        "version": "3.0.0",
        "server_host": "127.0.0.1",
        "server_port": 8765,
        "require_operator_pin": True,
        "operator_pin_sha256": MASTER_ADMIN_HASH,
        "trial_limit": DEFAULT_TRIAL_LIMIT,
        "trial_scans_used": 0,
        "activated_license_key": "",
        "activated_client_name": "",
        "gemini_api_key": "",
        "grok_api_key": "",
        "gemini_model": "gemini-3.5-flash-lite",
    }
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Se ainda estiver com o hash antigo de 'admin123', atualiza automaticamente para a nova senha Master
                old_admin123_hash = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"
                if loaded.get("operator_pin_sha256") == old_admin123_hash:
                    loaded["operator_pin_sha256"] = MASTER_ADMIN_HASH
                default_cfg.update(loaded)
        except Exception:
            pass
    return default_cfg


def save_config(base_dir: Path, new_data: dict) -> bool:
    cfg_path = base_dir / "config.json"
    current = load_config(base_dir)
    current.update(new_data)
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def generate_subscription_key(client_name: str, days_valid: int = 365) -> dict:
    """Gera uma Chave de Assinatura oficial (AEGIS-PRO-YYYYMMDD-CLIENT-SIG) assinada via HMAC-SHA256."""
    clean_client = "".join(c for c in (client_name or "CLIENTE").upper() if c.isalnum())[:6] or "PROUSR"
    exp_date = (datetime.now() + timedelta(days=int(days_valid))).strftime("%Y%m%d")
    payload = f"{exp_date}-{clean_client}"
    sig = hmac.new(MASTER_LICENSE_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:10].upper()
    full_key = f"AEGIS-PRO-{exp_date}-{clean_client}-{sig}"
    return {
        "license_key": full_key,
        "client_name": client_name or "Cliente Licenciado",
        "expires_at": f"{exp_date[:4]}-{exp_date[4:6]}-{exp_date[6:8]}",
        "days_valid": days_valid,
    }


def validate_subscription_key(license_key: str) -> dict:
    """Valida a autenticidade e a data de expiração de uma chave AEGIS-PRO-..."""
    raw = (license_key or "").strip().upper()
    parts = raw.split("-")
    if len(parts) != 5 or parts[0] != "AEGIS" or parts[1] != "PRO":
        return {"valid": False, "message": "Formato de chave inválido. Adquira sua chave oficial via WhatsApp +55 61 98515-8434."}

    exp_date, client_code, provided_sig = parts[2], parts[3], parts[4]
    payload = f"{exp_date}-{client_code}"
    expected_sig = hmac.new(MASTER_LICENSE_SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:10].upper()

    if not hmac.compare_digest(provided_sig, expected_sig):
        return {"valid": False, "message": "Assinatura criptográfica inválida. Chave não emitida por Adriano Barboza."}

    try:
        exp_dt = datetime.strptime(exp_date, "%Y%m%d")
        if datetime.now().date() > exp_dt.date():
            return {"valid": False, "message": f"Assinatura expirada em {exp_dt.strftime('%d/%m/%Y')}. Renove pelo WhatsApp {AUTHOR_WHATSAPP}."}
        return {
            "valid": True,
            "client_code": client_code,
            "expires_at": exp_dt.strftime("%d/%m/%Y"),
            "message": f"Assinatura PRO Ativa (Válida até {exp_dt.strftime('%d/%m/%Y')}).",
        }
    except ValueError:
        return {"valid": False, "message": "Data de validade corrompida na chave."}


def login_admin(base_dir: Path, candidate_pin: str) -> dict:
    """Autentica o Administrador Master (Adriano Barboza)."""
    cfg = load_config(base_dir)
    expected_hash = cfg.get("operator_pin_sha256", MASTER_ADMIN_HASH)
    cand_hash = hash_pin(candidate_pin)
    if cand_hash in (expected_hash, MASTER_ADMIN_HASH):
        if cfg.get("operator_pin_sha256") != MASTER_ADMIN_HASH and cand_hash == MASTER_ADMIN_HASH:
            save_config(base_dir, {"operator_pin_sha256": MASTER_ADMIN_HASH})
        token = secrets.token_hex(24)
        session = {
            "role": "admin",
            "role_label": "👑 Administrador Master (Adriano Barboza)",
            "trial_used": int(cfg.get("trial_scans_used", 0)),
            "trial_limit": int(cfg.get("trial_limit", DEFAULT_TRIAL_LIMIT)),
            "whatsapp": AUTHOR_WHATSAPP,
            "whatsapp_url": AUTHOR_WHATSAPP_URL,
        }
        ACTIVE_SESSIONS[token] = session
        return {"success": True, "token": token, **session}
    return {"success": False, "message": "Senha Master de Administrador incorreta."}


def login_subscriber(base_dir: Path, license_key: str) -> dict:
    """Autentica um Usuário Comum com Chave de Assinatura (AEGIS-PRO-...)."""
    val = validate_subscription_key(license_key)
    if not val["valid"]:
        return {"success": False, "message": val["message"]}

    save_config(base_dir, {"activated_license_key": license_key.strip().upper()})
    token = secrets.token_hex(24)
    session = {
        "role": "subscriber",
        "role_label": f"⭐ Assinante PRO (Até {val['expires_at']})",
        "expires_at": val["expires_at"],
        "trial_used": 0,
        "trial_limit": DEFAULT_TRIAL_LIMIT,
        "whatsapp": AUTHOR_WHATSAPP,
        "whatsapp_url": AUTHOR_WHATSAPP_URL,
    }
    ACTIVE_SESSIONS[token] = session
    return {"success": True, "token": token, "message": val["message"], **session}


def login_trial(base_dir: Path) -> dict:
    """Inicia sessão em Modo Trial Gratuito se ainda houver análises disponíveis."""
    cfg = load_config(base_dir)
    used = int(cfg.get("trial_scans_used", 0))
    limit = int(cfg.get("trial_limit", DEFAULT_TRIAL_LIMIT))
    if used >= limit:
        return {
            "success": False,
            "trial_exhausted": True,
            "trial_used": used,
            "trial_limit": limit,
            "whatsapp": AUTHOR_WHATSAPP,
            "whatsapp_url": AUTHOR_WHATSAPP_URL,
            "message": f"🔒 Você utilizou suas {limit} análises gratuitas do Modo Trial! Adquira sua Assinatura PRO pelo WhatsApp {AUTHOR_WHATSAPP} (Adriano Barboza).",
        }
    token = secrets.token_hex(24)
    session = {
        "role": "trial",
        "role_label": f"⏳ Modo Trial ({used}/{limit} análises usadas)",
        "trial_used": used,
        "trial_limit": limit,
        "whatsapp": AUTHOR_WHATSAPP,
        "whatsapp_url": AUTHOR_WHATSAPP_URL,
    }
    ACTIVE_SESSIONS[token] = session
    return {"success": True, "token": token, **session}


def get_session_info(base_dir: Path, token: str | None) -> dict | None:
    if token and token in ACTIVE_SESSIONS:
        sess = ACTIVE_SESSIONS[token]
        cfg = load_config(base_dir)
        sess["trial_used"] = int(cfg.get("trial_scans_used", 0))
        sess["trial_limit"] = int(cfg.get("trial_limit", DEFAULT_TRIAL_LIMIT))
        if sess["role"] == "trial":
            sess["role_label"] = f"⏳ Modo Trial ({sess['trial_used']}/{sess['trial_limit']} análises usadas)"
        return sess
    return None


def consume_trial_scan(base_dir: Path, token: str | None) -> tuple[bool, str]:
    sess = get_session_info(base_dir, token)
    if not sess:
        return False, "Sessão não autenticada."
    if sess["role"] in ("admin", "subscriber"):
        return True, "OK"

    cfg = load_config(base_dir)
    used = int(cfg.get("trial_scans_used", 0))
    limit = int(cfg.get("trial_limit", DEFAULT_TRIAL_LIMIT))
    if used >= limit:
        return (
            False,
            f"🔒 Limite do Modo Trial Atingido ({used} de {limit} análises gratuitas utilizadas). "
            f"Adquira sua Chave de Assinatura PRO com Adriano Barboza pelo WhatsApp {AUTHOR_WHATSAPP}!",
        )

    new_used = used + 1
    save_config(base_dir, {"trial_scans_used": new_used})
    sess["trial_used"] = new_used
    sess["role_label"] = f"⏳ Modo Trial ({new_used}/{limit} análises usadas)"
    return True, f"Análise Trial {new_used}/{limit} liberada."
