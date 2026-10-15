#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/html_reporter.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
================================================================================
Descrição:
Produz Relatórios Técnicos e Logs em HTML5 profissional, responsivo e pronto
para impressão/exportação em PDF. Inclui cabeçalho com identificação do autor
Adriano Barboza, resumo executivo, hardware, SO/Build, BIOS, drivers, softwares
desatualizados, histórico de ações executadas e parecer do Gemini AI.
"""

import html
from datetime import datetime
from pathlib import Path


def generate_html_report(snapshot: dict, base_dir: Path, ai_analysis: str = "", action_logs: list | None = None) -> dict:
    """Gera um arquivo HTML completo na pasta reports/ e retorna o caminho."""
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    file_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    hw = snapshot.get("hardware", {})
    os_info = snapshot.get("os", {})
    drv = snapshot.get("drivers_bios", {})
    bios = drv.get("bios", {})
    sw = snapshot.get("software", {})
    logs = action_logs or []

    hostname = html.escape(str(hw.get("hostname") or "Computador"))
    manuf = html.escape(str(hw.get("manufacturer") or "N/D"))
    model = html.escape(str(hw.get("model") or "N/D"))
    serial = html.escape(str(hw.get("serial_service_tag") or "N/D"))

    os_name = html.escape(str(os_info.get("os_name") or "N/D"))
    os_ver = html.escape(str(os_info.get("display_version") or "N/D"))
    os_build = html.escape(str(os_info.get("full_build") or "N/D"))

    # Linhas de Discos/Volumes
    vol_rows = ""
    for v in hw.get("volumes", []):
        pct = float(v.get("used_percent") or 0)
        bar_color = "#ef4444" if pct > 85 else ("#f59e0b" if pct > 70 else "#10b981")
        vol_rows += f"""
        <tr>
            <td><strong>{html.escape(str(v.get('drive')))}</strong> ({html.escape(str(v.get('label')))})</td>
            <td>{html.escape(str(v.get('filesystem')))}</td>
            <td>{v.get('size_gb')} GB</td>
            <td>{v.get('free_gb')} GB</td>
            <td>
                <div style="background:#1e293b;border-radius:6px;height:10px;width:120px;overflow:hidden;display:inline-block;vertical-align:middle;margin-right:8px;">
                    <div style="background:{bar_color};height:100%;width:{min(100, pct)}%;"></div>
                </div>
                {pct}%
            </td>
        </tr>
        """

    # Linhas de Softwares Obsoletos
    outdated_rows = ""
    for s in sw.get("outdated_software", []):
        outdated_rows += f"""
        <tr>
            <td>{html.escape(str(s.get('name')))}</td>
            <td><code>{html.escape(str(s.get('id')))}</code></td>
            <td><span class="badge warn">{html.escape(str(s.get('current_version')))}</span></td>
            <td><span class="badge ok">{html.escape(str(s.get('available_version')))}</span></td>
        </tr>
        """
    if not outdated_rows:
        outdated_rows = '<tr><td colspan="4">Nenhum software obsoleto pendente no Winget ou verificação não aplicável.</td></tr>'

    # Linhas de Drivers (destacando antigos ou com erro)
    drv_rows = ""
    for d in drv.get("drivers", [])[:40]:
        badge_cls = "warn" if d.get("outdated_flag") else "ok"
        drv_rows += f"""
        <tr>
            <td>{html.escape(str(d.get('device_name')))}</td>
            <td>{html.escape(str(d.get('device_class')))}</td>
            <td>{html.escape(str(d.get('manufacturer')))}</td>
            <td><code>{html.escape(str(d.get('version')))}</code></td>
            <td>{html.escape(str(d.get('date')))}</td>
            <td><span class="badge {badge_cls}">{html.escape(str(d.get('status')))}</span></td>
        </tr>
        """

    # Histórico de Ações Executadas na Sessão
    log_rows = ""
    for lg in logs:
        log_rows += f"""
        <tr>
            <td>{html.escape(str(lg.get('timestamp', now_str)))}</td>
            <td><strong>{html.escape(str(lg.get('action', 'Operação')))}</strong></td>
            <td>{html.escape(str(lg.get('summary', '')))}</td>
        </tr>
        """
    if not log_rows:
        log_rows = '<tr><td colspan="3">Apenas coleta diagnóstica (nenhuma alteração executada na sessão).</td></tr>'

    ai_block = ""
    if ai_analysis.strip():
        ai_block = f"""
        <div class="card" style="margin-top: 20px; border-left: 4px solid #38bdf8;">
            <h2>Parecer Inteligente — Google Gemini AI</h2>
            <pre style="white-space: pre-wrap; font-family: inherit; color: #e2e8f0; line-height: 1.6;">{html.escape(ai_analysis)}</pre>
        </div>
        """

    cpu_name = html.escape(hw.get("cpus", [{}])[0].get("name", "N/D")) if hw.get("cpus") else "N/D"
    gpu_name = html.escape(hw.get("gpus", [{}])[0].get("name", "N/D")) if hw.get("gpus") else "N/D"
    bios_badge = "warn" if bios.get("needs_review") else "ok"

    html_doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Laudo Técnico AegisPulse — {hostname}</title>
    <style>
        :root {{
            --bg: #0f172a;
            --card: #1e293b;
            --border: #334155;
            --text: #f8fafc;
            --muted: #94a3b8;
            --accent: #38bdf8;
            --ok: #10b981;
            --warn: #f59e0b;
            --err: #ef4444;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 32px;
            line-height: 1.5;
        }}
        .container {{ max-width: 1140px; margin: 0 auto; }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        .header h1 {{ font-size: 24px; color: var(--accent); }}
        .header p {{ color: var(--muted); font-size: 14px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
        }}
        .card h2 {{
            font-size: 16px;
            color: var(--accent);
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .kv {{ margin-bottom: 8px; font-size: 14px; }}
        .kv span {{ color: var(--muted); }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 13.5px;
        }}
        th, td {{
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
        }}
        th {{ color: var(--muted); font-weight: 600; background: rgba(15, 23, 42, 0.5); }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge.ok {{ background: rgba(16, 185, 129, 0.18); color: #34d399; }}
        .badge.warn {{ background: rgba(245, 158, 11, 0.18); color: #fbbf24; }}
        .badge.err {{ background: rgba(239, 68, 68, 0.18); color: #f87171; }}
        .footer {{
            margin-top: 32px;
            text-align: center;
            color: var(--muted);
            font-size: 13px;
            border-top: 1px solid var(--border);
            padding-top: 16px;
        }}
        .btn-print {{
            background: var(--accent);
            color: #0f172a;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
        }}
        @media print {{
            body {{ background: #ffffff; color: #0f172a; padding: 10px; }}
            .card, .header {{ background: #ffffff; border: 1px solid #cbd5e1; }}
            .btn-print {{ display: none; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h1>AEGISPULSE IT TOOLKIT — DIAGNÓSTICO • AUTOMAÇÃO • INTELIGÊNCIA</h1>
            <p style="color:#38bdf8;font-weight:600;margin-bottom:4px;">Tecnologia sob controle. Suporte com inteligência.</p>
            <p>Responsável Técnico / Autor do Toolkit: <strong>Adriano Barboza</strong> (adriano9200@gmail.com)</p>
            <p>Data/Hora da Coleta: {now_str} | Hostname: <strong>{hostname}</strong></p>
        </div>
        <button class="btn-print" onclick="window.print()">Imprimir / Salvar PDF</button>
    </div>

    <div class="grid">
        <div class="card">
            <h2>Identificação do Equipamento</h2>
            <div class="kv"><span>Fabricante:</span> <strong>{manuf}</strong></div>
            <div class="kv"><span>Modelo:</span> <strong>{model}</strong></div>
            <div class="kv"><span>Serial / Service Tag:</span> <code>{serial}</code></div>
            <div class="kv"><span>Placa-Mãe:</span> {html.escape(str(hw.get('motherboard', {}).get('manufacturer')))} {html.escape(str(hw.get('motherboard', {}).get('product')))}</div>
        </div>

        <div class="card">
            <h2>Sistema Operacional</h2>
            <div class="kv"><span>Edição:</span> <strong>{os_name}</strong></div>
            <div class="kv"><span>Versão:</span> <strong>{os_ver}</strong></div>
            <div class="kv"><span>Build / UBR:</span> <code>{os_build}</code></div>
            <div class="kv"><span>Arquitetura / Uptime:</span> {html.escape(str(os_info.get('architecture')))} ({os_info.get('uptime_hours')} h ligado)</div>
        </div>

        <div class="card">
            <h2>Hardware Principal</h2>
            <div class="kv"><span>Processador:</span> <strong>{cpu_name}</strong></div>
            <div class="kv"><span>Memória RAM Total:</span> <strong>{hw.get('total_ram_gb')} GB</strong> ({len(hw.get('ram_modules', []))} módulo(s))</div>
            <div class="kv"><span>Vídeo (GPU):</span> {gpu_name}</div>
        </div>

        <div class="card">
            <h2>Firmware BIOS / UEFI</h2>
            <div class="kv"><span>Fabricante BIOS:</span> {html.escape(str(bios.get('manufacturer')))}</div>
            <div class="kv"><span>Versão SMBIOS:</span> <code>{html.escape(str(bios.get('smbios_version')))}</code></div>
            <div class="kv"><span>Data de Lançamento:</span> {html.escape(str(bios.get('release_date')))} ({bios.get('age_months')} meses)</div>
            <div class="kv"><span>Status:</span> <span class="badge {bios_badge}">{html.escape(str(bios.get('status_label')))}</span></div>
        </div>
    </div>

    <div class="card" style="margin-bottom: 20px;">
        <h2>Armazenamento e Partições</h2>
        <table>
            <thead>
                <tr><th>Unidade</th><th>Sistema de Arquivos</th><th>Capacidade</th><th>Espaço Livre</th><th>Ocupação</th></tr>
            </thead>
            <tbody>{vol_rows}</tbody>
        </table>
    </div>

    <div class="card" style="margin-bottom: 20px;">
        <h2>Softwares com Atualização Pendente (Winget)</h2>
        <table>
            <thead>
                <tr><th>Software</th><th>ID Winget</th><th>Versão Instalada</th><th>Nova Versão Disponível</th></tr>
            </thead>
            <tbody>{outdated_rows}</tbody>
        </table>
    </div>

    <div class="card" style="margin-bottom: 20px;">
        <h2>Auditoria de Drivers ({drv.get('total_drivers', 0)} analisados | {drv.get('outdated_drivers_count', 0)} antigos | {drv.get('error_devices_count', 0)} com erro)</h2>
        <table>
            <thead>
                <tr><th>Dispositivo</th><th>Classe</th><th>Fabricante</th><th>Versão</th><th>Data</th><th>Status</th></tr>
            </thead>
            <tbody>{drv_rows}</tbody>
        </table>
    </div>

    <div class="card" style="margin-bottom: 20px;">
        <h2>Log de Auditoria e Ações Executadas na Sessão</h2>
        <table>
            <thead>
                <tr><th>Data/Hora</th><th>Operação</th><th>Resultado / Detalhes</th></tr>
            </thead>
            <tbody>{log_rows}</tbody>
        </table>
    </div>

    {ai_block}

    <div class="footer">
        <strong>AegisPulse IT Toolkit v1.1.0</strong> — Diagnóstico • Automação • Inteligência | <em>Tecnologia sob controle. Suporte com inteligência.</em> • Desenvolvido por <strong>Adriano Barboza</strong> (adriano9200@gmail.com)
    </div>
</div>
</body>
</html>"""

    reports_dir = base_dir / "reports"
    logs_dir = base_dir / "logs"
    reports_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    report_filename = f"Laudo_AegisPulse_{hostname}_{file_stamp}.html"
    report_path = reports_dir / report_filename
    log_copy_path = logs_dir / f"Log_Sessao_{hostname}_{file_stamp}.html"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    with open(log_copy_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    return {
        "success": True,
        "filename": report_filename,
        "report_path": str(report_path),
        "log_path": str(log_copy_path),
        "url": f"/reports/{report_filename}",
    }
