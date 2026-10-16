#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: tests/test_phase1_reporter.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  5.5.0
================================================================================
Descrição:
Suíte de Validação Obrigatória da Fase 1 (Prioridade 0) — Geração e Entrega de
Laudos Técnicos HTML5 e PDF (11 Cenários Reais via Servidor HTTP em Thread).
"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.auth import login_admin
from backend.server import AegisPulseRequestHandler, SESSION_STATE
from backend.services.html_reporter import generate_html_report


class TestPhase1ReportGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.base_dir = Path(cls.temp_dir.name)
        SESSION_STATE["base_dir"] = cls.base_dir
        SESSION_STATE["last_snapshot"] = {
            "hardware": {
                "hostname": "DESKTOP-0BQKLQN",
                "manufacturer": "Dell Inc.",
                "model": "XPS 8930",
                "serial_service_tag": "DELLXPS8930TAG",
                "total_ram_gb": 32.0,
                "temperatures": {"cpu_temp_c": 46, "gpu_temp_c": 44, "cpu_temp_status": "Ideal"},
                "cpus": [{"name": "Intel Core i7-8700K"}],
                "gpus": [{"name": "NVIDIA GeForce GTX 1080", "vram_gb": 8}],
                "volumes": [{"drive": "C:", "label": "OS", "filesystem": "NTFS", "size_gb": 953.8, "free_gb": 204.6, "used_percent": 78.5}],
            },
            "os": {"os_name": "Microsoft Windows 11 Education", "display_version": "24H2", "full_build": "26100.9711", "architecture": "64-bit", "uptime_hours": 3.5},
            "storage_suite": {
                "highest_risk_level": "MODERADO",
                "devices": [
                    {
                        "disk_number": 2,
                        "brand": "SK hynix",
                        "model": "PC801 NVMe SK hynix 1TB",
                        "serial_number": "ACE4_2E00",
                        "media_category": "SSD NVMe",
                        "protocol": "NVMe",
                        "controller": "SK hynix Cepheus",
                        "firmware": "51003141",
                        "partition_style": "GPT",
                        "drive_letters": ["C:", "F:"],
                        "capacity": {"bytes": 1024209543168, "formatted": "1.024 TB (953.87 GiB)"},
                        "unallocated_capacity": {"formatted": "0 B"},
                        "smart_summary": {"temperature_c": 41, "power_cycles": 412},
                        "lifespan": {"power_on_formatted": "3420 h (142.5 dias)", "manufacturer_reported_str": "96% restante", "total_reads_formatted": "12.4 TB", "total_writes_formatted": "10.8 TBW"},
                        "risk_assessment": {"risk_level": "MODERADO", "health_score": 85, "ordered_action_plan": ["Manter rotina de backup 3-2-1."]},
                        "fault_diagnostics": [{"category": "Interface", "title": "Erros CRC históricos", "explanation": "Ruído elétrico passado.", "recommendation": "Monitorar estabilidade."}],
                        "smart_attributes": [{"id": "0xC7", "name": "CRC Error Count", "current": 100, "worst": 100, "threshold": 0, "raw_hex": "0x001D", "raw_int": 29, "interpreted_value": "29 erros", "severity": "warning"}],
                    }
                ],
            },
        }

        auth_res = login_admin(cls.base_dir, "Luna@19102023")
        cls.token = auth_res["token"]

        ThreadingHTTPServer.allow_reuse_address = True
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), AegisPulseRequestHandler)
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.temp_dir.cleanup()

    def _http_call(self, path: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict, bytes, dict]:
        data_bytes = json.dumps(body).encode("utf-8") if body is not None else (b"{}" if method == "POST" else None)
        req = Request(
            f"{self.base_url}{path}",
            data=data_bytes,
            method=method,
            headers={"Content-Type": "application/json", "X-Operator-Token": self.token},
        )
        try:
            with urlopen(req, timeout=10) as resp:
                raw = resp.read()
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except Exception:
                    parsed = {}
                return resp.status, hdrs, raw, parsed
        except HTTPError as he:
            raw = he.read()
            hdrs = {k.lower(): v for k, v in he.headers.items()}
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except Exception:
                parsed = {}
            return he.code, hdrs, raw, parsed

    def test_01_html_generation_and_content_validation(self):
        """1. Geração de HTML válido e completo sem NameError."""
        res = generate_html_report(SESSION_STATE["last_snapshot"], self.base_dir, ai_analysis="### Diagnóstico IA\n- Sistema íntegro.")
        self.assertTrue(res["success"])
        self.assertTrue(res["html_generated"])
        self.assertGreater(res["html_size_bytes"], 5000)
        html_txt = Path(res["report_path"]).read_text(encoding="utf-8")
        self.assertIn("DESKTOP-0BQKLQN", html_txt)
        self.assertIn("AegisPulse Health Score", html_txt)
        self.assertIn("PC801 NVMe SK hynix 1TB", html_txt)

    def test_02_valid_pdf_generation_and_binary_header_eof(self):
        """2. Geração de PDF binário válido (%PDF-1.4 ... %%EOF)."""
        res = generate_html_report(SESSION_STATE["last_snapshot"], self.base_dir)
        self.assertTrue(res["pdf_generated"])
        self.assertGreater(res["pdf_size_bytes"], 1000)
        pdf_bytes = Path(res["pdf_path"]).read_bytes()
        self.assertTrue(pdf_bytes.startswith(b"%PDF-1.4"))
        self.assertIn(b"%%EOF", pdf_bytes[-64:])
        self.assertIn(b"/Type /Catalog", pdf_bytes)
        self.assertIn(b"/Type /Page", pdf_bytes)

    def test_03_http_delivery_of_html_and_pdf_files(self):
        """3. Entrega e abertura/download via rotas HTTP (/api/report/generate e /reports/<file>)."""
        status, _, _, payload = self._http_call("/api/report/generate", method="POST", body={"auto_open": False})
        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["html_generated"])
        self.assertTrue(payload["pdf_generated"])

        # Baixa o HTML gerado
        st_h, hdr_h, raw_h, _ = self._http_call(payload["url"], method="GET")
        self.assertEqual(st_h, 200)
        self.assertIn("text/html", hdr_h.get("content-type", ""))
        self.assertGreater(len(raw_h), 5000)

        # Baixa o PDF gerado com ?download=1
        st_p, hdr_p, raw_p, _ = self._http_call(payload["download_pdf_url"], method="GET")
        self.assertEqual(st_p, 200)
        self.assertEqual(hdr_p.get("content-type"), "application/pdf")
        self.assertIn("attachment", hdr_p.get("content-disposition", ""))
        self.assertTrue(raw_p.startswith(b"%PDF-1.4"))

    def test_04_missing_optional_snapshot_fields(self):
        """4. Ausência de dados opcionais (snapshot vazio ou campos None) gera relatório sem quebrar."""
        res = generate_html_report(snapshot={"hardware": None, "os": None, "storage_suite": None}, base_dir=self.base_dir)
        self.assertTrue(res["success"])
        self.assertTrue(res["html_generated"])
        self.assertTrue(res["pdf_generated"])

    def test_05_ai_service_unavailable_generates_deterministic_report(self):
        """5. Falha ou ausência do serviço de IA gera parecer técnico determinístico indicando a limitação."""
        res = generate_html_report(SESSION_STATE["last_snapshot"], self.base_dir, ai_analysis="[ERRO] Serviço de IA indisponível.")
        self.assertTrue(res["success"])
        self.assertFalse(res["ai_was_used"])
        html_txt = Path(res["report_path"]).read_text(encoding="utf-8")
        self.assertIn("Parecer Técnico Baseado em Regras Determinísticas", html_txt)

    def test_06_server_unavailable_connection_refused_detection(self):
        """6. Indisponibilidade do servidor é detectada como URLError/ConnectionRefused."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            closed_port = s.getsockname()[1]
        req = Request(f"http://127.0.0.1:{closed_port}/api/report/generate", data=b"{}", method="POST")
        with self.assertRaises(URLError):
            urlopen(req, timeout=2)

    def test_07_invalid_route_returns_structured_404_json(self):
        """7. Rota incorreta retorna HTTP 404 JSON estruturado (nunca fecha o socket sem resposta)."""
        status, _, _, payload = self._http_call("/api/report/rota_inexistente", method="POST", body={})
        self.assertEqual(status, 404)
        self.assertEqual(payload.get("error"), "invalid_endpoint")

    def test_08_internal_generator_exception_returns_structured_500_never_empty_response(self):
        """8. Erro interno do gerador retorna HTTP 500 JSON com error_stage, impedindo Failed to fetch."""
        status, _, _, payload = self._http_call("/api/report/generate", method="POST", body={"_simulate_generator_error": True})
        self.assertEqual(status, 500)
        self.assertFalse(payload.get("success", True))
        self.assertEqual(payload.get("error_stage"), "internal_generator_exception")

    def test_09_permission_or_invalid_output_path_failure(self):
        """9. Falha de caminho de saída inválido (ex: caminho apontando para um arquivo existente em vez de pasta)."""
        bad_file_path = self.base_dir / "arquivo_bloqueante.txt"
        bad_file_path.write_text("bloqueio", encoding="utf-8")
        res = generate_html_report(SESSION_STATE["last_snapshot"], base_dir=bad_file_path)
        self.assertFalse(res["success"])
        self.assertIn(res["error_stage"], ("directory_creation_or_permission", "html_write_error"))

    def test_10_concurrent_repeated_requests_safety(self):
        """10. Repetição de cliques e requisições simultâneas geram arquivos distintos sem corrupção."""
        def _call_rep(_i):
            st, _, _, pl = self._http_call("/api/report/generate", method="POST", body={"auto_open": False})
            return st == 200 and pl.get("success") and pl.get("pdf_generated")

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(_call_rep, range(4)))
        self.assertTrue(all(results))

    def test_11_app_window_compatibility_and_cors_headers(self):
        """11. Compatibilidade com janela dedicada (--app): cabeçalhos CORS, OPTIONS e sanitização de hostname."""
        req = Request(f"{self.base_url}/api/report/generate", method="OPTIONS")
        with urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")



# Fallback para mounts FUSE onde os.listdir pode omitir arquivos recém-criados durante unittest discover
import importlib.util as _ilu, os as _os
_tdir = Path(__file__).resolve().parent
if "test_crash_investigator.py" not in _os.listdir(_tdir) and (_tdir / "test_crash_investigator.py").exists():
    _sp = _ilu.spec_from_file_location("test_crash_investigator", str(_tdir / "test_crash_investigator.py"))
    if _sp and _sp.loader:
        _m = _ilu.module_from_spec(_sp)
        _sp.loader.exec_module(_m)
        TestAegisPulseCrashInvestigatorV55 = _m.TestAegisPulseCrashInvestigatorV55

if __name__ == "__main__":
    unittest.main()
