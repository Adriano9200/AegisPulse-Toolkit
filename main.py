#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit — Diagnostic, Maintenance & AI Suite
ARQUIVO: main.py (Ponto de Entrada Principal, Verificação de Porta e Dependências)
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  5.1.0
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

if str(BUNDLE_DIR) not in sys.path:
    sys.path.insert(0, str(BUNDLE_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

AUTHOR_NAME = "Adriano Barboza"
AUTHOR_EMAIL = "adriano9200@gmail.com"
APP_VERSION = "5.5.0"

CONFIG_FILE = BASE_DIR / "config.json"
CONFIG_EXAMPLE = BUNDLE_DIR / "config.example.json"


def verify_runtime_dependencies(auto_install: bool = False) -> dict:
    """Verifica se as dependências necessárias estão presentes no ambiente Python."""
    missing = []
    optional_missing = []
    try:
        import psutil  # noqa: F401
    except ImportError:
        missing.append("psutil")

    if missing and auto_install and not getattr(sys, "frozen", False):
        for pkg in list(missing):
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
                    capture_output=True,
                    timeout=45,
                    check=True,
                )
                missing.remove(pkg)
            except Exception:
                pass

    return {
        "ok": len(missing) == 0,
        "missing_required": missing,
        "missing_optional": optional_missing,
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
    }


def is_port_in_use(host: str, port: int) -> bool:
    """Retorna True se já houver um processo escutando na porta especificada."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex((host, int(port))) == 0


def select_available_port(host: str, preferred_port: int = 8765, max_attempts: int = 10) -> tuple[int, bool]:
    """
    Verifica se a porta preferencial está livre.
    Retorna (porta_selecionada, usou_fallback).
    """
    if not is_port_in_use(host, preferred_port):
        return preferred_port, False
    for offset in range(1, max_attempts + 1):
        candidate = preferred_port + offset
        if not is_port_in_use(host, candidate):
            return candidate, True
    return preferred_port, False


def ensure_environment(base_dir: Path | None = None) -> dict:
    """Garante que pastas de dados, relatórios, logs e config.json existam."""
    target_base = base_dir or BASE_DIR
    (target_base / "data").mkdir(parents=True, exist_ok=True)
    (target_base / "reports").mkdir(parents=True, exist_ok=True)
    (target_base / "logs").mkdir(parents=True, exist_ok=True)

    cfg_file = target_base / "config.json"
    if not cfg_file.exists():
        if (target_base / "config.example.json").exists():
            shutil.copyfile(target_base / "config.example.json", cfg_file)
        elif CONFIG_EXAMPLE.exists():
            shutil.copyfile(CONFIG_EXAMPLE, cfg_file)

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

    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_cfg.update(loaded)
        except Exception as exc:
            print(f"[AVISO] Falha ao ler config.json ({exc}). Usando padrões.")

    return default_cfg


def launch_desktop_window(url: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Aguarda o servidor aceitar conexões e abre SOMENTE a janela dedicada estilo Aplicativo (--app)."""
    for _ in range(25):
        if is_port_in_use(host, port):
            break
        time.sleep(0.15)

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


def main() -> int:
    deps = verify_runtime_dependencies(auto_install=False)
    if not deps["ok"]:
        print(f"[ERRO] Dependências obrigatórias ausentes: {', '.join(deps['missing_required'])}")
        print(f"       Execute: '{sys.executable}' -m pip install {' '.join(deps['missing_required'])}")
        return 1

    from backend.server import start_AegisPulse_server

    cfg = ensure_environment()
    host = cfg.get("server_host", "127.0.0.1")
    preferred_port = int(cfg.get("server_port", 8765))
    port, used_fallback = select_available_port(host, preferred_port)
    url = f"http://{host}:{port}"

    print("=" * 76)
    print(f"  AEGISPULSE IT TOOLKIT v{APP_VERSION} (Diagnóstico Seguro & Proteção de Boot)")
    print(f"  Desenvolvido por: {AUTHOR_NAME} ({AUTHOR_EMAIL})")
    print("=" * 76)
    if used_fallback:
        print(f"  [AVISO] A porta {preferred_port} estava ocupada. Usando porta livre: {port}")
    print(f"  [+] Servidor Backend ativo em : {url}")
    print(f"  [+] Diretório de Dados/SQLite : {BASE_DIR / 'data'}")
    print(f"  [+] Pasta de Relatórios HTML  : {BASE_DIR / 'reports'}")
    print(f"  [+] Pasta de Logs de Auditoria: {BASE_DIR / 'logs'}")
    print("  [!] Pressione CTRL+C nesta janela para encerrar o Toolkit.")
    print("=" * 76)

    threading.Thread(target=launch_desktop_window, args=(url, host, port), daemon=True).start()
    start_AegisPulse_server(host=host, port=port, base_dir=BASE_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
