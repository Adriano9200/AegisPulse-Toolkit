#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit v5.5
ARQUIVO: tests/test_crash_investigator.py
DESCRIÇÃO: Suíte de testes automatizados da Fase 2 & Fase 3 para o módulo
           AegisPulse Crash Investigator (19 cenários obrigatórios).
           NOTA: Todos os dados simulados abaixo são FIXTURES DE TESTE
           explicitamente identificadas.
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
================================================================================
"""

from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.auth import login_trial
from backend.collectors.crash_collector import (
    collect_crash_and_reliability_evidence,
    inspect_dump_files_safely,
    interpret_windows_event,
)
from backend.server import AegisPulseRequestHandler, SESSION_STATE
from backend.services.crash_investigator import (
    compare_crash_investigations,
    execute_authorized_crash_action,
    list_crash_investigations,
    run_full_crash_investigation,
    save_crash_investigation_to_db,
)
from backend.services.html_reporter import generate_html_report


# ==============================================================================
# FIXTURES DE TESTE EXPLICITAMENTE IDENTIFICADAS COMO TESTE AUTOMATIZADO
# ==============================================================================
TEST_FIXTURE_RAW_PROBE_PAYLOAD = {
    "Hostname": "TEST-WORKSTATION",
    "SystemEvents": [
        {
            "LogName": "System",
            "Id": 41,
            "Level": 1,
            "LevelDisplayName": "Crítico",
            "ProviderName": "Microsoft-Windows-Kernel-Power",
            "MachineName": "TEST-WORKSTATION",
            "TimeCreated": "2026-10-15 14:22:10",
            "Message": "[TEST_FIXTURE] O sistema foi reiniciado sem um desligamento correto primeiro. BugcheckCode 0x00000116.",
        },
        {
            "LogName": "System",
            "Id": 1001,
            "Level": 2,
            "LevelDisplayName": "Erro",
            "ProviderName": "Microsoft-Windows-WER-SystemErrorReporting",
            "MachineName": "TEST-WORKSTATION",
            "TimeCreated": "2026-10-15 14:22:15",
            "Message": "[TEST_FIXTURE] O computador foi reinicializado após uma verificação de erro. Essa verificação foi: 0x00000116 (0xfffffa8007, 0xfffff88004, 0x0, 0x2). Um despejo foi salvo em: C:\\Windows\\Minidump\\101526-11250-01.dmp.",
        },
        {
            "LogName": "System",
            "Id": 4101,
            "Level": 3,
            "LevelDisplayName": "Aviso",
            "ProviderName": "Display",
            "MachineName": "TEST-WORKSTATION",
            "TimeCreated": "2026-10-15 14:21:55",
            "Message": "[TEST_FIXTURE] O driver de vídeo nvlddmkm parou de responder e se recuperou com êxito.",
        },
        {
            "LogName": "System",
            "Id": 4101,
            "Level": 3,
            "LevelDisplayName": "Aviso",
            "ProviderName": "Display",
            "MachineName": "TEST-WORKSTATION",
            "TimeCreated": "2026-10-14 19:10:05",
            "Message": "[TEST_FIXTURE] O driver de vídeo nvlddmkm parou de responder e se recuperou com êxito.",
        },
        {
            "LogName": "System",
            "Id": 129,
            "Level": 3,
            "LevelDisplayName": "Aviso",
            "ProviderName": "storahci",
            "MachineName": "TEST-WORKSTATION",
            "TimeCreated": "2026-10-13 10:05:00",
            "Message": "[TEST_FIXTURE] Uma redefinição para o dispositivo, \\Device\\RaidPort0, foi emitida.",
        },
        {
            "LogName": "System",
            "Id": 19,
            "Level": 4,
            "LevelDisplayName": "Informação",
            "ProviderName": "Microsoft-Windows-WindowsUpdateClient",
            "MachineName": "TEST-WORKSTATION",
            "TimeCreated": "2026-10-13 08:00:00",
            "Message": "[TEST_FIXTURE] Instalação bem-sucedida da seguinte atualização: NVIDIA Display Driver 560.94.",
        },
    ],
    "ApplicationEvents": [],
    "ReliabilityRecords": [
        {
            "SourceName": "Windows",
            "EventIdentifier": 1001,
            "ProductName": "Windows Operating System",
            "TimeGenerated": "2026-10-15 14:22:20",
            "Message": "[TEST_FIXTURE] O Windows não foi desligado corretamente (BugCheck 0x00000116).",
        },
        {
            "SourceName": "MsiInstaller",
            "EventIdentifier": 11707,
            "ProductName": "NVIDIA Graphics Driver",
            "TimeGenerated": "2026-10-13 08:00:05",
            "Message": "[TEST_FIXTURE] Instalação concluída com êxito.",
        },
    ],
    "CrashControlConfig": {
        "CrashDumpEnabled": 3,
        "DumpFile": r"C:\Windows\MEMORY.DMP",
        "MinidumpDir": r"C:\Windows\Minidump",
    },
    "CollectionErrors": [],
}


class TestAegisPulseCrashInvestigatorV55(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="aegispulse_crash_test_"))
        (cls.temp_dir / "frontend").mkdir(parents=True, exist_ok=True)
        (cls.temp_dir / "reports").mkdir(parents=True, exist_ok=True)
        (cls.temp_dir / "data").mkdir(parents=True, exist_ok=True)
        (cls.temp_dir / "frontend" / "index.html").write_text("<html><body>AegisPulse Crash Test</body></html>", encoding="utf-8")

        SESSION_STATE["base_dir"] = cls.temp_dir
        SESSION_STATE["action_logs"] = []
        SESSION_STATE["last_crash_investigation"] = {}

        trial_res = login_trial(cls.temp_dir)
        cls.token = trial_res["token"]

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

    def _request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict, bytes]:
        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-Operator-Token": self.token,
        }
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=15) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                parsed = json.loads(raw.decode("utf-8")) if "application/json" in ctype else {}
                return resp.status, parsed, raw
        except HTTPError as err:
            raw = err.read()
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except Exception:
                parsed = {}
            return err.code, parsed, raw

    # --------------------------------------------------------------------------
    # 1. Eventos críticos de fixture identificada + separação Fato vs Interpretação
    # --------------------------------------------------------------------------
    def test_01_critical_events_from_fixture_and_fact_vs_interpretation_separation(self):
        inv = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=168,
            snapshot={"hardware": {"hostname": "TEST-WORKSTATION", "temperatures": {"cpu_temp_c": 62, "gpu_temp_c": 71}}},
            raw_override=TEST_FIXTURE_RAW_PROBE_PAYLOAD,
        )
        self.assertEqual(inv["incident_summary"]["total_events_collected"], 6)
        self.assertGreaterEqual(inv["incident_summary"]["bugcheck_count"], 1)

        for ev in inv["events"]:
            self.assertTrue(ev["original_message"].startswith("[TEST_FIXTURE]"))
            self.assertTrue(len(ev["technical_interpretation"]) > 20)
            self.assertNotEqual(ev["original_message"], ev["technical_interpretation"])
            self.assertIn("affected_component", ev)
            self.assertIn("severity", ev)

    # --------------------------------------------------------------------------
    # 2. Ausência de eventos no período
    # --------------------------------------------------------------------------
    def test_02_absence_of_events_in_period(self):
        empty_fixture = {
            "Hostname": "CLEAN-PC",
            "SystemEvents": [],
            "ApplicationEvents": [],
            "ReliabilityRecords": [],
            "CrashControlConfig": {"CrashDumpEnabled": 3},
            "CollectionErrors": [],
        }
        inv = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=72,
            snapshot={"hardware": {"hostname": "CLEAN-PC"}},
            raw_override=empty_fixture,
            dump_dirs_override=[self.temp_dir / "empty_dumps"],
        )
        self.assertEqual(inv["incident_summary"]["total_events_collected"], 0)
        self.assertEqual(inv["incident_summary"]["overall_severity"], "NORMAL")
        self.assertEqual(inv["hypotheses"], [])

    # --------------------------------------------------------------------------
    # 3. Permissões insuficientes para ler logs
    # --------------------------------------------------------------------------
    def test_03_insufficient_permissions_to_read_logs(self):
        restricted_fixture = {
            "Hostname": "RESTRICTED-PC",
            "PermissionDenied": True,
            "SystemEvents": [],
            "ApplicationEvents": [],
            "ReliabilityRecords": [],
            "CrashControlConfig": {},
            "CollectionErrors": ["Canal WHEA-Logger negado por falta de privilégio Administrativo."],
        }
        inv = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=168,
            snapshot={},
            raw_override=restricted_fixture,
            dump_dirs_override=[self.temp_dir / "empty_dumps"],
        )
        self.assertTrue(any("Permissões insuficientes" in lim for lim in inv["limitations_and_gaps"]))
        self.assertTrue(any("WHEA" in lim for lim in inv["limitations_and_gaps"]))

    # --------------------------------------------------------------------------
    # 4. Logs indisponíveis ou corrompidos
    # --------------------------------------------------------------------------
    def test_04_unavailable_or_corrupted_logs(self):
        with patch("backend.collectors.crash_collector._run_powershell_crash_probe") as mock_probe:
            mock_probe.return_value = {
                "CorruptedLog": True,
                "SystemEvents": [],
                "ApplicationEvents": [],
                "ReliabilityRecords": [],
                "CollectionErrors": ["Arquivo de log System.evtx corrompido (Erro 1500)."],
            }
            ev = collect_crash_and_reliability_evidence(period_hours=168)
            self.assertEqual(ev["events"], [])
            self.assertTrue(any("corrompido" in c for c in ev["collection_errors"]))

    # --------------------------------------------------------------------------
    # 5. Ausência de dumps de BSOD e orientação somente-leitura
    # --------------------------------------------------------------------------
    def test_05_absence_of_bsod_dumps_and_guidance(self):
        inv = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=168,
            snapshot={},
            raw_override=TEST_FIXTURE_RAW_PROBE_PAYLOAD,
            dump_dirs_override=[self.temp_dir / "non_existent_minidump_dir"],
        )
        self.assertEqual(inv["bsod_analysis"]["minidump_files_count"], 0)
        self.assertGreaterEqual(inv["bsod_analysis"]["bugcheck_count"], 1)
        self.assertTrue(any("nenhum arquivo .dmp correspondente" in lim for lim in inv["limitations_and_gaps"]))

    # --------------------------------------------------------------------------
    # 6. Dump existente mas apenas com módulos de SO (vítima, não causa confirmada)
    # --------------------------------------------------------------------------
    def test_06_existing_dump_with_only_os_victim_modules(self):
        dump_dir = self.temp_dir / "mock_minidumps_os_only"
        dump_dir.mkdir(parents=True, exist_ok=True)
        dmp_file = dump_dir / "101626-os-only.dmp"
        dmp_file.write_bytes(b"PAGEDUMP" + b"\x00" * 128 + b"ntoskrnl.exe\x00win32kfull.sys\x00" + b"\x00" * 256)

        res = inspect_dump_files_safely(dump_dirs=[dump_dir])
        self.assertEqual(res["minidump_files_count"], 1)
        d0 = res["minidumps"][0]
        self.assertTrue(d0["valid_signature"])
        self.assertIn("win32kfull.sys", d0["involved_victim_modules"])
        self.assertEqual(d0["probable_suspect_modules"], [])

    # --------------------------------------------------------------------------
    # 7. Dump existente com driver de terceiro (suspeito provável vs causa confirmada)
    # --------------------------------------------------------------------------
    def test_07_existing_dump_with_third_party_suspect_driver(self):
        dump_dir = self.temp_dir / "mock_minidumps_3rdparty"
        dump_dir.mkdir(parents=True, exist_ok=True)
        dmp_file = dump_dir / "101626-gpu-crash.dmp"
        dmp_file.write_bytes(b"PAGEDUMP" + b"\x00" * 64 + b"win32kfull.sys\x00nvlddmkm.sys\x00dxgkrnl.sys\x00" + b"\x00" * 128)

        res = inspect_dump_files_safely(dump_dirs=[dump_dir])
        self.assertEqual(res["minidump_files_count"], 1)
        d0 = res["minidumps"][0]
        self.assertIn("dxgkrnl.sys", d0["involved_victim_modules"])
        self.assertIn("nvlddmkm.sys", d0["probable_suspect_modules"])
        self.assertIn("Não confirmada isoladamente", d0["confirmed_cause_from_dump"])

    # --------------------------------------------------------------------------
    # 8. Eventos repetidos e próximos no tempo + correlação com atualização
    # --------------------------------------------------------------------------
    def test_08_recurring_and_nearby_events_clustering(self):
        inv = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=168,
            snapshot={},
            raw_override=TEST_FIXTURE_RAW_PROBE_PAYLOAD,
        )
        rec = inv["recurring_events_summary"]
        self.assertTrue(len(rec) > 0)
        display_group = next((g for g in rec if g["event_id"] == 4101), None)
        self.assertIsNotNone(display_group)
        self.assertEqual(display_group["count"], 2)
        self.assertGreaterEqual(inv["reliability_history"]["installations_updates_count"], 1)

    # --------------------------------------------------------------------------
    # 9. Falha de coleta de SMART
    # --------------------------------------------------------------------------
    def test_09_smart_collection_failure_resilience(self):
        inv = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=168,
            snapshot={"storage_suite": {"devices": []}},
            raw_override=TEST_FIXTURE_RAW_PROBE_PAYLOAD,
        )
        self.assertTrue(inv["success"])
        self.assertTrue(inv["hardware_io_correlation"]["smart_collection_failed"])
        self.assertTrue(any("SMART" in lim for lim in inv["limitations_and_gaps"]))

    # --------------------------------------------------------------------------
    # 10. Erros de I/O, timeout, nuance do Evento 129/CRC e prioridade de backup
    # --------------------------------------------------------------------------
    def test_10_io_errors_timeout_and_nuanced_129_crc_interpretation(self):
        ev_129 = interpret_windows_event("storahci", 129, "Reset to device \\Device\\RaidPort0 was issued.", "AVISO")
        self.assertIn("NÃO prova automaticamente que o SSD/HDD está fisicamente defeituoso", ev_129["technical_interpretation"])

        io_media_fixture = {
            "Hostname": "TEST-PC",
            "SystemEvents": [
                {
                    "LogName": "System",
                    "Id": 7,
                    "Level": 2,
                    "ProviderName": "disk",
                    "MachineName": "TEST-PC",
                    "TimeCreated": "2026-10-16 07:00:00",
                    "Message": "[TEST_FIXTURE] O dispositivo \\Device\\Harddisk0\\DR0 possui um bloco defeituoso.",
                },
                {
                    "LogName": "System",
                    "Id": 153,
                    "Level": 3,
                    "ProviderName": "disk",
                    "MachineName": "TEST-PC",
                    "TimeCreated": "2026-10-16 07:00:05",
                    "Message": "[TEST_FIXTURE] A operação de E/S no endereço de bloco lógico 0x1234 foi repetida.",
                },
            ],
            "ApplicationEvents": [],
            "ReliabilityRecords": [],
            "CrashControlConfig": {},
            "CollectionErrors": [],
        }
        snap_with_failing_disk = {
            "storage_suite": {
                "devices": [
                    {
                        "disk_number": 0,
                        "brand": "Seagate",
                        "model": "ST1000DM010",
                        "smart_summary": {
                            "reallocated_sectors": 24,
                            "pending_sectors": 8,
                            "uncorrectable_errors": 2,
                            "crc_interface_errors": 15,
                        },
                    }
                ]
            }
        }
        inv = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=168,
            snapshot=snap_with_failing_disk,
            raw_override=io_media_fixture,
        )
        self.assertTrue(inv["incident_summary"]["data_protection_priority"])
        self.assertEqual(inv["hypotheses"][0]["hypothesis_id"], "HYP_STORAGE_MEDIA_FAULT")
        self.assertEqual(inv["action_plan"][0]["action_id"], "manual_backup_before_storage_intervention")

    # --------------------------------------------------------------------------
    # 11. Dados de hardware inconsistentes
    # --------------------------------------------------------------------------
    def test_11_inconsistent_or_malformed_hardware_data(self):
        broken_snap = {
            "hardware": {"hostname": None, "temperatures": {"cpu_temp_c": None}},
            "storage_suite": {"devices": ["not_a_dict", {"disk_number": 0, "smart_summary": None}]},
            "drivers_bios": {"drivers": None},
        }
        inv = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=168,
            snapshot=broken_snap,
            raw_override=TEST_FIXTURE_RAW_PROBE_PAYLOAD,
        )
        self.assertTrue(inv["success"])
        self.assertTrue(len(inv["hypotheses"]) >= 1)

    # --------------------------------------------------------------------------
    # 12. Serviço de IA indisponível (Fallback determinístico local N3)
    # --------------------------------------------------------------------------
    def test_12_ai_service_unavailable_local_fallback(self):
        with patch("backend.services.gemini_ai.query_gemini_ai", side_effect=RuntimeError("Cloud AI Offline")):
            inv = run_full_crash_investigation(
                base_dir=self.temp_dir,
                period_hours=168,
                snapshot={},
                use_ai=True,
                ai_provider="gemini",
                api_key="FAKE_KEY",
                user_role="admin",
                raw_override=TEST_FIXTURE_RAW_PROBE_PAYLOAD,
            )
            self.assertTrue(inv["success"])
            dossier = inv["ai_correlation"]["structured_analysis_text"]
            self.assertIn("## 1. Resumo Executivo do Incidente", dossier)
            self.assertIn("## 3. Hipóteses Técnicas Ordenadas por Plausibilidade", dossier)
            self.assertIn("## 7. Plano de Ação Priorizado para Suporte N3", dossier)
            self.assertIn("## 8. Riscos e Cuidados Antes de Cada Intervenção", dossier)
            self.assertTrue(any("Falha ao consultar serviço de IA" in lim for lim in inv["limitations_and_gaps"]))

    # --------------------------------------------------------------------------
    # 13. Resposta da IA sem evidências suficientes reconhece incerteza
    # --------------------------------------------------------------------------
    def test_13_ai_response_with_insufficient_evidence_uncertainty(self):
        with patch("backend.services.gemini_ai.query_gemini_ai", return_value={"success": True, "response_text": "Curto"}):
            inv = run_full_crash_investigation(
                base_dir=self.temp_dir,
                period_hours=24,
                snapshot={},
                use_ai=True,
                ai_provider="gemini",
                api_key="FAKE_KEY",
                user_role="admin",
                raw_override=TEST_FIXTURE_RAW_PROBE_PAYLOAD,
            )
            self.assertFalse(inv["ai_correlation"]["ai_used"])
            self.assertTrue(any("não conteve evidências suficientes" in lim for lim in inv["limitations_and_gaps"]))

    # --------------------------------------------------------------------------
    # 14. Banco SQLite indisponível / falha de persistência tratada graciosamente
    # --------------------------------------------------------------------------
    def test_14_sqlite_database_unavailable_and_migration_resilience(self):
        fake_file_as_dir = self.temp_dir / "not_a_dir.txt"
        fake_file_as_dir.write_text("bloqueio", encoding="utf-8")
        inv_id, err_msg = save_crash_investigation_to_db(fake_file_as_dir, {"incident_summary": {}})
        self.assertIsNone(inv_id)
        self.assertTrue(len(err_msg) > 0)

        hist = list_crash_investigations(fake_file_as_dir)
        self.assertFalse(hist["success"])
        self.assertEqual(hist["items"], [])

    # --------------------------------------------------------------------------
    # 15. Comparação de períodos com diferentes coberturas (720h vs 24h)
    # --------------------------------------------------------------------------
    def test_15_period_comparison_with_different_coverage_warning(self):
        inv_old = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=720,
            snapshot={"hardware": {"hostname": "COMPARE-HOST"}},
            raw_override=TEST_FIXTURE_RAW_PROBE_PAYLOAD,
        )
        inv_new = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=24,
            snapshot={"hardware": {"hostname": "COMPARE-HOST"}},
            raw_override=TEST_FIXTURE_RAW_PROBE_PAYLOAD,
        )

        comp = compare_crash_investigations(inv_old, inv_new)
        self.assertTrue(comp["coverage_differ_flag"])
        self.assertIn("ATENÇÃO METODOLÓGICA", comp["coverage_warning"])
        self.assertGreater(comp["critical_rate_per_24h_newer"], comp["critical_rate_per_24h_older"])

    # --------------------------------------------------------------------------
    # 16. Geração HTML e PDF integrando o Crash Investigator
    # --------------------------------------------------------------------------
    def test_16_html_and_pdf_report_generation_with_crash_investigator(self):
        inv = run_full_crash_investigation(
            base_dir=self.temp_dir,
            period_hours=168,
            snapshot={"hardware": {"hostname": "REPORT-CRASH-PC", "manufacturer": "Dell", "model": "XPS"}},
            raw_override=TEST_FIXTURE_RAW_PROBE_PAYLOAD,
        )
        rep = generate_html_report(
            snapshot={
                "hardware": {"hostname": "REPORT-CRASH-PC", "manufacturer": "Dell", "model": "XPS"},
                "crash_investigation": inv,
            },
            base_dir=self.temp_dir,
            ai_analysis=inv["ai_correlation"]["structured_analysis_text"],
        )
        self.assertTrue(rep["success"])
        html_content = Path(rep["report_path"]).read_text(encoding="utf-8")
        self.assertIn("AegisPulse Crash Investigator", html_content)
        self.assertIn("0X00000116", html_content.upper())

        pdf_bytes = Path(rep["pdf_path"]).read_bytes()
        self.assertTrue(pdf_bytes.startswith(b"%PDF-1.4"))
        self.assertIn(b"%%EOF", pdf_bytes)

    # --------------------------------------------------------------------------
    # 17. Integração HTTP da API e tratamento de falha de comunicação
    # --------------------------------------------------------------------------
    def test_17_api_communication_and_http_endpoints_integration(self):
        st_run, data_run, _ = self._request(
            "POST",
            "/api/crash-investigator/run",
            {"period_days": 7, "category": "ALL", "mock_evidence": TEST_FIXTURE_RAW_PROBE_PAYLOAD},
        )
        self.assertEqual(st_run, 200)
        self.assertTrue(data_run["success"])
        self.assertEqual(data_run["crash_investigation"]["incident_summary"]["total_events_collected"], 6)

        st_hist, data_hist, _ = self._request("GET", "/api/crash-investigator/history?limit=5")
        self.assertEqual(st_hist, 200)
        self.assertTrue(data_hist["success"])
        self.assertGreaterEqual(data_hist["total"], 1)

        st_cmp, data_cmp, _ = self._request("GET", "/api/crash-investigator/compare")
        self.assertEqual(st_cmp, 200)
        self.assertTrue(data_cmp["success"])

        with self.assertRaises(URLError):
            urlopen(Request("http://127.0.0.1:59998/api/crash-investigator/run"), timeout=1)

    # --------------------------------------------------------------------------
    # 18. Tentativa de execução de comando sem confirmação explícita é bloqueada
    # --------------------------------------------------------------------------
    def test_18_action_execution_blocked_without_explicit_confirmation(self):
        res_no_tok = execute_authorized_crash_action(
            base_dir=self.temp_dir,
            action_id="verify_dism_checkhealth",
            confirm_token="",
        )
        self.assertFalse(res_no_tok["success"])
        self.assertTrue(res_no_tok["confirmation_required"])
        self.assertEqual(res_no_tok["error_code"], "CONFIRMATION_REQUIRED")

    # --------------------------------------------------------------------------
    # 19. Rejeição de comandos destrutivos / parâmetros inválidos e garantia de não-execução automática
    # --------------------------------------------------------------------------
    def test_19_rejection_of_invalid_or_destructive_commands_and_no_auto_exec(self):
        for forbidden_cmd in [
            "chkdsk C: /f /r",
            "bcdedit /set recoveryenabled no",
            "reg add HKLM\\System",
            "arbitrary_ai_text_command",
        ]:
            res = execute_authorized_crash_action(
                base_dir=self.temp_dir,
                action_id=forbidden_cmd,
                confirm_token="CONFIRMAR",
            )
            self.assertFalse(res["success"])
            self.assertEqual(res["error_code"], "INVALID_OR_UNWHITELISTED_ACTION")

        # Procedimento manual assistido não pode ser disparado como comando automático
        res_manual = execute_authorized_crash_action(
            base_dir=self.temp_dir,
            action_id="manual_backup_before_storage_intervention",
            confirm_token="CONFIRMAR",
        )
        self.assertFalse(res_manual["success"])
        self.assertEqual(res_manual["error_code"], "MANUAL_PROCEDURE_ONLY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
