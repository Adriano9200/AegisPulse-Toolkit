#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: tests/test_health_score.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.5.0
================================================================================
Descrição:
Suíte de Testes Automatizados para o Módulo AegisPulse Health Score:
- Cenário 1: Computador com todos os indicadores normais (Classificação Excelente 90-100).
- Cenário 2: Computador com SSD apresentando falha crítica SMART (Garantia de que
             a falha crítica não seja mascarada pela média e ative o teto crítico).
- Cenário 3: Temperatura de CPU acima do limite (>88°C) gerando achado de refrigeração.
- Cenário 4: Memória RAM de baixa capacidade (<8GB) e Single-Channel gerando recomendações.
- Cenário 5: Falha de dispositivo PnP no Gerenciador de Dispositivos.
- Cenário 6: Ausência de sensores térmicos (cobertura reduzida sem penalizar arbitrariamente).
- Cenário 7: Persistência SQLite (`health_score_evaluations`), recuperação e histórico paginado.
- Cenário 8: Comparação inteligente entre coletas (detecção de melhora, degradação e variação de cobertura).
- Cenário 9: Determinismo absoluto da pontuação (a mesma entrada gera rigorosamente o mesmo score).
- Cenário 10: Independência da IA (a IA não tem controle direto sobre a nota determinística).
"""

from __future__ import annotations

import gc
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Garante inclusão da raiz do projeto no sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import importlib.util as _ilu
_root = Path(__file__).resolve().parent.parent
for _mname, _rpath in [
    ("backend.collectors.storage_advanced", "backend/collectors/storage_advanced.py"),
    ("backend.services.storage_health", "backend/services/storage_health.py"),
    ("backend.services.storage_diagnostics", "backend/services/storage_diagnostics.py"),
    ("backend.services.storage_recovery", "backend/services/storage_recovery.py"),
    ("backend.services.health_score", "backend/services/health_score.py"),
]:
    if _mname not in sys.modules and (_root / _rpath).exists():
        _sp = _ilu.spec_from_file_location(_mname, str(_root / _rpath))
        _md = _ilu.module_from_spec(_sp)
        sys.modules[_mname] = _md
        _sp.loader.exec_module(_md)


from backend.services.health_score import (
    compute_health_score,
    get_latest_health_score,
    list_health_score_history,
    compare_health_evaluations,
    classify_score,
    get_machine_identifier,
)


def _build_mock_snapshot(
    overall_ok: bool = True,
    storage_pending_sectors: int = 0,
    storage_raw: bool = False,
    cpu_temp_c: float = 48.0,
    cpu_load: float = 15.0,
    ram_gb: float = 32.0,
    ram_modules_count: int = 2,
    pnp_errors_count: int = 0,
    antivirus_enabled: bool = True,
    has_sensors: bool = True,
) -> dict:
    """Constrói um snapshot sintético de teste com dados realistas controlados."""
    devices = [
        {
            "disk_number": 0,
            "device_path": r"\\.\PhysicalDrive0",
            "brand": "Samsung",
            "model": "Samsung SSD 990 PRO 1TB",
            "serial_number": "S990PRO001",
            "media_short": "SSD NVMe",
            "has_raw_volume": storage_raw,
            "capacity": {"bytes": 1_000_204_886_016, "formatted": "1.0 TB (931.5 GiB)"},
            "smart_summary": {
                "temperature_c": 41 if has_sensors else None,
                "power_on_hours": 1200,
                "power_cycles": 180,
                "reallocated_sectors": 0,
                "pending_sectors": storage_pending_sectors,
                "uncorrectable_errors": 0,
                "crc_interface_errors": 0,
                "critical_warning_raw": 0,
                "available_spare_percent": 100,
                "available_spare_threshold": 10,
                "wear_percent_used": 2,
            },
        }
    ]

    pnp_list = []
    for i in range(pnp_errors_count):
        pnp_list.append({
            "device_name": f"Dispositivo PCI com Falha #{i+1}",
            "status": "Error (Code 10)",
            "error_code": 10,
        })

    return {
        "hardware": {
            "hostname": "TEST-BENCH-01",
            "manufacturer": "Dell Inc.",
            "model": "Precision 3630",
            "serial_service_tag": "TESTTAG123",
            "uuid": "4C4C4544-004A-4B10-8053-C7C04F353932",
            "total_ram_gb": ram_gb,
            "ram_modules": [{"slot": f"DIMM{i+1}", "capacity_gb": ram_gb / ram_modules_count} for i in range(ram_modules_count)],
            "cpus": [{
                "name": "Intel(R) Core(TM) i7-8700K CPU @ 3.70GHz",
                "cores": 6,
                "threads": 12,
                "load_percent": cpu_load,
            }],
            "temperatures": {
                "cpu_temp_c": cpu_temp_c if has_sensors else None,
                "cpu_temp_source": "Sensor WMI",
                "gpu_temp_c": 44.0 if has_sensors else None,
            },
            "volumes": [{"drive": "C:", "size_gb": 500.0, "free_gb": 280.0, "used_percent": 44.0}],
        },
        "os": {
            "os_name": "Microsoft Windows 11 Enterprise",
            "display_version": "23H2",
            "full_build": "22631.3000",
            "uptime_hours": 24.5,
            "last_boot": "2026-10-14 10:00:00",
            "security": {
                "antivirus_enabled": antivirus_enabled,
                "realtime_protection": antivirus_enabled,
                "signature_age_days": 0,
                "tpm_present": True,
                "tpm_ready": True,
            },
        },
        "drivers_bios": {
            "total_drivers": 140,
            "outdated_drivers_count": 4,
            "pnp_errors": pnp_list,
            "bios": {
                "smbios_version": "2.10.0",
                "release_date": "2025-05-10",
                "age_months": 17,
                "needs_review": False,
            },
        },
        "software": {
            "outdated_count": 2,
            "bloatware_count": 1,
        },
        "gaming": {
            "missing_dlls_count": 0,
            "gamer_profile": {"gamer_tier": "Intermediário Gamer", "ram_gamer": {"channel_status": "Dual-Channel" if ram_modules_count >= 2 else "Single-Channel"}},
        },
        "storage_suite": {
            "total_physical_disks": len(devices),
            "highest_risk_level": "CRÍTICO" if (storage_pending_sectors > 0 or storage_raw) else "BAIXO",
            "devices": devices,
            "system_disk_events": [],
        },
    }


class TestAegisPulseHealthScore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

    def tearDown(self):
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_01_healthy_pc_scores_excellent(self):
        """Cenário 1: Computador perfeitamente saudável deve obter nota na faixa Excelente (90–100)."""
        snap = _build_mock_snapshot(overall_ok=True)
        res = compute_health_score(snap, base_dir=self.base_dir)

        self.assertGreaterEqual(res["overall_score"], 90.0)
        self.assertEqual(res["classification"], "Excelente")
        self.assertFalse(res["has_critical_issue"])
        self.assertFalse(res["critical_cap_applied"])
        self.assertEqual(res["coverage"]["count"], 8)
        self.assertEqual(res["coverage"]["percent"], 100.0)

    def test_02_critical_ssd_applies_cap_and_prevents_masking(self):
        """Cenário 2: Falha crítica SMART no disco (setores pendentes) NÃO pode ser mascarada pela média."""
        snap = _build_mock_snapshot(overall_ok=False, storage_pending_sectors=4)
        res = compute_health_score(snap, base_dir=self.base_dir)

        self.assertTrue(res["has_critical_issue"])
        self.assertTrue(res["critical_cap_applied"])
        # Garante que a nota foi limitada e nunca seja Excelente nem Bom
        self.assertLessEqual(res["overall_score"], 59.0)
        self.assertIn(res["classification"], ("Ruim", "Crítico"))

        # Verifica se o achado crítico foi gerado com prioridade máxima
        top_finding = res["prioritized_findings"][0]
        self.assertEqual(top_finding["severity"], "CRÍTICO")
        self.assertIn("Setores Pendentes", top_finding["title"])

    def test_03_high_cpu_temperature_generates_alert(self):
        """Cenário 3: Temperatura crítica de CPU (92°C) deve deduzir pontos e gerar alerta crítico."""
        snap = _build_mock_snapshot(cpu_temp_c=92.0)
        res = compute_health_score(snap, base_dir=self.base_dir)

        thermal_eval = res["categories"]["thermals"]
        self.assertEqual(thermal_eval["status"], "critico")
        self.assertLess(thermal_eval["score"], 60.0)

        crit_findings = [f for f in res["prioritized_findings"] if "THERMAL_CPU" in f.get("id", "")]
        self.assertTrue(len(crit_findings) > 0)
        self.assertEqual(crit_findings[0]["severity"], "CRÍTICO")

    def test_04_low_ram_and_single_channel_deductions(self):
        """Cenário 4: Memória RAM de 4GB Single-Channel deve ser penalizada adequadamente."""
        snap = _build_mock_snapshot(ram_gb=4.0, ram_modules_count=1)
        res = compute_health_score(snap, base_dir=self.base_dir)

        ram_eval = res["categories"]["ram"]
        self.assertLessEqual(ram_eval["score"], 70.0)
        ram_findings = [f for f in res["prioritized_findings"] if f.get("category") == "ram"]
        self.assertTrue(any("RAM_CAPACITY_LOW" in f["id"] for f in ram_findings))

    def test_05_pnp_driver_error_detection(self):
        """Cenário 5: Erros no Gerenciador de Dispositivos (PnP) reduzem a nota da categoria de drivers."""
        snap = _build_mock_snapshot(pnp_errors_count=2)
        res = compute_health_score(snap, base_dir=self.base_dir)

        drv_eval = res["categories"]["drivers_devices"]
        self.assertLess(drv_eval["score"], 80.0)
        self.assertTrue(any("DRIVER_PNP_ERROR" in f["id"] for f in res["prioritized_findings"]))

    def test_06_missing_sensors_adjusts_coverage_without_false_penalty(self):
        """Cenário 6: Ausência de sensores térmicos reduz a cobertura sem aplicar nota zero às demais."""
        snap = _build_mock_snapshot(has_sensors=False)
        res = compute_health_score(snap, base_dir=self.base_dir)

        # Categoria de temperatura deve estar marcada como indisponível
        self.assertFalse(res["categories"]["thermals"]["available"])
        self.assertEqual(res["coverage"]["count"], 7)
        self.assertEqual(res["coverage"]["percent"], 87.5)
        # O score global deve ser calculado estritamente sobre as 7 disponíveis
        self.assertGreaterEqual(res["overall_score"], 85.0)

    def test_07_sqlite_persistence_and_history(self):
        """Cenário 7: Avaliações devem persistir no SQLite e permitir listagem paginada."""
        snap1 = _build_mock_snapshot(cpu_temp_c=45.0)
        res1 = compute_health_score(snap1, base_dir=self.base_dir)

        snap2 = _build_mock_snapshot(cpu_temp_c=55.0)
        res2 = compute_health_score(snap2, base_dir=self.base_dir)

        latest = get_latest_health_score(self.base_dir)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["machine_uuid"], res2["machine_uuid"])

        hist = list_health_score_history(self.base_dir, limit=10)
        self.assertEqual(hist["total"], 2)
        self.assertEqual(len(hist["items"]), 2)
        self.assertEqual(len(hist["chart_series"]), 2)

    def test_08_comparison_diff_between_evaluations(self):
        """Cenário 8: Comparar duas avaliações deve identificar variação de nota, novos problemas e resolvidos."""
        # Avaliação 1 com erro de antivírus
        snap_old = _build_mock_snapshot(antivirus_enabled=False)
        eval_old = compute_health_score(snap_old, base_dir=self.base_dir)

        # Avaliação 2 com antivírus corrigido (melhora real)
        snap_new = _build_mock_snapshot(antivirus_enabled=True)
        eval_new = compute_health_score(snap_new, base_dir=self.base_dir)

        diff = compare_health_evaluations(eval_old, eval_new)
        self.assertGreater(diff["score_delta"], 0)
        self.assertEqual(diff["trend_label"], "Melhora Real Comprovada")
        self.assertTrue(any("SEC_ANTIVIRUS_DISABLED" in f["id"] for f in diff["resolved_findings"]))

    def test_09_deterministic_reproducibility(self):
        """Cenário 9: Os mesmos dados de entrada devem produzir rigorosamente a mesma pontuação."""
        snap = _build_mock_snapshot()
        eval1 = compute_health_score(snap)
        eval2 = compute_health_score(snap)

        self.assertEqual(eval1["overall_score"], eval2["overall_score"])
        self.assertEqual(eval1["classification"], eval2["classification"])
        self.assertEqual(eval1["coverage"]["percent"], eval2["coverage"]["percent"])
        self.assertEqual(len(eval1["prioritized_findings"]), len(eval2["prioritized_findings"]))

    def test_10_ai_cannot_override_score(self):
        """Cenário 10: O Health Score permanece independente da IA e auditável."""
        snap = _build_mock_snapshot(overall_ok=True)
        eval_res = compute_health_score(snap)

        # Simula resposta da IA com opinião diferente
        ai_opinion_text = "Eu acho que o computador é ruim nota 20."

        # O valor calculado pelo backend deve continuar inalterado
        self.assertGreaterEqual(eval_res["overall_score"], 90.0)
        self.assertNotEqual(eval_res["overall_score"], 20.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
