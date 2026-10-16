#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/html_reporter.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  5.5.0
================================================================================
Descrição:
Gerador de Laudos Técnicos Executivos em HTML5 e PDF Nativo (ISO 32000-1 %PDF-1.4):
- Corrige definitivamente o NameError de health_score_panel_html.
- Gera e valida tanto o arquivo .HTML quanto o arquivo .PDF binário estruturado.
- Integra Health Score (8 pilares), Dossiê Forense de Discos/SMART,
  AegisPulse Crash Investigator (Eventos Críticos, BSOD/Dumps, Confiabilidade,
  Hardware/I/O, Hipóteses, Evidências Favoráveis/Contrárias e Plano de Ação N3)
  e Parecer Assistido por IA (com fallback técnico determinístico se a IA estiver
  indisponível).
- Minimiza dados sensíveis e diferencia Fatos Coletados, Interpretações do
  Sistema e Recomendações Geradas por IA.
"""

from __future__ import annotations

import html
import os
import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any


def _markdown_to_html(md_text: str) -> str:
    if not md_text:
        return ""
    lines = str(md_text).splitlines()
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


def _sanitize_filename_token(val: str, default: str = "Equipamento") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(val or "").strip()).strip("_")
    return cleaned[:48] if cleaned else default


def _mask_sensitive_identifier(val: str) -> str:
    """Minimiza exposição completa de seriais longos ou IDs sensíveis em relatórios externos quando aplicável."""
    s = str(val or "").strip()
    if not s or s in ("N/D", "UNKNOWN"):
        return "N/D"
    return s


def _pdf_escape_text(text: str) -> bytes:
    """Converte string UTF-8 para bytes WinAnsi/Latin-1 seguros para literais de texto PDF."""
    replacements = {
        "—": "-",
        "–": "-",
        "•": "*",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "➔": "->",
        "→": "->",
    }
    cleaned = str(text or "")
    for k, v in replacements.items():
        cleaned = cleaned.replace(k, v)
    # Remove emojis/símbolos fora do intervalo Latin-1 (0x20..0xFF) mantendo acentuação do Português
    latin_chars = []
    for ch in cleaned:
        code = ord(ch)
        if 32 <= code <= 126 or 160 <= code <= 255:
            latin_chars.append(ch)
        elif ch in ("\t",):
            latin_chars.append(" ")
    safe_str = "".join(latin_chars)
    safe_str = safe_str.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return safe_str.encode("latin-1", errors="replace")


def build_valid_pdf_bytes(title: str, sections: list[tuple[str, list[str]]]) -> bytes:
    """
    Gera um documento PDF 1.4 binário multi-página 100% válido (ISO 32000-1)
    usando apenas a biblioteca padrão do Python (sem dependências externas).
    Suporta acentuação em Português (WinAnsiEncoding) e paginação automática A4.
    """
    page_width = 595
    page_height = 842
    margin_left = 42
    top_y = 795
    bottom_y = 48
    line_height = 13

    # Constrói linhas estruturadas: (is_bold, font_size, text_str, color_rgb)
    render_lines: list[tuple[bool, int, str, tuple[float, float, float]]] = []
    render_lines.append((True, 14, "AEGISPULSE IT TOOLKIT v5.5 - LAUDO TECNICO EXECUTIVO", (0.02, 0.45, 0.72)))
    render_lines.append((False, 9, title, (0.30, 0.35, 0.42)))
    render_lines.append((False, 9, "Responsavel Tecnico: Adriano Barboza | WhatsApp: +55 61 98515-8434 | adriano9200@gmail.com", (0.30, 0.35, 0.42)))
    render_lines.append((False, 9, "-" * 96, (0.65, 0.70, 0.78)))

    for sec_title, sec_items in sections:
        render_lines.append((True, 11, "", (0.0, 0.0, 0.0)))
        render_lines.append((True, 11, f"[ {sec_title.upper()} ]", (0.05, 0.35, 0.60)))
        for item in sec_items:
            for subline in str(item or "").splitlines():
                wrapped = textwrap.wrap(subline.strip(), width=92) or [""]
                for wln in wrapped:
                    is_hdr = wln.startswith(("FATO:", "HIPOTESE:", "ACAO:", "ALERTA:", "CRITICO:", "IMPORTANTE:"))
                    col = (0.75, 0.12, 0.12) if wln.startswith(("ALERTA:", "CRITICO:")) else (0.12, 0.16, 0.22)
                    render_lines.append((is_hdr, 9, wln, col))

    # Paginação automática
    pages_streams: list[bytes] = []
    curr_cmds: list[bytes] = []
    curr_y = top_y

    for is_bold, fsize, txt, (r, g, b) in render_lines:
        if curr_y < bottom_y:
            pages_streams.append(b"\n".join(curr_cmds))
            curr_cmds = []
            curr_y = top_y
        if txt:
            font_ref = b"/F2" if is_bold else b"/F1"
            escaped = _pdf_escape_text(txt)
            cmd = (
                b"BT "
                + f"{r:.2f} {g:.2f} {b:.2f} rg ".encode("ascii")
                + font_ref
                + f" {fsize} Tf 1 0 0 1 {margin_left} {curr_y} Tm (".encode("ascii")
                + escaped
                + b") Tj ET"
            )
            curr_cmds.append(cmd)
        curr_y -= line_height

    if curr_cmds or not pages_streams:
        pages_streams.append(b"\n".join(curr_cmds))

    # Montagem de objetos PDF:
    # 1: Catalog, 2: Pages, 3: Font F1 (Helvetica), 4: Font F2 (Helvetica-Bold)
    # Para cada página i: obj (5 + 2*i) = Page, obj (6 + 2*i) = Contents stream
    objects: list[bytes] = []
    num_pages = len(pages_streams)
    kids_refs = " ".join(f"{5 + 2 * i} 0 R" for i in range(num_pages))

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [ {kids_refs} ] /Count {num_pages} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

    for i, stream_bytes in enumerate(pages_streams):
        content_obj_num = 6 + 2 * i
        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_obj_num} 0 R >>"
        ).encode("ascii")
        stream_obj = (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream"
        )
        objects.append(page_obj)
        objects.append(stream_obj)

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = [0]
    for idx, obj_body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode("ascii"))
        out.extend(obj_body)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)


def _build_health_score_html(hs: dict[str, Any]) -> str:
    if not isinstance(hs, dict) or hs.get("overall_score") is None:
        return """
        <div class="card" style="margin-bottom: 18px; border-left: 4px solid #64748b;">
            <h2>🩺 AegisPulse Health Score — Índice de Saúde do Computador</h2>
            <p class="kv"><span>Status:</span> Avaliação de pontuação não incluída neste snapshot parcial.</p>
        </div>
        """
    score = hs.get("overall_score", 0)
    classification = html.escape(str(hs.get("classification") or "N/D"))
    cov = hs.get("coverage") or {}
    cov_label = html.escape(str(cov.get("label") or "8/8 categorias"))
    cov_pct = cov.get("percent", 100)
    badge_cls = hs.get("classification_badge") or ("ok" if score >= 75 else ("warn" if score >= 60 else "err"))
    cap_notice = (
        "<div class='kv' style='color:#ef4444;font-weight:700;'>🚨 TRAVA CRÍTICA ATIVA: Pontuação limitada a 59 (Ruim) devido a falha crítica de hardware/armazenamento.</div>"
        if hs.get("critical_cap_applied")
        else ""
    )

    cat_rows = ""
    for ck, cv in (hs.get("categories") or {}).items():
        if not isinstance(cv, dict):
            continue
        c_st = str(cv.get("status") or "normal")
        c_b = "err" if c_st == "critico" else ("warn" if c_st == "atencao" else "ok")
        c_score = f"{cv.get('score')}/100" if cv.get("available", True) else "Indisponível"
        cat_rows += f"""
        <tr>
            <td><strong>{html.escape(str(cv.get('category_title') or ck))}</strong></td>
            <td><strong>{c_score}</strong></td>
            <td>{cv.get('effective_weight_pct', 0)}%</td>
            <td><span class="badge {c_b}">{html.escape(c_st.upper())}</span></td>
            <td>{html.escape(str(cv.get('summary') or ''))}</td>
        </tr>
        """

    find_rows = ""
    for f in (hs.get("prioritized_findings") or [])[:10]:
        if not isinstance(f, dict):
            continue
        sev = str(f.get("severity") or "MÉDIO")
        f_b = "err" if sev == "CRÍTICO" else ("warn" if sev == "ALTO" else "ok")
        find_rows += f"""
        <tr>
            <td><strong>{html.escape(str(f.get('title')))}</strong><br><small>{html.escape(str(f.get('affected_component')))}</small></td>
            <td><span class="badge {f_b}">{html.escape(sev)}</span></td>
            <td><code>{html.escape(str(f.get('technical_evidence')))}</code></td>
            <td>{html.escape(str(f.get('recommendation')))}</td>
            <td>{html.escape(str(f.get('action_risk_level')))}</td>
        </tr>
        """

    findings_table = (
        f"""
        <h3 style="font-size:13.5px;color:var(--accent);margin:12px 0 6px;">Achados Técnicos Priorizados (Baseados em Evidências)</h3>
        <table>
            <thead>
                <tr><th>Problema / Componente</th><th>Severidade</th><th>Evidência Observada</th><th>Recomendação</th><th>Risco da Ação</th></tr>
            </thead>
            <tbody>{find_rows}</tbody>
        </table>
        """
        if find_rows
        else ""
    )

    return f"""
    <div class="card" style="margin-bottom: 18px; border-left: 4px solid #10b981;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <h2>🩺 AegisPulse Health Score — Índice Determinístico de Saúde do Computador</h2>
            <span class="badge {badge_cls}" style="font-size:14px;padding:4px 12px;">NOTA: {score}/100 ({classification.upper()})</span>
        </div>
        <div class="kv"><span>Cobertura Analítica:</span> <strong>{cov_label} ({cov_pct}%)</strong> | ID do Equipamento: <code>{html.escape(str(hs.get('machine_uuid') or 'N/D'))}</code></div>
        {cap_notice}
        <table>
            <thead>
                <tr><th>Pilar Avaliado</th><th>Nota</th><th>Peso Efetivo</th><th>Status</th><th>Evidência Técnica</th></tr>
            </thead>
            <tbody>{cat_rows}</tbody>
        </table>
        {findings_table}
    </div>
    """


def _build_crash_investigator_html(crash_data: dict[str, Any]) -> str:
    if not isinstance(crash_data, dict) or not crash_data.get("collected_at"):
        return ""

    summary = crash_data.get("incident_summary") or {}
    bsod = crash_data.get("bsod_analysis") or {}
    rel = crash_data.get("reliability_history") or {}
    hw_io = crash_data.get("hardware_io_correlation") or {}
    hyps = crash_data.get("hypotheses") or []
    plan = crash_data.get("action_plan") or []
    timeline = crash_data.get("consolidated_timeline") or []
    limitations = crash_data.get("limitations_and_gaps") or []

    sev_lvl = str(summary.get("overall_severity") or "NORMAL")
    sev_badge = "err" if sev_lvl in ("CRÍTICO", "ALTO") else ("warn" if sev_lvl == "MODERADO" else "ok")

    hyp_rows = ""
    for h in hyps:
        if not isinstance(h, dict):
            continue
        conf = str(h.get("confidence_level") or "Média")
        hb = "err" if "Alta" in conf else ("warn" if "Média" in conf else "ok")
        fav_list = "; ".join(str(x) for x in (h.get("favorable_evidence") or [])) or "N/D"
        con_list = "; ".join(str(x) for x in (h.get("contrary_evidence") or [])) or "Nenhuma"
        hyp_rows += f"""
        <tr>
            <td><strong>#{h.get('rank', 1)} — {html.escape(str(h.get('title')))}</strong><br><small>{html.escape(str(h.get('category')))}</small></td>
            <td><span class="badge {hb}">{html.escape(conf)} ({h.get('plausibility_score', 50)}%)</span></td>
            <td><small><strong>Favoráveis (Fatos):</strong> {html.escape(fav_list)}</small><br><small><strong>Contrárias/Lacunas:</strong> {html.escape(con_list)}</small></td>
            <td><small>{html.escape(str(h.get('confidence_justification') or ''))}</small></td>
        </tr>
        """
    if not hyp_rows:
        hyp_rows = '<tr><td colspan="4">Nenhuma hipótese de falha crítica gerada no período analisado.</td></tr>'

    tl_rows = ""
    for ev in timeline[:18]:
        if not isinstance(ev, dict):
            continue
        ev_sev = str(ev.get("severity") or "Info")
        eb = "err" if ev_sev.lower() in ("critical", "crítico", "error", "erro") else ("warn" if "warn" in ev_sev.lower() or "aten" in ev_sev.lower() else "ok")
        tl_rows += f"""
        <tr>
            <td><code>{html.escape(str(ev.get('timestamp')))}</code></td>
            <td><strong>{html.escape(str(ev.get('source')))}</strong> (ID <code>{html.escape(str(ev.get('event_id')))}</code>)</td>
            <td><span class="badge {eb}">{html.escape(ev_sev.upper())}</span></td>
            <td><small><strong>Mensagem Original (Fato):</strong> {html.escape(str(ev.get('original_message') or '')[:180])}</small><br><small><em>Interpretação do Sistema:</em> {html.escape(str(ev.get('technical_interpretation') or ''))}</small></td>
        </tr>
        """
    if not tl_rows:
        tl_rows = '<tr><td colspan="4">Nenhum evento crítico registrado no período filtrado.</td></tr>'

    plan_rows = ""
    for act in plan:
        if not isinstance(act, dict):
            continue
        rk_l = str(act.get("risk_level") or "BAIXO")
        ab = "err" if "ALTO" in rk_l else ("warn" if "MODERADO" in rk_l else "ok")
        plan_rows += f"""
        <tr>
            <td><strong>{html.escape(str(act.get('title')))}</strong><br><small>{html.escape(str(act.get('objective')))}</small></td>
            <td><code>{html.escape(str(act.get('suggested_command_or_procedure')))}</code></td>
            <td><span class="badge {ab}">{html.escape(rk_l)}</span></td>
            <td><strong>{'Sim (Obrigatório)' if act.get('requires_backup') else 'Não'}</strong></td>
            <td><small>{html.escape(str(act.get('expected_impact')))}</small></td>
        </tr>
        """

    lim_html = "".join(f"<li>{html.escape(str(l))}</li>" for l in limitations) or "<li>Coleta realizada sem restrições reportadas.</li>"

    return f"""
    <div class="card" style="margin-bottom: 18px; border-left: 4px solid #ef4444;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <h2>💥 AegisPulse Crash Investigator — Dossiê de Eventos, Telas Azuis (BSOD), Confiabilidade & Causa-Raiz</h2>
            <span class="badge {sev_badge}">SEVERIDADE DO INCIDENTE: {html.escape(sev_lvl)}</span>
        </div>
        <div class="grid" style="margin-bottom:10px;">
            <div>
                <div class="kv"><span>Período Investigado:</span> <strong>Últimas {crash_data.get('period_hours', 168)} horas ({crash_data.get('period_days', 7)} dias)</strong></div>
                <div class="kv"><span>Resumo Executivo (Fatos Observados):</span> <strong>{html.escape(str(summary.get('headline') or 'Sem falhas críticas registradas.'))}</strong></div>
                <div class="kv"><span>Eventos Críticos / Erros Analisados:</span> Críticos: <strong>{summary.get('critical_events_count', 0)}</strong> | Erros: <strong>{summary.get('error_events_count', 0)}</strong> | Avisos I/O: <strong>{summary.get('warning_events_count', 0)}</strong></div>
            </div>
            <div>
                <div class="kv"><span>Telas Azuis (BSOD / BugChecks) & Dumps:</span> Ocorrências: <strong>{bsod.get('bugcheck_count', 0)}</strong> | Minidumps Encontrados: <strong>{bsod.get('minidump_files_count', 0)}</strong></div>
                <div class="kv"><span>Histórico de Confiabilidade:</span> Falhas de Apps: <strong>{rel.get('app_failures_count', 0)}</strong> | Falhas de SO/Hardware: <strong>{rel.get('os_hardware_failures_count', 0)}</strong></div>
                <div class="kv"><span>Correlação Hardware & E/S (51/129/153/WHEA):</span> <strong>{html.escape(str(hw_io.get('primary_classification') or 'Operação Normal'))}</strong></div>
            </div>
        </div>

        <h3 style="font-size:13.5px;color:var(--accent);margin:10px 0 6px;">Hipóteses Técnicas Ordenadas por Plausibilidade (Fatos vs Inferências)</h3>
        <table>
            <thead>
                <tr><th>Hipótese & Categoria</th><th>Confiança / Plausibilidade</th><th>Evidências Favoráveis (Fatos) vs Contrárias</th><th>Justificativa Técnica</th></tr>
            </thead>
            <tbody>{hyp_rows}</tbody>
        </table>

        <h3 style="font-size:13.5px;color:var(--accent);margin:12px 0 6px;">Linha do Tempo Consolidada de Eventos Relevantes (Mensagem Original vs Interpretação)</h3>
        <table>
            <thead>
                <tr><th>Data / Horário</th><th>Origem & Event ID</th><th>Severidade</th><th>Descrição Original (Fato) & Interpretação Técnica do Sistema</th></tr>
            </thead>
            <tbody>{tl_rows}</tbody>
        </table>

        <h3 style="font-size:13.5px;color:var(--accent);margin:12px 0 6px;">Plano de Ação N3 Ordenado por Menor Risco (Execução Manual sob Autorização)</h3>
        <table>
            <thead>
                <tr><th>Ação / Objetivo</th><th>Procedimento / Comando Recomendado</th><th>Risco</th><th>Exige Backup?</th><th>Impacto Esperado</th></tr>
            </thead>
            <tbody>{plan_rows}</tbody>
        </table>

        <div class="kv" style="margin-top:10px;"><span>Limitações da Coleta e Observações de Escopo:</span></div>
        <ul class="ai-ul">{lim_html}</ul>
    </div>
    """


def _build_fallback_deterministic_summary(snapshot: dict[str, Any], hs: dict[str, Any], crash_data: dict[str, Any]) -> str:
    """
    Quando a análise por IA externa está indisponível ou não foi executada,
    gera um resumo técnico determinístico baseado exclusivamente nas evidências
    reais coletadas, explicitando essa condição.
    """
    hw = snapshot.get("hardware") or {}
    st = snapshot.get("storage_suite") or {}
    score = hs.get("overall_score", "N/D")
    cls_name = hs.get("classification", "N/D")
    devs = st.get("devices") or []
    crash_sum = (crash_data.get("incident_summary") or {}).get("headline") or "Nenhuma investigação de falha crítica anexada."

    lines = [
        "### Parecer Técnico Baseado em Regras Determinísticas Locais (Sem Uso de IA Externa)",
        "- **Nota de Transparência:** Este parecer foi compilado automaticamente pelo motor determinístico local do AegisPulse com base exclusiva nas evidências físicas e lógicas coletadas (o serviço de IA em nuvem não foi acionado ou estava indisponível no momento da geração).",
        f"- **Fato Observado (Health Score):** Pontuação geral calculada em **{score}/100 ({cls_name})**.",
        f"- **Fato Observado (Hardware):** Estação `{hw.get('hostname', 'Local')}` ({hw.get('manufacturer', 'N/D')} {hw.get('model', 'N/D')}) com {hw.get('total_ram_gb', 'N/D')} GB de RAM.",
        f"- **Fato Observado (Armazenamento):** {len(devs)} dispositivo(s) físico(s) inspecionado(s) — Risco global: **{st.get('highest_risk_level', 'BAIXO')}**.",
        f"- **Fato Observado (Estabilidade / Crash Investigator):** {crash_sum}",
    ]
    for f in (hs.get("prioritized_findings") or [])[:5]:
        if isinstance(f, dict):
            lines.append(
                f"- **[{f.get('severity', 'INFO')}] {f.get('title')} ({f.get('affected_component')}):** "
                f"Evidência: `{f.get('technical_evidence')}` — Recomendação: {f.get('recommendation')}"
            )
    return "\n".join(lines)


def generate_html_report(
    snapshot: dict[str, Any] | None,
    base_dir: Path,
    ai_analysis: str = "",
    action_logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Gera, valida e entrega o Laudo Técnico Executivo completo tanto em formato
    HTML5 (.html) quanto em formato PDF binário válido (.pdf).
    """
    if not isinstance(snapshot, dict):
        snapshot = {}

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    file_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]

    hw = snapshot.get("hardware") if isinstance(snapshot.get("hardware"), dict) else {}
    temps = hw.get("temperatures") if isinstance(hw.get("temperatures"), dict) else {}
    os_info = snapshot.get("os") if isinstance(snapshot.get("os"), dict) else {}
    drv = snapshot.get("drivers_bios") if isinstance(snapshot.get("drivers_bios"), dict) else {}
    bios = drv.get("bios") if isinstance(drv.get("bios"), dict) else {}
    sw = snapshot.get("software") if isinstance(snapshot.get("software"), dict) else {}
    gaming = snapshot.get("gaming") if isinstance(snapshot.get("gaming"), dict) else {}
    gp = gaming.get("gamer_profile") if isinstance(gaming.get("gamer_profile"), dict) else {}
    compat = snapshot.get("compatibility") if isinstance(snapshot.get("compatibility"), dict) else {}
    st_suite = snapshot.get("storage_suite") if isinstance(snapshot.get("storage_suite"), dict) else {}
    hs_data = snapshot.get("health_score") if isinstance(snapshot.get("health_score"), dict) else {}
    crash_data = snapshot.get("crash_investigation") if isinstance(snapshot.get("crash_investigation"), dict) else {}
    logs = action_logs if isinstance(action_logs, list) else (snapshot.get("action_logs") if isinstance(snapshot.get("action_logs"), list) else [])

    # Se o Health Score não estiver no snapshot, tenta calculá-lo de forma segura sem persistir
    if not hs_data and (hw or st_suite or os_info):
        try:
            from backend.services.health_score import compute_health_score
            hs_data = compute_health_score(snapshot, base_dir=base_dir, persist=False)
        except Exception:
            hs_data = {}

    raw_hostname = str(hw.get("hostname") or "Computador")
    safe_file_host = _sanitize_filename_token(raw_hostname, default="Computador")
    hostname = html.escape(raw_hostname)
    manuf = html.escape(str(hw.get("manufacturer") or "N/D"))
    model = html.escape(str(hw.get("model") or "N/D"))
    serial = html.escape(_mask_sensitive_identifier(str(hw.get("serial_service_tag") or "N/D")))

    os_name = html.escape(str(os_info.get("os_name") or "N/D"))
    os_ver = html.escape(str(os_info.get("display_version") or "N/D"))
    os_build = html.escape(str(os_info.get("full_build") or "N/D"))

    health_score_panel_html = _build_health_score_html(hs_data)
    crash_investigator_panel_html = _build_crash_investigator_html(crash_data)

    # Seção Forense de Discos, SMART, Vida Útil e Riscos
    storage_cards_html = ""
    pdf_storage_lines: list[str] = []
    for dev in (st_suite.get("devices") or []):
        if not isinstance(dev, dict):
            continue
        sm = dev.get("smart_summary") if isinstance(dev.get("smart_summary"), dict) else {}
        lf = dev.get("lifespan") if isinstance(dev.get("lifespan"), dict) else {}
        rk = dev.get("risk_assessment") if isinstance(dev.get("risk_assessment"), dict) else {}
        cap = dev.get("capacity") if isinstance(dev.get("capacity"), dict) else {}
        r_lvl = str(rk.get("risk_level") or "BAIXO")
        r_badge = "err" if r_lvl in ("ALTO", "CRÍTICO") else ("warn" if r_lvl == "MODERADO" else "ok")

        pdf_storage_lines.append(
            f"FATO: Disco #{dev.get('disk_number')} - {dev.get('brand')} {dev.get('model')} "
            f"(Serie: {dev.get('serial_number')}) | Capacidade: {cap.get('formatted', 'N/D')} | "
            f"Unidades: {', '.join(dev.get('drive_letters') or ['Sem Letra'])} | Risco: {r_lvl} ({rk.get('health_score', 100)}/100)"
        )

        smart_rows = ""
        for a in (dev.get("smart_attributes") or [])[:14]:
            if not isinstance(a, dict):
                continue
            s_cls = "err" if a.get("severity") == "critical" else ("warn" if a.get("severity") == "warning" else "ok")
            interp_val = a.get("interpreted_value") if a.get("interpreted_value") is not None else a.get("interpreted", "")
            smart_rows += f"""
            <tr>
                <td><code>{html.escape(str(a.get('id')))}</code></td>
                <td><strong>{html.escape(str(a.get('name')))}</strong></td>
                <td>{a.get('current')} / {a.get('worst')} (Lim: {a.get('threshold')})</td>
                <td><code>{html.escape(str(a.get('raw_hex')))}</code> ({a.get('raw_int')})</td>
                <td><strong>{html.escape(str(interp_val))}</strong></td>
                <td><span class="badge {s_cls}">{html.escape(str(a.get('severity', 'ok')).upper())}</span></td>
            </tr>
            """
        if not smart_rows:
            smart_rows = '<tr><td colspan="6">Atributos SMART detalhados não expostos pela controladora/ponte USB deste dispositivo.</td></tr>'

        faults_html = ""
        for fd in (dev.get("fault_diagnostics") or []):
            if not isinstance(fd, dict):
                continue
            faults_html += f"""
            <li>
                <strong>[{html.escape(str(fd.get('category')))}] {html.escape(str(fd.get('title')))}:</strong>
                {html.escape(str(fd.get('explanation')))}
                <br><em>Recomendação: {html.escape(str(fd.get('recommendation')))}</em>
            </li>
            """
            pdf_storage_lines.append(f"  - [{fd.get('category')}] {fd.get('title')}: {fd.get('recommendation')}")

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
                    <div class="kv"><span>Capacidade Física (Decimal vs Binária):</span> <strong>{html.escape(str(cap.get('formatted')))}</strong> (<code>{int(cap.get('bytes') or 0):,} bytes</code>)</div>
                    <div class="kv"><span>Tabela de Partições & Unidades:</span> <strong>{html.escape(str(dev.get('partition_style')))}</strong> ({', '.join(dev.get('drive_letters') or ['Sem Letra'])}) | Não Alocado: {(dev.get('unallocated_capacity') or {}).get('formatted', '0 B')}</div>
                </div>
                <div>
                    <div class="kv"><span>Temperatura Atual do Disco:</span> <strong>{sm.get('temperature_c') if sm.get('temperature_c') is not None else 'N/D'} °C</strong></div>
                    <div class="kv"><span>Tempo Acumulado Ligado (POH):</span> <strong>{html.escape(str(lf.get('power_on_formatted', 'N/D')))}</strong> | Ciclos: {sm.get('power_cycles') or 'N/D'}</div>
                    <div class="kv"><span>Vida Útil (Fabricante vs Estimada TBW):</span> <strong>{html.escape(str(lf.get('manufacturer_reported_str', 'N/D')))}</strong></div>
                    <div class="kv"><span>Total Lido / Gravado (TBW):</span> Lido: {html.escape(str(lf.get('total_reads_formatted', 'N/D')))} | Gravado: <strong>{html.escape(str(lf.get('total_writes_formatted', 'N/D')))}</strong></div>
                </div>
            </div>
            <div class="kv"><span>Diagnóstico Especializado de Falhas & Causa-Raiz (Interpretação do Sistema):</span></div>
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
    for v in (hw.get("volumes") or []):
        if not isinstance(v, dict):
            continue
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
                    <div class="bar-fill" style="background-color:{bar_color} !important;width:{min(100.0, pct)}%;"></div>
                </div>
                <strong>{pct}%</strong>
            </td>
        </tr>
        """

    ded_gpu = gp.get("dedicated_gpu") if isinstance(gp.get("dedicated_gpu"), dict) else {}
    int_gpu = gp.get("integrated_gpu") if isinstance(gp.get("integrated_gpu"), dict) else {}
    cpu_g = gp.get("cpu_gamer") if isinstance(gp.get("cpu_gamer"), dict) else {}
    ram_g = gp.get("ram_gamer") if isinstance(gp.get("ram_gamer"), dict) else {}
    techs_html = ", ".join(html.escape(str(t)) for t in (gp.get("supported_technologies") or [])) or "DirectX 12"
    bottlenecks_html = "".join(f"<li>{html.escape(str(b))}</li>" for b in (gp.get("bottlenecks_and_alerts") or []))

    outdated_rows = ""
    for s in (sw.get("outdated_software") or []):
        if not isinstance(s, dict):
            continue
        outdated_rows += f"""
        <tr>
            <td><strong>{html.escape(str(s.get('name')))}</strong></td>
            <td><code>{html.escape(str(s.get('id')))}</code></td>
            <td><span class="badge warn">{html.escape(str(s.get('current_version')))}</span></td>
            <td><span class="badge ok">{html.escape(str(s.get('available_version')))}</span></td>
        </tr>
        """
    if not outdated_rows:
        outdated_rows = '<tr><td colspan="4">Todos os softwares monitorados pelo Winget estão atualizados ou sem pendências detectadas.</td></tr>'

    key_classes = {"DISPLAY", "NET", "MEDIA", "HDC", "SCSIADAPTER", "FIRMWARE"}
    filtered_drivers = []
    seen_names = set()
    for d in (drv.get("drivers") or []):
        if not isinstance(d, dict):
            continue
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
        if not isinstance(lg, dict):
            continue
        log_rows += f"""
        <tr>
            <td><code>{html.escape(str(lg.get('timestamp', now_str)))}</code></td>
            <td><strong>{html.escape(str(lg.get('action', 'Operação')))}</strong></td>
            <td>{html.escape(str(lg.get('summary', '')))}</td>
        </tr>
        """
    if not log_rows:
        log_rows = '<tr><td colspan="3">Coleta diagnóstica concluída.</td></tr>'

    # Distinção explícita entre Recomendações Geradas por IA vs Análise Determinística do Sistema
    ai_clean = str(ai_analysis or snapshot.get("last_ai_analysis") or "").strip()
    ai_was_used = bool(ai_clean and not ai_clean.startswith("[ERRO]") and not ai_clean.startswith("[AVISO]"))
    if ai_was_used:
        formatted_ai = _markdown_to_html(ai_clean)
        ai_block = f"""
        <div class="card ai-card" style="margin-top: 18px; border-left: 4px solid #0284c7;">
            <h2>✨ Resumo e Recomendações Assistidas por IA (Identificado como Conteúdo Gerado por IA)</h2>
            <p class="kv" style="margin-bottom:8px;"><span>Aviso de Escopo:</span> As recomendações abaixo foram sintetizadas pelo motor de Inteligência Artificial a partir das evidências coletadas. Fatos observados e métricas determinísticas encontram-se nas tabelas técnicas acima.</p>
            <div class="ai-content">{formatted_ai}</div>
        </div>
        """
        pdf_ai_text = ai_clean
    else:
        det_summary = _build_fallback_deterministic_summary(snapshot, hs_data, crash_data)
        formatted_det = _markdown_to_html(det_summary)
        ai_block = f"""
        <div class="card ai-card" style="margin-top: 18px; border-left: 4px solid #10b981;">
            <h2>📋 Parecer Técnico Baseado em Regras Determinísticas (Serviço de IA Não Acionado / Indisponível)</h2>
            <div class="ai-content">{formatted_det}</div>
        </div>
        """
        pdf_ai_text = det_summary

    cpus_list = hw.get("cpus") if isinstance(hw.get("cpus"), list) and hw.get("cpus") else [{}]
    gpus_list = hw.get("gpus") if isinstance(hw.get("gpus"), list) and hw.get("gpus") else [{}]
    cpu_name = html.escape(str((cpus_list[0] if isinstance(cpus_list[0], dict) else {}).get("name", "N/D")))
    gpu_name = html.escape(str(ded_gpu.get("name") or (gpus_list[0] if isinstance(gpus_list[0], dict) else {}).get("name", "N/D")))
    bios_badge = "warn" if bios.get("needs_review") else "ok"
    mb_info = hw.get("motherboard") if isinstance(hw.get("motherboard"), dict) else {}

    pdf_filename = f"Laudo_AegisPulse_{safe_file_host}_{file_stamp}.pdf"
    report_filename = f"Laudo_AegisPulse_{safe_file_host}_{file_stamp}.html"

    html_doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Laudo Técnico AegisPulse v5.5 — {hostname}</title>
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
            flex-wrap: wrap;
            gap: 12px;
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
            vertical-align: top;
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
            text-decoration: none;
            display: inline-block;
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
            <h1>AEGISPULSE IT TOOLKIT v5.5 — DIAGNÓSTICO • AUTOMAÇÃO • INTELIGÊNCIA</h1>
            <p style="color:#0284c7;font-weight:600;margin-bottom:4px;">Tecnologia sob controle. Suporte com inteligência.</p>
            <p>Responsável Técnico / Autor: <strong>Adriano Barboza</strong> | WhatsApp: <strong>+55 61 98515-8434</strong> | adriano9200@gmail.com</p>
            <p>Data/Hora de Emissão: {now_str} | Hostname: <strong>{hostname}</strong></p>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <a class="btn-print" href="/reports/{pdf_filename}?download=1" download="{pdf_filename}">⬇️ Baixar PDF Nativo</a>
            <button class="btn-print" onclick="window.print()">🖨️ Imprimir / Salvar PDF</button>
        </div>
    </div>

    {health_score_panel_html}

    {crash_investigator_panel_html}

    <div class="grid">
        <div class="card">
            <h2>Identificação Técnica do Equipamento (Fatos Coletados)</h2>
            <div class="kv"><span>Fabricante:</span> <strong>{manuf}</strong></div>
            <div class="kv"><span>Modelo:</span> <strong>{model}</strong></div>
            <div class="kv"><span>Serial / Service Tag:</span> <code>{serial}</code></div>
            <div class="kv"><span>Placa-Mãe:</span> {html.escape(str(mb_info.get('manufacturer', 'N/D')))} {html.escape(str(mb_info.get('product', 'N/D')))}</div>
        </div>

        <div class="card">
            <h2>Sistema Operacional</h2>
            <div class="kv"><span>Edição:</span> <strong>{os_name}</strong></div>
            <div class="kv"><span>Versão:</span> <strong>{os_ver}</strong></div>
            <div class="kv"><span>Build / UBR:</span> <code>{os_build}</code></div>
            <div class="kv"><span>Arquitetura / Uptime:</span> {html.escape(str(os_info.get('architecture', 'N/D')))} ({os_info.get('uptime_hours', 0)} h ligado)</div>
        </div>

        <div class="card">
            <h2>Hardware & Monitoramento Térmico (°C)</h2>
            <div class="kv"><span>Processador:</span> <strong>{cpu_name}</strong></div>
            <div class="kv"><span>Temperatura Atual CPU:</span> <strong>{temps.get('cpu_temp_c', 45)}°C</strong> — <span class="badge ok">{html.escape(str(temps.get('cpu_temp_status', 'Ideal')))}</span></div>
            <div class="kv"><span>GPU Principal & Temp:</span> <strong>{gpu_name} ({temps.get('gpu_temp_c', 42)}°C)</strong></div>
            <div class="kv"><span>Memória RAM Total:</span> <strong>{hw.get('total_ram_gb', 'N/D')} GB</strong> ({len(hw.get('ram_modules') or [])} módulo(s))</div>
        </div>

        <div class="card">
            <h2>Firmware BIOS / UEFI</h2>
            <div class="kv"><span>Fabricante BIOS:</span> {html.escape(str(bios.get('manufacturer', 'N/D')))}</div>
            <div class="kv"><span>Versão SMBIOS:</span> <code>{html.escape(str(bios.get('smbios_version', 'N/D')))}</code></div>
            <div class="kv"><span>Data de Lançamento:</span> {html.escape(str(bios.get('release_date', 'N/D')))} ({bios.get('age_months', 0)} meses)</div>
            <div class="kv"><span>Status:</span> <span class="badge {bios_badge}">{html.escape(str(bios.get('status_label', 'OK')))}</span></div>
        </div>
    </div>

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
        <strong>AegisPulse IT Toolkit v5.5.0</strong> — Diagnóstico • Automação • Inteligência | <em>Tecnologia sob controle. Suporte com inteligência.</em><br>
        Desenvolvido por <strong>Adriano Barboza</strong> • WhatsApp Comercial: <strong>+55 61 98515-8434</strong> • adriano9200@gmail.com
    </div>
</div>
</body>
</html>"""

    # Constrói seções para o PDF binário nativo (%PDF-1.4)
    pdf_sections: list[tuple[str, list[str]]] = [
        (
            "1. Identificacao do Equipamento e Sistema Operacional (Fatos Coletados)",
            [
                f"FATO: Hostname: {raw_hostname} | Fabricante/Modelo: {hw.get('manufacturer', 'N/D')} {hw.get('model', 'N/D')} | Serial: {hw.get('serial_service_tag', 'N/D')}",
                f"FATO: Sistema Operacional: {os_info.get('os_name', 'N/D')} ({os_info.get('display_version', 'N/D')}) - Build {os_info.get('full_build', 'N/D')}",
                f"FATO: Processador: {cpu_name} ({temps.get('cpu_temp_c', 45)} C) | GPU: {gpu_name} ({temps.get('gpu_temp_c', 42)} C) | RAM: {hw.get('total_ram_gb', 'N/D')} GB",
            ],
        ),
        (
            "2. AegisPulse Health Score (Avaliacao Deterministica)",
            [
                f"FATO: Pontuacao Geral: {hs_data.get('overall_score', 'N/D')}/100 ({hs_data.get('classification', 'N/D')}) | Cobertura: {(hs_data.get('coverage') or {}).get('label', 'N/D')}",
                *(
                    [f"ALERTA: [{f.get('severity')}] {f.get('title')} ({f.get('affected_component')}) -> {f.get('recommendation')}" for f in (hs_data.get("prioritized_findings") or [])[:8] if isinstance(f, dict)]
                    or ["Nenhum achado critico de Health Score."]
                ),
            ],
        ),
        (
            "3. Dossie Forense de Armazenamento & SMART",
            pdf_storage_lines or ["Nenhum dispositivo de armazenamento reportado no snapshot."],
        ),
    ]

    if crash_data and crash_data.get("collected_at"):
        c_sum = crash_data.get("incident_summary") or {}
        c_bsod = crash_data.get("bsod_analysis") or {}
        c_hyps = crash_data.get("hypotheses") or []
        c_plan = crash_data.get("action_plan") or []
        pdf_sections.append((
            "4. AegisPulse Crash Investigator (Eventos, BSOD, Hipoteses e Plano N3)",
            [
                f"FATO: Periodo investigado: Ultimas {crash_data.get('period_hours', 168)}h | Severidade: {c_sum.get('overall_severity', 'NORMAL')}",
                f"FATO: Resumo: {c_sum.get('headline', 'N/D')}",
                f"FATO: BSODs/BugChecks: {c_bsod.get('bugcheck_count', 0)} | Minidumps: {c_bsod.get('minidump_files_count', 0)}",
                *[
                    f"HIPOTESE: #{h.get('rank', 1)} {h.get('title')} (Confianca: {h.get('confidence_level')} - {h.get('plausibility_score')}%) | Evidencias: {'; '.join(h.get('favorable_evidence') or [])}"
                    for h in c_hyps[:6] if isinstance(h, dict)
                ],
                *[
                    f"ACAO: [{a.get('risk_level')}] {a.get('title')} -> {a.get('suggested_command_or_procedure')} (Backup obrigatorio: {'Sim' if a.get('requires_backup') else 'Nao'})"
                    for a in c_plan[:6] if isinstance(a, dict)
                ],
            ],
        ))

    pdf_sections.append((
        "5. Parecer Analitico (Sistema Deterministico / Assistido por IA)",
        [ln for ln in pdf_ai_text.splitlines() if ln.strip()][:40],
    ))

    reports_dir = Path(base_dir) / "reports"
    logs_dir = Path(base_dir) / "logs"
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError as dir_err:
        return {
            "success": False,
            "error_stage": "directory_creation_or_permission",
            "message": f"Falha de permissão ao criar diretório de relatórios ({reports_dir}): {dir_err}",
        }

    report_path = reports_dir / report_filename
    pdf_path = reports_dir / pdf_filename
    log_copy_path = logs_dir / f"Log_Sessao_{safe_file_host}_{file_stamp}.html"

    # 1. Escrita e validação do HTML
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_doc)
        with open(log_copy_path, "w", encoding="utf-8") as f:
            f.write(html_doc)
    except OSError as html_err:
        return {
            "success": False,
            "error_stage": "html_write_error",
            "message": f"Falha ao gravar arquivo HTML em {report_path}: {html_err}",
        }

    if not report_path.exists() or report_path.stat().st_size < 200:
        return {
            "success": False,
            "error_stage": "html_validation_error",
            "message": "O arquivo HTML gerado está vazio ou incompleto.",
        }

    # 2. Geração e validação do PDF binário (%PDF-1.4)
    pdf_generated = False
    pdf_error_msg = ""
    try:
        pdf_bytes = build_valid_pdf_bytes(
            title=f"Emitido em {now_str} | Equipamento: {raw_hostname} ({hw.get('manufacturer', 'N/D')} {hw.get('model', 'N/D')})",
            sections=pdf_sections,
        )
        with open(pdf_path, "wb") as pf:
            pf.write(pdf_bytes)
        if pdf_path.exists() and pdf_path.stat().st_size > 200:
            with open(pdf_path, "rb") as pf_chk:
                hdr = pf_chk.read(8)
            if hdr.startswith(b"%PDF-"):
                pdf_generated = True
            else:
                pdf_error_msg = "Cabeçalho %PDF- inválido no arquivo gerado."
        else:
            pdf_error_msg = "Arquivo PDF gerado com tamanho insuficiente."
    except Exception as pdf_exc:
        pdf_error_msg = str(pdf_exc)

    html_size = report_path.stat().st_size
    pdf_size = pdf_path.stat().st_size if pdf_generated and pdf_path.exists() else 0

    return {
        "success": True,
        "html_generated": True,
        "pdf_generated": pdf_generated,
        "pdf_error": pdf_error_msg,
        "ai_was_used": ai_was_used,
        "filename": report_filename,
        "pdf_filename": pdf_filename if pdf_generated else "",
        "html_size_bytes": html_size,
        "pdf_size_bytes": pdf_size,
        "report_path": str(report_path),
        "pdf_path": str(pdf_path) if pdf_generated else "",
        "log_path": str(log_copy_path),
        "url": f"/reports/{report_filename}",
        "pdf_url": f"/reports/{pdf_filename}" if pdf_generated else "",
        "download_html_url": f"/reports/{report_filename}?download=1",
        "download_pdf_url": f"/reports/{pdf_filename}?download=1" if pdf_generated else "",
        "message": (
            f"Laudo Técnico HTML ({html_size:,} B) e PDF ({pdf_size:,} B) gerados e validados com sucesso!"
            if pdf_generated
            else f"Laudo HTML gerado ({html_size:,} B), mas houve aviso no PDF: {pdf_error_msg}"
        ),
    }
