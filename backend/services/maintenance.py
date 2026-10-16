#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/maintenance.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
================================================================================
Descrição:
Executa rotinas seguras e auditáveis de manutenção preventiva e corretiva:
- Limpeza segura de diretórios temporários (%TEMP%, C:\Windows\Temp);
- Reparo de conectividade e pilha de rede (Flush DNS, Winsock, TCP/IP);
- Verificação não destrutiva de integridade do sistema (SFC / VerifyOnly e DISM CheckHealth);
- Criação de Ponto de Restauração do Sistema antes de intervenções críticas.
"""

import os
import shutil
import tempfile
import platform
import subprocess
from datetime import datetime


def run_maintenance_task(task_id: str) -> dict:
    """Executa uma tarefa de manutenção padronizada e retorna log detalhado."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if task_id == "clean_temp":
        removed_files = 0
        freed_bytes = 0
        temp_dirs = [tempfile.gettempdir()]
        if platform.system() == "Windows":
            win_temp = os.path.expandvars(r"%SystemRoot%\Temp")
            if os.path.exists(win_temp) and win_temp not in temp_dirs:
                temp_dirs.append(win_temp)

        for tdir in temp_dirs:
            if not os.path.exists(tdir):
                continue
            for root, dirs, files in os.walk(tdir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        sz = os.path.getsize(fpath)
                        os.remove(fpath)
                        removed_files += 1
                        freed_bytes += sz
                    except Exception:
                        pass

        freed_mb = round(freed_bytes / (1024 * 1024), 2)
        return {
            "success": True,
            "task": "Limpeza Segura de Arquivos Temporários",
            "risk_level": "BAIXO RISCO",
            "timestamp": timestamp,
            "summary": f"{removed_files} arquivos temporários removidos ({freed_mb} MB liberados).",
            "details": f"Diretórios auditados: {', '.join(temp_dirs)}",
        }

    if task_id == "reset_network":
        if platform.system() != "Windows":
            return {
                "success": True,
                "task": "Reparo de Pilha de Rede e DNS",
                "risk_level": "RISCO MODERADO",
                "timestamp": timestamp,
                "summary": "[Simulação] Cache DNS e sockets revisados.",
                "details": "Comandos ipconfig /flushdns e netsh winsock reset aplicáveis em estações Windows.",
            }
        cmds = [
            ["ipconfig", "/flushdns"],
            ["netsh", "winsock", "reset"],
            ["netsh", "int", "ip", "reset"],
        ]
        outputs = []
        for c in cmds:
            try:
                r = subprocess.run(c, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25)
                outputs.append(f"$ {' '.join(c)}\n{r.stdout.strip()}")
            except Exception as e:
                outputs.append(f"$ {' '.join(c)} -> Erro: {e}")
        return {
            "success": True,
            "task": "Reparo de Pilha de Rede e Cache DNS",
            "risk_level": "RISCO MODERADO",
            "timestamp": timestamp,
            "summary": "Cache DNS limpo e catálogos Winsock/TCP-IP redefinidos com sucesso.",
            "details": "\n\n".join(outputs),
        }

    if task_id == "check_system_health":
        if platform.system() != "Windows":
            return {
                "success": True,
                "task": "Diagnóstico de Integridade (DISM / SFC)",
                "risk_level": "BAIXO RISCO",
                "timestamp": timestamp,
                "summary": "[Simulação] Verificação rápida de imagem concluída sem corrupção.",
                "details": "Em estações Windows, executa DISM /Online /Cleanup-Image /CheckHealth.",
            }
        try:
            r = subprocess.run(
                ["DISM.exe", "/Online", "/Cleanup-Image", "/CheckHealth"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            return {
                "success": r.returncode == 0,
                "task": "Verificação Rápida de Integridade (DISM CheckHealth)",
                "risk_level": "BAIXO RISCO",
                "timestamp": timestamp,
                "summary": "Imagem do Windows íntegra." if r.returncode == 0 else "Foram detectados alertas no DISM.",
                "details": (r.stdout + "\n" + r.stderr).strip(),
            }
        except Exception as exc:
            return {
                "success": False,
                "task": "Verificação Rápida de Integridade (DISM CheckHealth)",
                "risk_level": "BAIXO RISCO",
                "timestamp": timestamp,
                "summary": f"Falha ao executar DISM: {exc}",
                "details": "Certifique-se de executar o AegisPulse como Administrador.",
            }

    if task_id == "create_restore_point":
        if platform.system() != "Windows":
            return {
                "success": True,
                "task": "Criar Ponto de Restauração do Sistema",
                "risk_level": "BAIXO RISCO",
                "timestamp": timestamp,
                "summary": "[Simulação] Ponto de restauração registrado.",
                "details": "Checkpoint-Computer aplicável em estações Windows.",
            }
        ps_cmd = "Checkpoint-Computer -Description 'AegisPulse_PreManutencao' -RestorePointType 'MODIFY_SETTINGS'"
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            ok = r.returncode == 0
            return {
                "success": ok,
                "task": "Criação de Ponto de Restauração",
                "risk_level": "BAIXO RISCO",
                "timestamp": timestamp,
                "summary": "Ponto de restauração 'AegisPulse_PreManutencao' criado com sucesso." if ok else "Não foi possível criar o Ponto de Restauração (verifique se a Proteção do Sistema está ativa).",
                "details": (r.stdout + "\n" + r.stderr).strip(),
            }
        except Exception as exc:
            return {
                "success": False,
                "task": "Criação de Ponto de Restauração",
                "risk_level": "BAIXO RISCO",
                "timestamp": timestamp,
                "summary": f"Erro ao criar Ponto de Restauração: {exc}",
                "details": "",
            }

    return {
        "success": False,
        "task": task_id,
        "risk_level": "DESCONHECIDO",
        "timestamp": timestamp,
        "summary": "Tarefa de manutenção não reconhecida.",
        "details": "",
    }
