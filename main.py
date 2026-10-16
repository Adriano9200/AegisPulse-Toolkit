#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit — Diagnostic, Maintenance & AI Suite
ARQUIVO: main.py (Ponto de Entrada Principal + Suporte Portátil .EXE / Pendrive)
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  5.0.0
LICENÇA: Proprietária — Todos os direitos reservados a Adriano Barboza
================================================================================
"""

import os
import sys
import json
import time
import shutil
import socket
import subprocess
import threading
import webbrowser
from pathlib import Path

# Quando compilado com PyInstaller, garante que stdout/stderr nunca sejam None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Define o diretório persistente (ao lado do .exe no Pendrive) e o diretório interno do bundle (_MEIPASS)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR

# Garante que os pacotes backend.* sejam encontrados tanto em modo script quanto em modo .EXE
if str(BUNDLE_DIR) not in sys.path:
    sys.path.insert(0, str(BUNDLE_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.server import start_AegisPulse_server

AUTHOR_NAME = "Adriano Barboza"
AUTHOR_EMAIL = "adriano9200@gmail.com"
APP_VERSION = "5.0.0"

CONFIG_FILE = BASE_DIR / "config.json"
CONFIG_EXAMPLE = BUNDLE_DIR / "config.example.json"


def ensure_environment() -> dict:
    """Garante que pastas de dados, relatórios, logs e config.json existam no Pendrive/pasta local."""
    (BASE_DIR / "data").mkdir(exist_ok=True)
    (BASE_DIR / "reports").mkdir(exist_ok=True)
    (BASE_DIR / "logs").mkdir(exist_ok=True)

    # Se estiver rodando como .exe único sem a pasta frontend externa, extrai ou usa BUNDLE_DIR
    if not CONFIG_FILE.exists():
        if (BASE_DIR / "config.example.json").exists():
            shutil.copyfile(BASE_DIR / "config.example.json", CONFIG_FILE)
        elif CONFIG_EXAMPLE.exists():
            shutil.copyfile(CONFIG_EXAMPLE, CONFIG_FILE)

    default_cfg = {
        "author": AUTHOR_NAME,
        "app_name": "AegisPulse IT Toolkit",
        "version": APP_VERSION,
        "server_host": "127.0.0.1",
        "server_port": 8765,
        "require_operator_pin": True,
        "operator_pin_sha256": "09c7224628d009a062f7841e3c02fa0ff783fffe9c2c6931e62d3ca0654e9a1c",
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash",
    }

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_cfg.update(loaded)
        except Exception as exc:
            print(f"[AVISO] Falha ao ler config.json ({exc}). Usando padrões.")

    return default_cfg


def launch_desktop_window(url: str) -> None:
    """Abre SOMENTE a janela dedicada estilo Aplicativo Nativo (Edge/Chrome --app) ou navegador padrão se não houver Edge/Chrome."""
    time.sleep(0.9)
    if sys.platform.startswith("win"):
        browser_candidates = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        ]
        for browser_bin in browser_candidates:
            if os.path.exists(browser_bin):
                try:
                    subprocess.Popen([browser_bin, f"--app={url}", "--window-size=1380,880"])
                    return
                except Exception:
                    pass
    webbrowser.open(url)


def main() -> None:
    cfg = ensure_environment()
    host = cfg.get("server_host", "127.0.0.1")
    port = int(cfg.get("server_port", 8765))
    url = f"http://{host}:{port}"

    print("=" * 76)
    print(f"  AEGISPULSE IT TOOLKIT v{APP_VERSION} (Portátil / Pendrive Ready)")
    print(f"  Desenvolvido por: {AUTHOR_NAME} ({AUTHOR_EMAIL})")
    print("=" * 76)
    print(f"  [+] Servidor Backend ativo em : {url}")
    print(f"  [+] Diretório de Dados/SQLite : {BASE_DIR / 'data'}")
    print(f"  [+] Pasta de Relatórios HTML  : {BASE_DIR / 'reports'}")
    print(f"  [+] Pasta de Logs de Auditoria: {BASE_DIR / 'logs'}")
    print("  [!] Pressione CTRL+C nesta janela para encerrar o Toolkit.")
    print("=" * 76)

    threading.Thread(target=launch_desktop_window, args=(url,), daemon=True).start()
    start_AegisPulse_server(host=host, port=port, base_dir=BASE_DIR)


if __name__ == "__main__":
    main()
