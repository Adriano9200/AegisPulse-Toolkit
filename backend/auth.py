#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/auth.py (Autenticação e Controle de Acesso do Operador)
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
================================================================================
Descrição:
Impede que terceiros que visualizem ou baixem o repositório do GitHub utilizem
as funções de manutenção, atualização ou diagnóstico sem a Senha/PIN do Técnico
(Adriano Barboza). Usa hash SHA-256 e tokens de sessão em memória.
"""

import hashlib
import secrets
import json
from pathlib import Path

ACTIVE_TOKENS = set()


def hash_pin(raw_pin: str) -> str:
    """Retorna o hash SHA-256 de um PIN ou senha."""
    return hashlib.sha256(raw_pin.strip().encode("utf-8")).hexdigest()


def load_config(base_dir: Path) -> dict:
    cfg_path = base_dir / "config.json"
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "require_operator_pin": True,
        "operator_pin_sha256": hash_pin("admin123"),
    }


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


def verify_operator_pin(base_dir: Path, candidate_pin: str) -> str | None:
    """Valida o PIN do técnico. Se válido, gera e retorna um token de sessão."""
    cfg = load_config(base_dir)
    expected_hash = cfg.get(
        "operator_pin_sha256",
        hash_pin("admin123"),
    )
    if hash_pin(candidate_pin) == expected_hash:
        token = secrets.token_hex(24)
        ACTIVE_TOKENS.add(token)
        return token
    return None


def is_authorized(base_dir: Path, token: str | None) -> bool:
    """Verifica se a sessão está autorizada ou se o bloqueio por PIN está desativado."""
    cfg = load_config(base_dir)
    if not cfg.get("require_operator_pin", True):
        return True
    if not token:
        return False
    return token in ACTIVE_TOKENS
