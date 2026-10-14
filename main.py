#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit — Diagnostic, Maintenance & AI Suite
ARQUIVO: main.py (Ponto de Entrada Principal)
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
VERSÃO:  1.0.0
LICENÇA: Proprietária — Todos os direitos reservados a Adriano Barboza
================================================================================
Descrição:
Inicializa os diretórios de trabalho, carrega as configurações locais, sobe o
servidor HTTP/REST do Backend na porta configurada (padrão 127.0.0.1:8765) e
abre a interface gráfica moderna (em janela dedicada App Mode do Edge/Chrome ou
navegador padrão).
"""

import os
import sys
import json
import time
import shutil
import subprocess
import threading
import webbrowser
from pathlib import Path

from backend.server import start_AegisPulse_server

AUTHOR_NAME = "Adriano Barboza"
AUTHOR_EMAIL = "adriano9200@gmail.com"
APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
CONFIG_EXAMPLE = BASE_DIR / "config.example.json"


def ensure_environment() -> dict:
    """Garante que pastas de logs/relatórios e config.json existam."""
    (BASE_DIR / "reports").mkdir(exist_ok=True)
    (BASE_DIR / "logs").mkdir(exist_ok=True)

    if not CONFIG_FILE.exists() and CONFIG_EXAMPLE.exists():
        shutil.copyfile(CONFIG_EXAMPLE, CONFIG_FILE)

    default_cfg = {
        "author": AUTHOR_NAME,
        "app_name": "AegisPulse IT Toolkit",
        "version": APP_VERSION,
        "server_host": "127.0.0.1",
        "server_port": 8765,
        "require_operator_pin": True,
        "operator_pin_sha256": "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",
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
    """Tenta abrir em janela estilo Aplicativo Nativo (Edge/Chrome --app) ou navegador padrão."""
    time.sleep(0.8)
    if sys.platform.startswith("win"):
        edge_paths = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        ]
        for edge in edge_paths:
            if os.path.exists(edge):
                try:
                    subprocess.Popen([edge, f"--app={url}", "--window-size=1360,860"])
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
    print(f"  AEGISPULSE IT TOOLKIT v{APP_VERSION}")
    print(f"  Desenvolvido por: {AUTHOR_NAME} ({AUTHOR_EMAIL})")
    print("=" * 76)
    print(f"  [+] Servidor Backend ativo em : {url}")
    print(f"  [+] Pasta de Relatórios HTML  : {BASE_DIR / 'reports'}")
    print(f"  [+] Pasta de Logs de Auditoria: {BASE_DIR / 'logs'}")
    print("  [!] Pressione CTRL+C nesta janela para encerrar o Toolkit.")
    print("=" * 76)

    threading.Thread(target=launch_desktop_window, args=(url,), daemon=True).start()
    start_AegisPulse_server(host=host, port=port, base_dir=BASE_DIR)


if __name__ == "__main__":
    main()
