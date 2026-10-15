#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/html_reporter.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.0.0
================================================================================
Descrição:
Etapa 10 — Gerador de Laudos Técnicos Executivos em HTML5/PDF (v4.0.0):
- Inclui Dossiê Forense de Armazenamento (Identificação completa, capacidades em
  Bytes, GB/TB e GiB/TiB, atributos SMART detalhados, Temperatura, Horas Ligadas
  e Dias, Desgaste, TBW, Erros Realocados/Pendentes/CRC, Classificação de Risco,
  Diagnóstico de Falhas e Procedimentos/Recomendações).
- Preserva Temperaturas de CPU/GPU, Seção PC Gamer, Matriz de Compatibilidade
  e Parecer Inteligente da IA.
"""

import re
import html
from datetime import datetime
from pathlib import Path


def _markdown_to_html(md_text: str) -> str:
    if not md_text:
        return ""
    lines = md_text.splitlines()
    out_lines = []
    in_list = False

    for raw_ln in lines:
        ln = raw_ln.strip()
        if not ln:
            if in_list:
                out_lines.append("</ul>")
                in_list = False
            out_lines.append("<div style='height:8px;'></div>")
            continue

        if ln in ("---", "***", "___"):
            if in_list:
                out_lines.append("</ul>")
                in_list = False
            out_lines.append("<hr style='border:none;border-top:1px solid #cbd5e1;margin:12px 0;'>")
            continue

        safe = html.escape(ln)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
        safe = re.sub(r"`([^`]+)`", r"<code>\1</code>", safe)
        safe = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", safe)

        if safe.startswith("### "):
            if in_list:
                out_lines.append("</ul>")
                in_list = False
            out_lines.append(f"<h3 class='ai-h3'>{safe[4:]}</h3>")
        elif safe.startswith("## "):
            if in_list:
                out_lines.append("</ul>")
                in_list = False
            out_lines.append(f"<h3 class='ai-h3'>{safe[3:]}</h3>")
        elif safe.startswith(("- ", "* ")):
            if not in_list:
                out_lines.append("<ul class='ai-ul'>")
                in_list = True
            out_lines.append(f"<li>{safe[2:]}</li>")
        elif re.match(r"^\d+\.\s+", safe):
            if not in_list:
                out_lines.append("<ul class='ai-ul'>")
                in_list = True
            out_lines.append(f"<li>{safe}</li>")
        else:
            if in_list:
                out_lines.append("</ul>")
                in_list = False
            out_lines.append(f"<p class='ai-p'>{safe}</p>")

    if in_list:
        out_lines.append("</ul>")
    return "\n".join(out_lines)


def generate_html_report(snapshot: dict, base_dir: Path, ai_analysis: str = "", action_logs: list | None = None) -> dict:
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    file_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    hw = snapshot.get("hardware", {})
    temps = hw.get("temperatures", {})
    os_info = snapshot.get("os", {})
    drv = snapshot.get("drivers_bios", {})
    bios = drv.get("bios", {})
    sw = snapshot.get("software", {})
    gaming = snapshot.get("gaming", {})
    gp = gaming.get("gamer_profile", {})
    compat = snapshot.get("compatibility", {})
    st_suite = snapshot.get("storage_suite", {})
    logs = action_logs or []

    hostname = html.escape(str(hw.get("hostname") or "Computador"))
    manuf = html.escape(str(hw.get("manufacturer") or "N/D"))
    model = html.escape(str(hw.get("model") or "N/D"))
    serial = html.escape(str(hw.get("serial_service_tag") or "N/D"))

    os_name = html.escape(str(os_info.get("os_name") or "N/D"))
    os_ver = html.escape(str(os_info.get("display_version") or "N/D"))
    os_build = html.escape(str(os_info.get("full_build") or "N/D"))

    # Seção Forense de Discos, SMART, Vida Útil e Riscos (v4.0.0)
    storage_cards_html = ""
    for dev in (st_suite.get("devices") or []):
        sm = dev.get("smart_summary") or {}
        lf = dev.get("lifespan") or {}
        rk = dev.get("risk_assessment") or {}
        cap = dev.get("capacity") or {}
        r_lvl = str(rk.get("risk_level") or "BAIXO")
        r_badge = "err" if r_lvl in ("ALTO", "CRÍTICO") else ("warn" if r_lvl == "MODERADO" else "ok")

        smart_rows = ""
        for a in (dev.get("smart_attributes") or [])[:14]:
            s_cls = "err" if a.get("severity") == "critical" else ("warn" if a.get("severity") == "warning" else "ok")
            smart_rows += f"""
            <tr>
                <td><code>{html.escape(str(a.get('id')))}</code></td>
                <td><strong>{html.escape(str(a.get('name')))}</strong></td>
                <td>{a.get('current')} / {a.get('worst')} (Lim: {a.get('threshold')})</td>
                <td><code>{html.escape(str(a.get('raw_hex')))}</code> ({a.get('raw_int')})</td>
                <td><strong>{html.escape(str(a.get('interpreted')))}</strong></td>
                <td><span class="badge {s_cls}">{html.escape(str(a.get('severity', 'ok')).upper())}</span></td>
            </tr>
            """
        if not smart_rows:
            smart_rows = '<tr><td colspan="6">Atributos SMART detalhados não expostos pela controladora/ponte USB deste dispositivo.</td></tr>'

        faults_html = ""
        for fd in (dev.get("fault_diagnostics") or []):
            faults_html += f"""
            <li>
                <strong>[{html.escape(str(fd.get('category')))}] {html.escape(str(fd.get('title')))}:</strong>
                {html.escape(str(fd.get('explanation')))}
                <br><em>Recomendação: {html.escape(str(fd.get('recommendation')))}</em>
            </li>
            """

        plan_html = "".join(f"<li>{html.escape(str(p))}</li>" for p in (rk.get("ordered_action_plan") or []))

        storage_cards_html += f"""
        <div style="border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <h3 style="font-size:15px;color:var(--accent);">
                    💿 Disco Físico #{dev.get('disk_number')} — {html.escape(str(dev.get('brand')))} {html.escape(str(dev.get('model')))}
                    (<code>{html.escape(str(dev.get('serial_number')))}</code>)
                </h3>
                <span class="badge {r_badge}">RISCO: {html.escape(r_lvl)} (Saúde: {rk.get('health_score', 100)}/100)</span>
            </div>
            <div class="grid" style="margin-bottom:8px;">
                <div>
                    <div class="kv"><span>Tipo / Interface / Protocolo:</span> <strong>{html.escape(str(dev.get('media_category')))} ({html.escape(str(dev.get('protocol')))})</strong></div>
                    <div class="kv"><span>Controlador / Firmware:</span> {html.escape(str(dev.get('controller')))} | FW: <code>{html.escape(str(dev.get('firmware')))}</code></div>
                    <div class="kv"><span>Capacidade Física (Decimal vs Binária):</span> <strong>{html.escape(str(cap.get('formatted')))}</strong> (<code>{cap.get('bytes', 0):,} bytes</code>)</div>
                    <div class="kv"><span>Tabela de Partições & Unidades:</span> <strong>{html.escape(str(dev.get('partition_style')))}</strong> ({', '.join(dev.get('drive_letters') or ['Sem Letra'])}) | Não Alocado: {dev.get('unallocated_capacity', {}).get('formatted')}</div>
                </div>
                <div>
                    <div class="kv"><span>Temperatura Atual do Disco:</span> <strong>{sm.get('temperature_c') if sm.get('temperature_c') is not None else 'N/D'} °C</strong></div>
                    <div class="kv"><span>Tempo Acumulado Ligado (POH):</span> <strong>{html.escape(str(lf.get('power_on_formatted')))}</strong> | Ciclos: {sm.get('power_cycles') or 'N/D'}</div>
                    <div class="kv"><span>Vida Útil (Fabricante vs Estimada TBW):</span> <strong>{html.escape(str(lf.get('manufacturer_reported_str')))}</strong></div>
                    <div class="kv"><span>Total Lido / Gravado (TBW):</span> Lido: {html.escape(str(lf.get('total_reads_formatted')))} | Gravado: <strong>{html.escape(str(lf.get('total_writes_formatted')))}</strong></div>
                </div>
            </div>
            <div class="kv"><span>Diagnóstico Especializado de Falhas & Causa-Raiz:</span></div>
            <ul class="ai-ul">{faults_html}</ul>
            <div class="kv" style="margin-top:6px;"><span>Plano de Ação Recomendado (Ordenado por Menor Risco aos Dados):</span></div>
            <ul class="ai-ul">{plan_html}</ul>
            <table style="margin-top:8px;">
                <thead>
                    <tr><th>ID</th><th>Atributo SMART / NVMe</th><th>Atual / Pior / Limiar</th><th>Valor Bruto</th><th>Interpretação Técnica</th><th>Severidade</th></tr>
                </thead>
                <tbody>{smart_rows}</tbody>
            </table>
        </div>
        """

    vol_rows = ""
    for v in hw.get("volumes", []):
        pct = float(v.get("used_percent") or 0)
        bar_color = "#ef4444" if pct >= 85 else ("#f59e0b" if pct >= 70 else "#10b981")
        vol_rows += f"""
        <tr>
            <td><strong>{html.escape(str(v.get('drive')))}</strong> ({html.escape(str(v.get('label')))})</td>
            <td>{html.escape(str(v.get('filesystem')))}</td>
            <td>{v.get('size_gb')} GiB</td>
            <td>{v.get('free_gb')} GiB</td>
            <td>
                <div class="bar-bg">
                    <div class="bar-fill" style="background-color:{bar_color} !important;width:{min(100, pct)}%;"></div>
                </div>
                <strong>{pct}%</strong>
            </td>
        </tr>
        """

    ded_gpu = gp.get("dedicated_gpu", {})
    int_gpu = gp.get("integrated_gpu", {})
    cpu_g = gp.get("cpu_gamer", {})
    ram_g = gp.get("ram_gamer", {})
    techs_html = ", ".join(html.escape(t) for t in gp.get("supported_technologies", [])) or "DirectX 12"
    bottlenecks_html = "".join(f"<li>{html.escape(b)}</li>" for b in gp.get("bottlenecks_and_alerts", []))

    outdated_rows = ""
    for s in sw.get("outdated_software", []):
        outdated_rows += f"""
        <tr>
            <td><strong>{html.escape(str(s.get('name')))}</strong></td>
            <td><code>{html.escape(str(s.get('id')))}</code></td>
            <td><span class="badge warn">{html.escape(str(s.get('current_version')))}</span></td>
            <td><span class="badge ok">{html.escape(str(s.get('available_version')))}</span></td>
        </tr>
        """
    if not outdated_rows:
        outdated_rows = '<tr><td colspan="4">Todos os softwares monitorados pelo Winget estão atualizados.</td></tr>'

    key_classes = {"DISPLAY", "NET", "MEDIA", "HDC", "SCSIADAPTER", "FIRMWARE"}
    filtered_drivers = []
    seen_names = set()
    for d in drv.get("drivers", []):
        d_cls = str(d.get("device_class", "")).upper()
        d_name = str(d.get("device_name", ""))
        is_alert = bool(d.get("outdated_flag"))
        if is_alert or d_cls in key_classes:
            sig_key = f"{d_cls}:{d_name}"
            if sig_key not in seen_names:
                seen_names.add(sig_key)
                filtered_drivers.append(d)

    drv_rows = ""
    for d in filtered_drivers[:18]:
        badge_cls = "warn" if d.get("outdated_flag") else "ok"
        drv_rows += f"""
        <tr>
            <td><strong>{html.escape(str(d.get('device_name')))}</strong></td>
            <td>{html.escape(str(d.get('device_class')))}</td>
            <td>{html.escape(str(d.get('manufacturer')))}</td>
            <td><code>{html.escape(str(d.get('version')))}</code></td>
            <td>{html.escape(str(d.get('date')))}</td>
            <td><span class="badge {badge_cls}">{html.escape(str(d.get('status')))}</span></td>
        </tr>
        """

    log_rows = ""
    for lg in logs:
        log_rows += f"""
        <tr>
            <td><code>{html.escape(str(lg.get('timestamp', now_str)))}</code></td>
            <td><strong>{html.escape(str(lg.get('action', 'Operação')))}</strong></td>
            <td>{html.escape(str(lg.get('summary', '')))}</td>
        </tr>
        """
    if not log_rows:
        log_rows = '<tr><td colspan="3">Coleta diagnóstica concluída.</td></tr>'

    ai_block = ""
    if ai_analysis.strip():
        formatted_ai = _markdown_to_html(ai_analysis)
        ai_block = f"""
        <div class="card ai-card" style="margin-top: 18px; border-left: 4px solid #0284c7;">
            <h2>✨ Parecer Inteligente — AegisPulse AI v4.0</h2>
            <div class="ai-content">{formatted_ai}</div>
        </div>
        """

    cpu_name = html.escape(hw.get("cpus", [{}])[0].get("name", "N/D")) if hw.get("cpus") else "N/D"
    gpu_name = html.escape(ded_gpu.get("name") or (hw.get("gpus", [{}])[0].get("name", "N/D") if hw.get("gpus") else "N/D"))
    bios_badge = "warn" if bios.get("needs_review") else "ok"

    html_doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Laudo Técnico AegisPulse v4.0 — {hostname}</title>
    <style>
        :root {{
            --bg: #0f172a;
            --card: #1e293b;
            --border: #334155;
            --text: #f8fafc;
            --muted: #94a3b8;
            --accent: #38bdf8;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 28px;
            line-height: 1.5;
        }}
        .container {{ max-width: 1140px; margin: 0 auto; }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #1e293b;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 22px;
            margin-bottom: 20px;
        }}
        .header h1 {{ font-size: 21px; color: var(--accent); }}
        .header p {{ color: var(--muted); font-size: 13.5px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
            margin-bottom: 18px;
        }}
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 18px;
            page-break-inside: avoid;
        }}
        .card h2 {{
            font-size: 14.5px;
            color: var(--accent);
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .kv {{ margin-bottom: 6px; font-size: 13.5px; }}
        .kv span {{ color: var(--muted); }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 8px;
            font-size: 12.5px;
        }}
        th, td {{
            text-align: left;
            padding: 7px 9px;
            border-bottom: 1px solid var(--border);
        }}
        th {{ color: var(--muted); font-weight: 600; background: rgba(15, 23, 42, 0.5); }}
        .bar-bg {{
            background-color: #334155 !important;
            border-radius: 6px;
            height: 10px;
            width: 110px;
            overflow: hidden;
            display: inline-block;
            vertical-align: middle;
            margin-right: 8px;
        }}
        .bar-fill {{ height: 100%; display: block; }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 11.5px;
            font-weight: 600;
        }}
        .badge.ok {{ background-color: rgba(16, 185, 129, 0.2) !important; color: #059669 !important; }}
        .badge.warn {{ background-color: rgba(245, 158, 11, 0.22) !important; color: #d97706 !important; }}
        .badge.err {{ background-color: rgba(239, 68, 68, 0.22) !important; color: #dc2626 !important; }}
        .ai-content {{ font-size: 13.5px; line-height: 1.6; color: #f1f5f9; }}
        .ai-h3 {{ color: #0284c7; font-size: 15px; margin: 12px 0 6px; }}
        .ai-ul {{ padding-left: 20px; margin: 6px 0; }}
        .ai-ul li {{ margin-bottom: 5px; }}
        .ai-p {{ margin-bottom: 6px; }}
        code {{ background: rgba(148, 163, 184, 0.18); padding: 1px 5px; border-radius: 4px; font-family: Consolas, monospace; }}
        .footer {{
            margin-top: 24px;
            text-align: center;
            color: var(--muted);
            font-size: 12.5px;
            border-top: 1px solid var(--border);
            padding-top: 14px;
        }}
        .btn-print {{
            background: var(--accent);
            color: #0f172a;
            border: none;
            padding: 9px 16px;
            border-radius: 6px;
            font-weight: 700;
            cursor: pointer;
        }}
        @media print {{
            body {{ background: #ffffff !important; color: #0f172a !important; padding: 8px; }}
            .card, .header {{ background: #ffffff !important; border: 1px solid #cbd5e1 !important; color: #0f172a !important; }}
            .header h1, .card h2, .ai-h3 {{ color: #0369a1 !important; }}
            .header p, .kv span, th, .footer {{ color: #475569 !important; }}
            th {{ background: #f1f5f9 !important; }}
            td, th {{ border-bottom: 1px solid #e2e8f0 !important; color: #0f172a !important; }}
            .ai-content, .ai-p, .ai-ul li {{ color: #0f172a !important; }}
            .bar-bg {{ background-color: #e2e8f0 !important; border: 1px solid #94a3b8; }}
            .btn-print {{ display: none !important; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h1>AEGISPULSE IT TOOLKIT v4.0 — DIAGNÓSTICO • AUTOMAÇÃO • INTELIGÊNCIA</h1>
            <p style="color:#0284c7;font-weight:600;margin-bottom:4px;">Tecnologia sob controle. Suporte com inteligência.</p>
            <p>Responsável Técnico / Autor: <strong>Adriano Barboza</strong> | WhatsApp: <strong>+55 61 98515-8434</strong> | adriano9200@gmail.com</p>
            <p>Data/Hora da Coleta: {now_str} | Hostname: <strong>{hostname}</strong></p>
        </div>
        <button class="btn-print" onclick="window.print()">🖨️ Imprimir / Salvar PDF</button>
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
            <h2>Hardware & Monitoramento Térmico (°C)</h2>
            <div class="kv"><span>Processador:</span> <strong>{cpu_name}</strong></div>
            <div class="kv"><span>Temperatura Atual CPU:</span> <strong>{temps.get('cpu_temp_c', 45)}°C</strong> — <span class="badge ok">{html.escape(str(temps.get('cpu_temp_status', 'Ideal')))}</span></div>
            <div class="kv"><span>GPU Principal & Temp:</span> <strong>{gpu_name} ({temps.get('gpu_temp_c', 42)}°C)</strong></div>
            <div class="kv"><span>Memória RAM Total:</span> <strong>{hw.get('total_ram_gb')} GB</strong> ({len(hw.get('ram_modules', []))} módulo(s))</div>
        </div>

        <div class="card">
            <h2>Firmware BIOS / UEFI</h2>
            <div class="kv"><span>Fabricante BIOS:</span> {html.escape(str(bios.get('manufacturer')))}</div>
            <div class="kv"><span>Versão SMBIOS:</span> <code>{html.escape(str(bios.get('smbios_version')))}</code></div>
            <div class="kv"><span>Data de Lançamento:</span> {html.escape(str(bios.get('release_date')))} ({bios.get('age_months')} meses)</div>
            <div class="kv"><span>Status:</span> <span class="badge {bios_badge}">{html.escape(str(bios.get('status_label')))}</span></div>
        </div>
    </div>

    <!-- NOVA SEÇÃO v4.0: DOSSIÊ FORENSE DE ARMAZENAMENTO, SAÚDE SMART, VIDA ÚTIL & RISCOS -->
    <div class="card" style="margin-bottom: 18px; border-left: 4px solid #f59e0b;">
        <h2>💿 Dossiê Forense de Armazenamento, Saúde SMART, Vida Útil (TBW/POH) & Risco Operacional</h2>
        {storage_cards_html}
        <h3 style="font-size:13.5px;color:var(--accent);margin:10px 0 6px;">Ocupação de Volumes Lógicos Montados</h3>
        <table>
            <thead>
                <tr><th>Unidade</th><th>Sistema de Arquivos</th><th>Capacidade (GiB)</th><th>Espaço Livre</th><th>Ocupação Visual</th></tr>
            </thead>
            <tbody>{vol_rows}</tbody>
        </table>
    </div>

    <!-- SEÇÃO EXCLUSIVA PC GAMER -->
    <div class="card" style="margin-bottom: 18px; border-left: 4px solid #10b981;">
        <h2>🎮 Análise Completa PC Gamer & Performance Gráfica</h2>
        <div class="grid" style="margin-bottom:10px;">
            <div>
                <div class="kv"><span>Classificação Gamer (Tier):</span> <strong>{html.escape(str(gp.get('gamer_tier', 'Workstation / Gamer')))}</strong></div>
                <div class="kv"><span>Perfil de Resolução Ideal:</span> <strong>{html.escape(str(gp.get('target_resolution', '1080p Full HD')))}</strong></div>
                <div class="kv"><span>Placa de Vídeo Dedicada (Offboard):</span> <strong>{html.escape(str(ded_gpu.get('name', gpu_name)))} ({html.escape(str(ded_gpu.get('vram_gb', 'N/D')))}) — {temps.get('gpu_temp_c', 42)}°C</strong></div>
                <div class="kv"><span>Vídeo Integrado Secundário (iGPU):</span> {html.escape(str(int_gpu.get('name', 'N/D')))}</div>
            </div>
            <div>
                <div class="kv"><span>Processador Gamer:</span> <strong>{html.escape(str(cpu_g.get('name', cpu_name)))} ({temps.get('cpu_temp_c', 45)}°C)</strong></div>
                <div class="kv"><span>Arquitetura de Memória RAM:</span> <strong>{html.escape(str(ram_g.get('total_gb', '')))} @ {html.escape(str(ram_g.get('speed_mhz', '')))}</strong> — <span class="badge ok">{html.escape(str(ram_g.get('channel_status', '')))}</span></div>
                <div class="kv"><span>Tecnologias Gráficas Compatíveis:</span> {techs_html}</div>
                <div class="kv"><span>Bibliotecas e DLLs de Jogos (32/64-bit):</span> <strong>{gaming.get('missing_dlls_count', 0)} ausente(s)</strong></div>
            </div>
        </div>
        <div class="kv"><span>Diagnóstico de Equilíbrio e Gargalos (Bottlenecks):</span></div>
        <ul class="ai-ul">{bottlenecks_html}</ul>
    </div>

    <!-- SEÇÃO DE COMPATIBILIDADE DE HARDWARE & UPGRADES -->
    <div class="card" style="margin-bottom: 18px; border-left: 4px solid #38bdf8;">
        <h2>🧩 Matriz de Compatibilidade de Hardware & Upgrades (Setup Completo)</h2>
        <div class="grid" style="margin-bottom:6px;">
            <div>
                <div class="kv"><span>Socket da Placa-Mãe / CPU:</span> <strong>{html.escape(str(compat.get('cpu_socket', 'N/D')))}</strong></div>
                <div class="kv"><span>Upgrades de Processador Compatíveis:</span> {html.escape(str(compat.get('compatible_cpu_upgrades', 'N/D')))}</div>
                <div class="kv"><span>Padrão de Memória RAM:</span> <strong>{html.escape(str(compat.get('ram_standard', 'DDR4')))}</strong> (Expansão: {html.escape(str(compat.get('ram_compatible_spec', '')))})</div>
            </div>
            <div>
                <div class="kv"><span>Barramento de Armazenamento:</span> {html.escape(str(compat.get('storage_compatibility', 'NVMe / SATA')))}</div>
                <div class="kv"><span>Upgrades de Placa de Vídeo (PCIe x16):</span> {html.escape(str(compat.get('compatible_gpu_upgrades', 'N/D')))}</div>
                <div class="kv"><span>Fonte Recomendada (PSU):</span> <strong>{html.escape(str(compat.get('recommended_psu', '500W 80 Plus')))}</strong></div>
            </div>
        </div>
    </div>

    <div class="card" style="margin-bottom: 18px;">
        <h2>Softwares com Atualização Pendente (Winget)</h2>
        <table>
            <thead>
                <tr><th>Software</th><th>ID Winget</th><th>Versão Instalada</th><th>Nova Versão Disponível</th></tr>
            </thead>
            <tbody>{outdated_rows}</tbody>
        </table>
    </div>

    <div class="card" style="margin-bottom: 18px;">
        <h2>Resumo Executivo de Drivers Principais & Alertas ({drv.get('total_drivers', 0)} auditados | {drv.get('outdated_drivers_count', 0)} com revisão recomendada)</h2>
        <table>
            <thead>
                <tr><th>Dispositivo Principal</th><th>Classe</th><th>Fabricante</th><th>Versão</th><th>Data</th><th>Status</th></tr>
            </thead>
            <tbody>{drv_rows}</tbody>
        </table>
    </div>

    <div class="card" style="margin-bottom: 18px;">
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
        <strong>AegisPulse IT Toolkit v4.0.0</strong> — Diagnóstico • Automação • Inteligência | <em>Tecnologia sob controle. Suporte com inteligência.</em><br>
        Desenvolvido por <strong>Adriano Barboza</strong> • WhatsApp Comercial: <strong>+55 61 98515-8434</strong> • adriano9200@gmail.com
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
