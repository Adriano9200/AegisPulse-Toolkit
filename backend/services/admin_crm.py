#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: backend/services/admin_crm.py (CRM SQLite, Preços Justos e Relatório Cliente)
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  3.0.0
================================================================================
Descrição:
Módulo exclusivo do Administrador (Adriano Barboza):
1. Banco de dados SQLite local (data/aegispulse_admin.db) para cadastrar,
   identificar e consultar clientes com Nome, Telefone, WhatsApp, Equipamento,
   Serviços realizados e Valor cobrado;
2. Catálogo de Preços Médios Justos de Mercado (Sem Abuso — Referência 2026)
   para serviços de Suporte Técnico, Redes, Formatação, Upgrades e PC Gamer;
3. Gerador de Relatório e Orçamento Comercial Exclusivo para Enviar ao Cliente
   (em HTML/PDF pronto para impressão e link direto para o WhatsApp do cliente).
"""

import html
import json
import sqlite3
import urllib.parse
from datetime import datetime
from pathlib import Path

FAIR_PRICING_CATALOG = [
    {
        "id": "diag_laudo",
        "service": "Diagnóstico Técnico Completo + Laudo AegisPulse",
        "category": "Diagnóstico",
        "min_brl": 60.0,
        "fair_brl": 80.0,
        "max_brl": 120.0,
        "description": "Inspeção completa de hardware, saúde SMART dos discos, temperaturas, BIOS, drivers e relatório técnico (abatido caso aprove o serviço).",
    },
    {
        "id": "otimizacao_debloat",
        "service": "Otimização de Sistema, Limpeza Segura e Remoção de Bloatware",
        "category": "Manutenção de Software",
        "min_brl": 90.0,
        "fair_brl": 120.0,
        "max_brl": 160.0,
        "description": "Limpeza de temporários, remoção de apps pré-instalados inúteis (Debloat), atualização de programas via Winget e ajuste de inicialização.",
    },
    {
        "id": "pc_gamer_pack",
        "service": "Otimização Especializada PC Gamer (Drivers, Runtimes DLLs, Shaders e Energia)",
        "category": "PC Gamer",
        "min_brl": 120.0,
        "fair_brl": 150.0,
        "max_brl": 200.0,
        "description": "Reparo de DLLs 32/64-bit (Visual C++ e DirectX), limpeza de cache de shaders da GPU, ativação de Desempenho Máximo e ajuste de DNS Gamer.",
    },
    {
        "id": "formatacao_backup",
        "service": "Formatação Profissional Windows 10/11 com Backup + Kit Pós-Formatação",
        "category": "Sistema Operacional",
        "min_brl": 150.0,
        "fair_brl": 180.0,
        "max_brl": 250.0,
        "description": "Backup seguro de arquivos do cliente, instalação limpa do Windows, drivers oficiais do fabricante e pacote essencial de aplicativos.",
    },
    {
        "id": "limpeza_fisica_pasta",
        "service": "Higienização Física Interna + Troca de Pasta Térmica de Alta Condutividade",
        "category": "Hardware & Térmica",
        "min_brl": 130.0,
        "fair_brl": 160.0,
        "max_brl": 220.0,
        "description": "Desmontagem cuidadosa, limpeza de coolers/dissipadores e aplicação de pasta térmica de alta performance em CPU/GPU.",
    },
    {
        "id": "upgrade_ssd_ram",
        "service": "Instalação Física de Upgrade (SSD NVMe/SATA ou Memória RAM) + Clonagem",
        "category": "Upgrade de Hardware",
        "min_brl": 110.0,
        "fair_brl": 140.0,
        "max_brl": 190.0,
        "description": "Instalação física do novo componente (peça cobrada à parte), configuração de Dual-Channel/BIOS e clonagem ou ajuste de partições.",
    },
    {
        "id": "remocao_malware",
        "service": "Remoção Avançada de Vírus/Malware e Blindagem de Segurança (Defender/DNS)",
        "category": "Segurança",
        "min_brl": 130.0,
        "fair_brl": 160.0,
        "max_brl": 220.0,
        "description": "Varredura profunda contra malwares/adwares, revisão de extensões de navegador, ativação de proteção em tempo real e DNS anti-phishing.",
    },
    {
        "id": "reparo_rede_wifi",
        "service": "Diagnóstico e Otimização de Rede Local, Wi-Fi e DNS de Baixa Latência",
        "category": "Redes & Internet",
        "min_brl": 100.0,
        "fair_brl": 130.0,
        "max_brl": 180.0,
        "description": "Reset de pilha TCP/IP e Winsock, atualização de driver de rede, configuração de DNS rápido (Cloudflare/Google) e testes de estabilidade.",
    },
    {
        "id": "bios_update",
        "service": "Atualização Segura de BIOS / UEFI e Firmware Oficial",
        "category": "Firmware",
        "min_brl": 110.0,
        "fair_brl": 140.0,
        "max_brl": 190.0,
        "description": "Verificação de compatibilidade, atualização assistida para a versão oficial do fabricante e configuração de TPM 2.0 / XMP.",
    },
]


def _get_db_path(base_dir: Path) -> Path:
    data_dir = base_dir / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "aegispulse_admin.db"


def init_crm_database(base_dir: Path) -> None:
    """Inicializa a tabela SQLite de clientes e orçamentos."""
    db_path = _get_db_path(base_dir)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                phone TEXT,
                whatsapp TEXT NOT NULL,
                email TEXT,
                equipment_model TEXT,
                service_tag TEXT,
                services_json TEXT,
                discount_brl REAL DEFAULT 0,
                total_brl REAL DEFAULT 0,
                notes TEXT,
                report_filename TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def list_crm_clients(base_dir: Path, search_query: str = "") -> list[dict]:
    """Lista os clientes cadastrados no SQLite (com filtro opcional por nome ou WhatsApp)."""
    init_crm_database(base_dir)
    db_path = _get_db_path(base_dir)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if search_query.strip():
            q = f"%{search_query.strip()}%"
            rows = conn.execute(
                "SELECT * FROM clients WHERE client_name LIKE ? OR whatsapp LIKE ? OR phone LIKE ? OR equipment_model LIKE ? ORDER BY id DESC",
                (q, q, q, q),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM clients ORDER BY id DESC LIMIT 100").fetchall()

        result = []
        for r in rows:
            d = dict(r)
            try:
                d["services"] = json.loads(d.get("services_json") or "[]")
            except Exception:
                d["services"] = []
            result.append(d)
        return result


def delete_crm_client(base_dir: Path, client_id: int) -> bool:
    init_crm_database(base_dir)
    db_path = _get_db_path(base_dir)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM clients WHERE id = ?", (int(client_id),))
        conn.commit()
    return True


def save_client_and_generate_report(
    base_dir: Path,
    snapshot: dict,
    client_data: dict,
) -> dict:
    """
    Salva o cliente no banco SQLite e gera um Relatório & Orçamento Exclusivo
    em HTML/PDF pronto para enviar ao cliente (com link direto de WhatsApp).
    """
    init_crm_database(base_dir)
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    file_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    c_name = (client_data.get("client_name") or "Cliente").strip()
    c_phone = (client_data.get("phone") or "").strip()
    c_whats = (client_data.get("whatsapp") or c_phone or "").strip()
    c_email = (client_data.get("email") or "").strip()
    c_notes = (client_data.get("notes") or "Diagnóstico concluído com sucesso. Equipamento testado e auditado pelo AegisPulse IT Toolkit.").strip()
    selected_ids = set(client_data.get("selected_service_ids") or [])
    custom_discount = float(client_data.get("discount_brl") or 0.0)

    hw = snapshot.get("hardware", {})
    os_info = snapshot.get("os", {})
    temps = hw.get("temperatures", {})

    eq_model = f"{hw.get('manufacturer', 'PC')} {hw.get('model', '')}".strip()
    eq_serial = str(hw.get("serial_service_tag") or "N/D")
    cpu_name = hw.get("cpus", [{}])[0].get("name", "N/D") if hw.get("cpus") else "N/D"
    gpu_name = hw.get("gpus", [{}])[0].get("name", "N/D") if hw.get("gpus") else "N/D"

    selected_services = []
    subtotal = 0.0
    for item in FAIR_PRICING_CATALOG:
        if item["id"] in selected_ids:
            selected_services.append(item)
            subtotal += float(item["fair_brl"])

    if not selected_services:
        selected_services.append(FAIR_PRICING_CATALOG[0])
        subtotal = float(FAIR_PRICING_CATALOG[0]["fair_brl"])

    total_brl = max(0.0, round(subtotal - custom_discount, 2))

    # Gera link direto para mandar o orçamento no WhatsApp do cliente
    digits_whats = "".join(ch for ch in c_whats if ch.isdigit())
    if digits_whats and not digits_whats.startswith("55") and len(digits_whats) in (10, 11):
        digits_whats = "55" + digits_whats

    services_text_wa = "\n".join(f"✅ {s['service']}: R$ {s['fair_brl']:.2f}" for s in selected_services)
    wa_msg = (
        f"Olá, *{c_name}*! Tudo bem?\n"
        f"Aqui é o *Adriano Barboza* (AegisPulse IT Toolkit).\n\n"
        f"Concluí o diagnóstico do seu equipamento *{eq_model}*:\n"
        f"• Processador: {cpu_name} ({temps.get('cpu_temp_c', 45)}°C)\n"
        f"• Memória RAM: {hw.get('total_ram_gb', 0)} GB\n"
        f"• Placa de Vídeo: {gpu_name} ({temps.get('gpu_temp_c', 42)}°C)\n\n"
        f"*Serviços Recomendados (Tabela Justa):*\n{services_text_wa}\n"
        f"*Valor Total do Orçamento:* R$ {total_brl:.2f}\n\n"
        f"*Observações Técnicas:* {c_notes}\n\n"
        f"Qualquer dúvida estou à disposição neste WhatsApp (+55 61 98515-8434)!"
    )
    client_wa_url = f"https://wa.me/{digits_whats}?text={urllib.parse.quote(wa_msg)}" if digits_whats else ""

    # Gera Relatório HTML/PDF Exclusivo do Cliente
    srv_rows = ""
    for s in selected_services:
        srv_rows += f"""
        <tr>
            <td><strong>{html.escape(s['service'])}</strong><br><small style="color:#64748b;">{html.escape(s['description'])}</small></td>
            <td>{html.escape(s['category'])}</td>
            <td style="text-align:right;font-weight:700;">R$ {s['fair_brl']:.2f}</td>
        </tr>
        """

    safe_cname = "".join(c for c in c_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "Cliente"
    report_filename = f"Proposta_Cliente_{safe_cname}_{file_stamp}.html"
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / report_filename

    html_doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Relatório e Orçamento do Cliente — {html.escape(c_name)}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #f8fafc; color: #0f172a; padding: 28px; line-height: 1.5; }}
        .page {{ max-width: 920px; margin: 0 auto; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 12px; padding: 28px; box-shadow: 0 4px 16px rgba(15,23,42,0.06); }}
        .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #0284c7; padding-bottom: 16px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 21px; color: #0369a1; }}
        .header .sub {{ font-size: 13px; color: #475569; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 18px; }}
        .box {{ background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px; }}
        .box h3 {{ font-size: 13px; color: #0369a1; text-transform: uppercase; margin-bottom: 8px; }}
        .kv {{ font-size: 13.5px; margin-bottom: 4px; }}
        .kv span {{ color: #64748b; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13.5px; }}
        th, td {{ padding: 10px 12px; border-bottom: 1px solid #cbd5e1; text-align: left; }}
        th {{ background: #e2e8f0; color: #0f172a; font-weight: 700; }}
        .total-box {{ margin-top: 16px; text-align: right; background: #e0f2fe; border: 1px solid #7dd3fc; padding: 14px 18px; border-radius: 8px; }}
        .total-box strong {{ font-size: 19px; color: #0369a1; }}
        .btn-bar {{ display: flex; gap: 10px; margin-bottom: 16px; }}
        .btn {{ background: #0284c7; color: #fff; border: none; padding: 9px 16px; border-radius: 6px; font-weight: 600; cursor: pointer; text-decoration: none; font-size: 13px; }}
        .btn.wa {{ background: #10b981; }}
        .footer {{ margin-top: 24px; border-top: 1px solid #cbd5e1; padding-top: 12px; text-align: center; font-size: 12.5px; color: #475569; }}
        @media print {{ .btn-bar {{ display: none !important; }} body {{ background: #fff; padding: 0; }} .page {{ border: none; box-shadow: none; }} }}
    </style>
</head>
<body>
<div class="page">
    <div class="btn-bar">
        <button class="btn" onclick="window.print()">🖨️ Imprimir / Salvar em PDF para o Cliente</button>
        {f'<a class="btn wa" href="{client_wa_url}" target="_blank">💬 Enviar Orçamento Direto no WhatsApp de {html.escape(c_name)}</a>' if client_wa_url else ''}
    </div>

    <div class="header">
        <div>
            <h1>AEGISPULSE IT TOOLKIT — LAUDO & ORÇAMENTO DO CLIENTE</h1>
            <p class="sub"><strong>Diagnóstico • Automação • Inteligência</strong> — Tecnologia sob controle. Suporte com inteligência.</p>
        </div>
        <div style="text-align:right;font-size:13px;">
            <strong>Responsável Técnico: Adriano Barboza</strong><br>
            WhatsApp Oficial: <strong>+55 61 98515-8434</strong><br>
            E-mail: adriano9200@gmail.com<br>
            Emissão: {now_str}
        </div>
    </div>

    <div class="grid">
        <div class="box">
            <h3>👤 Dados do Cliente</h3>
            <div class="kv"><span>Cliente / Empresa:</span> <strong>{html.escape(c_name)}</strong></div>
            <div class="kv"><span>WhatsApp:</span> <strong>{html.escape(c_whats or 'Não informado')}</strong></div>
            <div class="kv"><span>Telefone Alternativo:</span> {html.escape(c_phone or '—')}</div>
            <div class="kv"><span>E-mail:</span> {html.escape(c_email or '—')}</div>
        </div>
        <div class="box">
            <h3>🖥️ Equipamento Inspecionado</h3>
            <div class="kv"><span>Marca / Modelo:</span> <strong>{html.escape(eq_model)}</strong> (Tag: <code>{html.escape(eq_serial)}</code>)</div>
            <div class="kv"><span>Processador & Temp:</span> {html.escape(cpu_name)} (<strong>{temps.get('cpu_temp_c', 45)}°C</strong>)</div>
            <div class="kv"><span>Memória RAM & Vídeo:</span> {hw.get('total_ram_gb', 0)} GB RAM | {html.escape(gpu_name)} (<strong>{temps.get('gpu_temp_c', 42)}°C</strong>)</div>
            <div class="kv"><span>Sistema Operacional:</span> {html.escape(str(os_info.get('os_name', 'Windows')))} ({html.escape(str(os_info.get('display_version', '')))})</div>
        </div>
    </div>

    <div class="box" style="margin-bottom:18px;">
        <h3>📋 Parecer Técnico e Recomendações para o Cliente</h3>
        <p style="font-size:13.5px;white-space:pre-wrap;">{html.escape(c_notes)}</p>
    </div>

    <h3 style="color:#0369a1;font-size:14px;text-transform:uppercase;">💰 Serviços Técnicos Orçados (Tabela Justa e Transparente)</h3>
    <table>
        <thead>
            <tr><th>Serviço Técnico & Escopo</th><th>Categoria</th><th style="text-align:right;">Valor (R$)</th></tr>
        </thead>
        <tbody>{srv_rows}</tbody>
    </table>

    <div class="total-box">
        <div>Subtotal: R$ {subtotal:.2f} | Desconto Aplicado: R$ {custom_discount:.2f}</div>
        <strong>VALOR TOTAL DO SERVIÇO: R$ {total_brl:.2f}</strong>
    </div>

    <div class="footer">
        Documento emitido via <strong>AegisPulse IT Toolkit v3.0.0</strong> • Desenvolvido por <strong>Adriano Barboza</strong> • WhatsApp: <strong>+55 61 98515-8434</strong>
    </div>
</div>
</body>
</html>"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    # Grava no SQLite
    db_path = _get_db_path(base_dir)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO clients (
                client_name, phone, whatsapp, email, equipment_model, service_tag,
                services_json, discount_brl, total_brl, notes, report_filename, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                c_name,
                c_phone,
                c_whats,
                c_email,
                eq_model,
                eq_serial,
                json.dumps(selected_services, ensure_ascii=False),
                custom_discount,
                total_brl,
                c_notes,
                report_filename,
                now_str,
            ),
        )
        conn.commit()
        new_id = cur.lastrowid

    return {
        "success": True,
        "client_id": new_id,
        "report_filename": report_filename,
        "report_url": f"/reports/{report_filename}",
        "whatsapp_url": client_wa_url,
        "total_brl": total_brl,
        "message": f"Cliente '{c_name}' salvo no banco SQLite e Orçamento Exclusivo gerado (R$ {total_brl:.2f})!",
    }
