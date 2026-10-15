#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
PROJETO: AegisPulse IT Toolkit
ARQUIVO: tests/test_storage_module.py
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.0.0
================================================================================
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import importlib.util as _ilu
_root = Path(__file__).resolve().parent.parent
for _mname, _rpath in [
    ("backend.collectors.storage_advanced", "backend/collectors/storage_advanced.py"),
    ("backend.services.storage_health", "backend/services/storage_health.py"),
    ("backend.services.storage_diagnostics", "backend/services/storage_diagnostics.py"),
    ("backend.services.storage_recovery", "backend/services/storage_recovery.py"),
]:
    if _mname not in sys.modules and (_root / _rpath).exists():
        _sp = _ilu.spec_from_file_location(_mname, str(_root / _rpath))
        _md = _ilu.module_from_spec(_sp)
        sys.modules[_mname] = _md
        _sp.loader.exec_module(_md)


from backend.collectors.storage_advanced import (
    format_dual_capacity,
    parse_ata_smart_binary,
)
from backend.services.storage_health import (
    build_complete_storage_suite_payload,
    evaluate_lifespan_and_record_history,
)
from backend.services.storage_diagnostics import (
    diagnose_specialized_faults,
    run_storage_integrity_test,
)
from backend.services.storage_recovery import (
    create_or_resume_disk_image,
    execute_logical_repair,
    inspect_and_recover_partitions,
    recover_files_assisted,
    validate_clone_source_and_destination,
)


def _build_ata_smart_slot(attr_id: int, current: int, worst: int, raw_int: int, flags: int = 0x03) -> list[int]:
    raw_bytes = [(raw_int >> (8 * i)) & 0xFF for i in range(6)]
    return [attr_id, flags & 0xFF, (flags >> 8) & 0xFF, current, worst] + raw_bytes + [0]


class TestAegisPulseStorageSuiteV4(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_healthy_nvme_and_dual_capacity(self):
        """Cenário 1: Disco NVMe saudável, capacidades GB/TB vs GiB/TiB e POH em horas/dias."""
        cap = format_dual_capacity(1_000_204_886_016)
        self.assertEqual(cap["bytes"], 1_000_204_886_016)
        self.assertAlmostEqual(cap["gb"], 1000.2, places=1)
        self.assertAlmostEqual(cap["gib"], 931.51, places=1)

        mock_raw = {
            "WmiDisks": [
                {
                    "Index": 0,
                    "DeviceID": r"\\.\PhysicalDrive0",
                    "Model": "Samsung SSD 990 PRO 1TB",
                    "Manufacturer": "Samsung",
                    "SerialNumber": "S6Z1NJ0T999999",
                    "FirmwareRevision": "4B2QJXD7",
                    "InterfaceType": "NVMe",
                    "MediaType": "Fixed hard disk media",
                    "Size": 1_000_204_886_016,
                    "Status": "OK",
                    "_mock_smartctl": {
                        "nvme_smart_health_information_log": {
                            "critical_warning": 0,
                            "temperature": 42,
                            "available_spare": 100,
                            "available_spare_threshold": 10,
                            "percentage_used": 3,
                            "data_units_read": 25_000_000,
                            "data_units_written": 18_500_000,
                            "power_cycles": 310,
                            "power_on_hours": 2400,
                            "unsafe_shutdowns": 4,
                            "media_errors": 0,
                        }
                    },
                }
            ],
            "PhysicalDisks": [],
            "ReliabilityCounters": {},
            "OsDisks": [{"Number": 0, "PartitionStyle": "GPT", "OperationalStatus": "Online", "HealthStatus": "Healthy", "BusType": "NVMe", "Size": 1_000_204_886_016, "AllocatedSize": 1_000_000_000_000}],
            "Partitions": [{"DiskNumber": 0, "PartitionNumber": 1, "DriveLetter": "C", "Size": 1_000_000_000_000, "Type": "Basic", "IsBoot": True, "IsSystem": True}],
            "Volumes": [{"DriveLetter": "C", "FileSystemLabel": "Sistema", "FileSystem": "NTFS", "Size": 1_000_000_000_000, "SizeRemaining": 600_000_000_000}],
        }

        suite = build_complete_storage_suite_payload(self.base_dir, raw_override=mock_raw)
        self.assertEqual(suite["total_physical_disks"], 1)
        dev = suite["devices"][0]
        self.assertEqual(dev["brand"], "Samsung")
        self.assertEqual(dev["media_short"], "SSD NVMe")
        self.assertEqual(dev["lifespan"]["power_on_hours"], 2400)
        self.assertEqual(dev["lifespan"]["power_on_days"], 100.0)
        self.assertEqual(dev["lifespan"]["manufacturer_reported_life_pct"], 97)
        self.assertEqual(dev["risk_assessment"]["risk_level"], "BAIXO")

    def test_02_crc_error_differentiated_from_bad_sector(self):
        """Cenário 4: Erro CRC (ID 199) NÃO deve ser confundido automaticamente com Setor Defeituoso."""
        vendor_buf = [0, 0] + _build_ata_smart_slot(199, 100, 100, 42) + _build_ata_smart_slot(5, 100, 100, 0) + [0] * 340
        attrs = parse_ata_smart_binary(vendor_buf, brand="Western Digital")
        crc_attr = next(a for a in attrs if a["id_num"] == 199)
        self.assertEqual(crc_attr["raw_int"], 42)
        self.assertEqual(crc_attr["severity"], "warning")

        fake_dev = {
            "device_uid": "WD_CRC_TEST",
            "disk_number": 1,
            "brand": "Western Digital (WD)",
            "model": "WDC WD10EZEX",
            "media_short": "HDD SATA",
            "partition_style": "GPT",
            "partitions_count": 1,
            "is_initialized": True,
            "capacity": {"bytes": 1_000_000_000_000, "gb": 1000.0},
            "smart_summary": {
                "crc_interface_errors": 42,
                "reallocated_sectors": 0,
                "pending_sectors": 0,
                "uncorrectable_errors": 0,
            },
        }
        faults = diagnose_specialized_faults(fake_dev, system_disk_events=[])
        codes = [f["code"] for f in faults]
        self.assertIn("FAULT_CRC_INTERFACE", codes)
        self.assertNotIn("FAULT_BAD_SECTORS", codes)
        crc_fault = next(f for f in faults if f["code"] == "FAULT_CRC_INTERFACE")
        self.assertIn("NÃO significa automaticamente", crc_fault["explanation"])

    def test_03_critical_smart_and_sqlite_degradation_history(self):
        """Cenário 3: Disco com setores realocados/pendentes/incorrigíveis e alerta de degradação no SQLite."""
        dev_t1 = {
            "device_uid": "ST2000DM001_FAIL01",
            "disk_number": 2,
            "brand": "Seagate",
            "model": "ST2000DM001",
            "serial_number": "FAIL01",
            "media_short": "HDD SATA",
            "is_initialized": True,
            "partitions_count": 1,
            "capacity": {"bytes": 2_000_000_000_000, "gb": 2000.0},
            "smart_summary": {
                "temperature_c": 48,
                "power_on_hours": 12000,
                "power_cycles": 800,
                "reallocated_sectors": 4,
                "pending_sectors": 2,
                "uncorrectable_errors": 0,
                "crc_interface_errors": 0,
            },
        }
        res1 = evaluate_lifespan_and_record_history(self.base_dir, dev_t1)
        self.assertIn(res1["risk_assessment"]["risk_level"], ("ALTO", "CRÍTICO"))
        self.assertTrue(res1["risk_assessment"]["block_destructive_or_chkdsk_write"])

        dev_t2 = dict(dev_t1)
        dev_t2["smart_summary"] = {
            **dev_t1["smart_summary"],
            "reallocated_sectors": 12,
            "pending_sectors": 9,
            "uncorrectable_errors": 3,
        }
        res2 = evaluate_lifespan_and_record_history(self.base_dir, dev_t2)
        self.assertEqual(res2["risk_assessment"]["risk_level"], "CRÍTICO")
        self.assertTrue(res2["risk_assessment"]["recommend_cleanroom_lab"])
        self.assertGreaterEqual(len(res2["degradation_alerts"]), 2)

    def test_04_raw_volume_and_usb_pendrive_anomalies(self):
        """Cenários 2 e 5: Volume RAW, desconexões USB (Eventos 51/157) e Pendrive de capacidade falsa."""
        usb_dev = {
            "device_uid": "USB_FAKE_2TB",
            "disk_number": 3,
            "brand": "Genérico / OEM",
            "model": "USB Flash Disk 2.0 2TB",
            "serial_number": "USB0001",
            "media_short": "Pendrive USB",
            "is_removable_usb": True,
            "is_usb_bridge": True,
            "has_raw_volume": True,
            "is_read_only": True,
            "is_initialized": True,
            "partitions_count": 1,
            "drive_letters": ["E:"],
            "capacity": {"bytes": 2_000_000_000_000, "gb": 2000.0},
            "smart_summary": {},
        }
        events = [
            {"Id": 51, "Message": "An error was detected on device \\Device\\Harddisk3\\DR3 during a paging operation."},
            {"Id": 157, "Message": "Disk 3 has been surprise removed."},
        ]
        faults = diagnose_specialized_faults(usb_dev, system_disk_events=events)
        codes = {f["code"] for f in faults}
        self.assertIn("FAULT_VOLUME_RAW", codes)
        self.assertIn("FAULT_WRITE_PROTECTED", codes)
        self.assertIn("FAULT_DISCONNECTIONS_POWER", codes)
        self.assertIn("FAULT_USB_FAKE_CAPACITY", codes)

    def test_05_integrity_benchmark_and_write_safety_guard(self):
        """Cenário 6: Benchmark real de leitura em arquivo mock e bloqueio de escrita sem confirmação."""
        sample_file = self.base_dir / "mock_disk_surface.bin"
        sample_file.write_bytes(os.urandom(2 * 1024 * 1024))

        dev = {
            "device_uid": "MOCK_BENCH_01",
            "disk_number": 0,
            "brand": "SK hynix",
            "model": "PC801 NVMe 1TB",
            "media_short": "SSD NVMe",
            "drive_letters": ["C:"],
            "capacity": {"bytes": 2 * 1024 * 1024, "gb": 0.002},
            "smart_summary": {},
        }
        bench = run_storage_integrity_test(
            base_dir=self.base_dir,
            device=dev,
            test_type="read_benchmark",
            sample_mb=2,
            block_size_kb=256,
            target_override=str(sample_file),
        )
        self.assertTrue(bench["success"])
        self.assertEqual(bench["bytes_examined"], 2 * 1024 * 1024)
        self.assertGreater(bench["speed_mb_s"], 0.0)

        blocked_w = run_storage_integrity_test(
            base_dir=self.base_dir,
            device=dev,
            test_type="write_verify",
            confirm_write_risk="",
        )
        self.assertFalse(blocked_w["success"])
        self.assertTrue(blocked_w["blocked_by_safety"])

    def test_06_resumable_disk_image_mapfile_and_safety_interlocks(self):
        """Cenário 7: Bloqueio de Origem == Destino, criação de imagem com setor ruim simulado, pausa/retomada e bloqueio de CHKDSK."""
        src_bin = self.base_dir / "source_drive.bin"
        sector_0 = bytearray(512)
        sector_0[3:11] = b"NTFS    "
        sector_0[510:512] = b"\x55\xAA"
        pdf_payload = b"%PDF-1.7\nConteudo de teste AegisPulse\n%%EOF"
        png_payload = b"\x89PNG\r\n\x1a\n Dados PNG Mock IEND\xaeB`\x82"
        raw_content = bytes(sector_0) + b"\x00" * 8192 + pdf_payload + b"\x00" * 4096 + png_payload + os.urandom(64 * 1024)
        src_bin.write_bytes(raw_content)

        dev = {
            "device_uid": "RESCUE_DISK_01",
            "disk_number": 1,
            "brand": "Seagate",
            "model": "ST1000DM003",
            "serial_number": "S1D99999",
            "media_short": "HDD SATA",
            "drive_letters": ["E:"],
            "capacity": {"bytes": len(raw_content), "gb": 0.001},
            "smart_summary": {"reallocated_sectors": 8, "pending_sectors": 4, "uncorrectable_errors": 1},
        }

        same_drive_check = validate_clone_source_and_destination(
            source_device=dev,
            destination_path=r"E:\backup_invalido.img",
            confirm_token="CONFIRMAR_IMAGEM",
        )
        self.assertFalse(same_drive_check["valid"])
        self.assertEqual(same_drive_check["error_code"], "SAME_SOURCE_AND_DEST")

        dest_img = self.base_dir / "recovered_clone.img"
        run1 = create_or_resume_disk_image(
            base_dir=self.base_dir,
            source_device=dev,
            destination_image_path=str(dest_img),
            confirm_token="CONFIRMAR_IMAGEM",
            max_bytes_limit=len(raw_content),
            block_size_kb=4,
            resume=True,
            source_file_override=str(src_bin),
            simulate_bad_block_offsets=[4096],
            stop_after_blocks=2,
        )
        self.assertTrue(run1["success"])
        self.assertEqual(run1["status"], "paused_resumable")
        self.assertEqual(run1["current_offset"], 8192)
        self.assertEqual(run1["read_errors_count"], 1)

        run2 = create_or_resume_disk_image(
            base_dir=self.base_dir,
            source_device=dev,
            destination_image_path=str(dest_img),
            confirm_token="CONFIRMAR_IMAGEM",
            max_bytes_limit=len(raw_content),
            block_size_kb=4,
            resume=True,
            source_file_override=str(src_bin),
        )
        self.assertTrue(run2["success"])
        self.assertEqual(run2["status"], "completed")
        self.assertEqual(run2["resumed_from_offset"], 8192)
        self.assertEqual(run2["progress_pct"], 100.0)
        self.assertTrue(os.path.exists(run2["ddrescue_map_path"]))

        part_res = inspect_and_recover_partitions(self.base_dir, dev, image_or_target_override=str(dest_img))
        self.assertTrue(part_res["mbr_signature_valid"])

        rec_dir = self.base_dir / "carved_out"
        carve_res = recover_files_assisted(
            base_dir=self.base_dir,
            source_device=dev,
            destination_folder=str(rec_dir),
            source_override_path=str(dest_img),
        )
        self.assertTrue(carve_res["success"])
        self.assertGreaterEqual(carve_res["recovered_count"], 2)

        chk_res = execute_logical_repair(
            base_dir=self.base_dir,
            device=dev,
            drive_letter="E:",
            mode="repair_active",
            confirm_repair="CONFIRMAR_REPARO_LOGICO",
        )
        self.assertFalse(chk_res["success"])
        self.assertTrue(chk_res["blocked_by_physical_risk"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
