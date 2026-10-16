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
    ("backend.services.health_score", "backend/services/health_score.py"),
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
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

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



    def test_07_windows_on_disk_2_and_attempt_to_format_or_assign_p_blocked(self):
        """Cenário 7: Windows em C: no Disk #2 (SK hynix NVMe) — bloqueia formatação E bloqueia tentativa de atribuir P: ao Disk #2."""
        from backend.collectors.storage_advanced import collect_storage_forensics
        from backend.services.storage_recovery import (
            assign_or_change_drive_letter,
            execute_diskpart_action,
            force_unlock_and_revive_disk,
            format_and_partition_disk,
        )

        mock_raw = {
            "SystemDrive": "C:",
            "OccupiedDriveLetters": ["C:", "D:", "E:", "F:", "P:"],
            "WmiDisks": [
                {"Index": 2, "DeviceID": r"\\.\PhysicalDrive2", "Model": "PC801 NVMe SK hynix 1TB", "Manufacturer": "SK hynix", "SerialNumber": "ACE4_2E00_2649", "FirmwareRevision": "51003141", "InterfaceType": "NVMe", "MediaType": "Fixed hard disk media", "Size": 1024209543168, "Partitions": 3, "Status": "OK"},
                {"Index": 1, "DeviceID": r"\\.\PhysicalDrive1", "Model": "Samsung SSD 860 EVO 500GB", "Manufacturer": "Samsung", "SerialNumber": "S3YZNB0M548102W", "FirmwareRevision": "RVT04B6Q", "InterfaceType": "SATA", "MediaType": "Fixed hard disk media", "Size": 500107862016, "Partitions": 1, "Status": "OK"},
                {"Index": 3, "DeviceID": r"\\.\PhysicalDrive3", "Model": "JMicron Tech SCSI Disk Device", "Manufacturer": "JMicron", "SerialNumber": "000000000119", "FirmwareRevision": "4101", "InterfaceType": "USB", "MediaType": "External hard disk media", "Size": 2000398934016, "Partitions": 1, "Status": "OK"},
            ],
            "OsDisks": [
                {"Number": 2, "FriendlyName": "PC801 NVMe SK hynix 1TB", "SerialNumber": "ACE4_2E00_2649", "PartitionStyle": "GPT", "OperationalStatus": "Online", "HealthStatus": "Healthy", "BusType": "NVMe", "IsSystem": True, "IsBoot": True, "IsReadOnly": False, "IsOffline": False, "Size": 1024209543168},
                {"Number": 1, "FriendlyName": "Samsung SSD 860 EVO 500GB", "SerialNumber": "S3YZNB0M548102W", "PartitionStyle": "MBR", "OperationalStatus": "Online", "HealthStatus": "Healthy", "BusType": "SATA", "IsSystem": False, "IsBoot": False, "IsReadOnly": False, "IsOffline": False, "Size": 500107862016},
                {"Number": 3, "FriendlyName": "JMicron Tech SCSI Disk Device", "SerialNumber": "000000000119", "PartitionStyle": "GPT", "OperationalStatus": "Online", "HealthStatus": "Healthy", "BusType": "USB", "IsSystem": False, "IsBoot": False, "IsReadOnly": False, "IsOffline": False, "Size": 2000398934016},
            ],
            "Partitions": [
                {"DiskNumber": 2, "PartitionNumber": 1, "DriveLetter": "", "Size": 104857600, "Type": "System", "IsBoot": False, "IsSystem": True},
                {"DiskNumber": 2, "PartitionNumber": 2, "DriveLetter": "C", "Size": 800000000000, "Type": "Basic", "IsBoot": True, "IsSystem": False},
                {"DiskNumber": 1, "PartitionNumber": 1, "DriveLetter": "E", "Size": 500107862016, "Type": "Basic", "IsBoot": False, "IsSystem": False},
                {"DiskNumber": 3, "PartitionNumber": 1, "DriveLetter": "", "Size": 2000398934016, "Type": "Basic", "IsBoot": False, "IsSystem": False},
            ],
            "Volumes": [
                {"DriveLetter": "C", "FileSystemLabel": "OS", "FileSystem": "NTFS", "Size": 800000000000, "SizeRemaining": 200000000000},
                {"DriveLetter": "E", "FileSystemLabel": "JOGOS", "FileSystem": "NTFS", "Size": 500107862016, "SizeRemaining": 100000000000},
            ],
        }
        forensics = collect_storage_forensics(raw_override=mock_raw)
        devs_by_num = {d["disk_number"]: d for d in forensics["devices"]}
        disk2 = devs_by_num[2]
        self.assertTrue(disk2["is_system_disk"])
        self.assertTrue(disk2["contains_windows_volume"])
        self.assertTrue(disk2["is_protected_from_destruction"])

        # 1. Tentativa de formatar Disk #2 deve ser bloqueada e retornar disk_number=2
        res_fmt = format_and_partition_disk(self.base_dir, disk2, filesystem="NTFS", confirm_token="FORMATAR")
        self.assertFalse(res_fmt["success"])
        self.assertTrue(res_fmt.get("blocked_system_disk"))
        self.assertEqual(res_fmt.get("disk_number"), 2)

        # 2. Tentativa de atribuir a letra P: ao Disk #2 deve ser bloqueada!
        res_let = assign_or_change_drive_letter(self.base_dir, disk2, desired_letter="P")
        self.assertFalse(res_let["success"])
        self.assertTrue(res_let.get("blocked_system_disk"))
        self.assertEqual(res_let.get("error_code"), "PROTECTED_SYSTEM_OR_BOOT_DISK")

        # 3. Tentativa de desbloqueio/montagem forçada no Disk #2 deve ser bloqueada!
        res_unl = force_unlock_and_revive_disk(self.base_dir, disk2)
        self.assertFalse(res_unl["success"])
        self.assertTrue(res_unl.get("blocked_system_disk"))

        # 4. Tentativa de clean_disk no Disk #2 deve ser bloqueada!
        res_cln = execute_diskpart_action(self.base_dir, disk2, action="clean_disk", confirm_token="CONFIRMAR")
        self.assertFalse(res_cln["success"])
        self.assertTrue(res_cln.get("blocked_system_disk"))

    def test_08_disk_renumbering_after_reboot_and_confirmation_reuse_blocked(self):
        """Cenário 8: Numeração de discos alterada após reinicialização e impedimento de reutilizar confirmação de um disco em outro."""
        from backend.services.storage_recovery import format_and_partition_disk

        usb_disk = {
            "device_uid": "JMICRON_2TB_0119",
            "hardware_identity_hash": "ABCD1234EFGH5678",
            "disk_number": 3,
            "model": "JMicron Tech SCSI Disk Device",
            "serial_number": "000000000119",
            "capacity": {"bytes": 2000398934016, "formatted": "2.0 TB"},
            "partitions_count": 1,
            "partitions": [{"partition_number": 1, "drive_letter": "Sem Letra", "filesystem": "EXFAT", "partition_role": "DATA_VOLUME", "capacity": {"bytes": 2000398934016}}],
            "drive_letters": [],
            "is_system_disk": False,
            "_mock_execution": True,
        }

        # Se o chamador pedir Disk #1 mas o objeto é Disk #3 (renumeração pós-boot), deve bloquear!
        res_renum = format_and_partition_disk(
            self.base_dir,
            usb_disk,
            requested_disk_number=1,
            requested_device_uid="JMICRON_2TB_0119",
            confirm_token="FORMATAR",
        )
        self.assertFalse(res_renum["success"])
        self.assertEqual(res_renum["error_code"], "DISK_NUMBER_MISMATCH")

        # Se tentar reutilizar token ou UID de confirmação emitido para outro disco (ex: FORMATAR_DISK_1 ou confirm_device_uid diferente), deve bloquear!
        res_reuse_tok = format_and_partition_disk(
            self.base_dir,
            usb_disk,
            requested_disk_number=3,
            confirm_token="FORMATAR_DISK_1",
        )
        self.assertFalse(res_reuse_tok["success"])
        self.assertEqual(res_reuse_tok["error_code"], "CONFIRMATION_TARGET_MISMATCH")

        res_reuse_uid = format_and_partition_disk(
            self.base_dir,
            usb_disk,
            requested_disk_number=3,
            confirm_token="FORMATAR",
            confirm_device_uid="SAMSUNG_860_EVO_500GB",
        )
        self.assertFalse(res_reuse_uid["success"])
        self.assertEqual(res_reuse_uid["error_code"], "CONFIRMATION_TARGET_MISMATCH")

    def test_09_cross_disk_efi_boot_partition_protection(self):
        """Cenário 9: Partição EFI em um disco diferente do volume C: (ambos os discos devem ser protegidos contra formatação/limpeza)."""
        from backend.collectors.storage_advanced import collect_storage_forensics
        from backend.services.storage_recovery import format_and_partition_disk

        mock_split_boot = {
            "SystemDrive": "C:",
            "WmiDisks": [
                {"Index": 0, "DeviceID": r"\\.\PhysicalDrive0", "Model": "Samsung SSD 860 EVO 500GB", "SerialNumber": "SAM001", "Size": 500107862016},
                {"Index": 2, "DeviceID": r"\\.\PhysicalDrive2", "Model": "PC801 NVMe SK hynix 1TB", "SerialNumber": "HYN002", "Size": 1024209543168},
            ],
            "OsDisks": [
                {"Number": 0, "FriendlyName": "Samsung SSD 860 EVO 500GB", "SerialNumber": "SAM001", "PartitionStyle": "GPT", "IsSystem": True, "IsBoot": False, "Size": 500107862016},
                {"Number": 2, "FriendlyName": "PC801 NVMe SK hynix 1TB", "SerialNumber": "HYN002", "PartitionStyle": "GPT", "IsSystem": False, "IsBoot": True, "Size": 1024209543168},
            ],
            "Partitions": [
                # Partição EFI está no Disk #0!
                {"DiskNumber": 0, "PartitionNumber": 1, "DriveLetter": "", "Size": 104857600, "Type": "System", "IsSystem": True, "IsBoot": False},
                {"DiskNumber": 0, "PartitionNumber": 2, "DriveLetter": "E", "Size": 499000000000, "Type": "Basic", "IsSystem": False, "IsBoot": False},
                # Volume C: do Windows está no Disk #2!
                {"DiskNumber": 2, "PartitionNumber": 1, "DriveLetter": "C", "Size": 1024000000000, "Type": "Basic", "IsSystem": False, "IsBoot": True},
            ],
            "Volumes": [
                {"DriveLetter": "C", "FileSystem": "NTFS", "Size": 1024000000000, "SizeRemaining": 400000000000},
                {"DriveLetter": "E", "FileSystem": "NTFS", "Size": 499000000000, "SizeRemaining": 200000000000},
            ],
        }
        forensics = collect_storage_forensics(raw_override=mock_split_boot)
        by_num = {d["disk_number"]: d for d in forensics["devices"]}
        disk0_efi = by_num[0]
        disk2_win = by_num[2]

        self.assertTrue(disk0_efi["contains_efi_boot_partition"])
        self.assertTrue(disk0_efi["is_protected_from_destruction"])
        self.assertTrue(disk2_win["contains_windows_volume"])
        self.assertTrue(disk2_win["is_protected_from_destruction"])

        # Formatar Disk #0 (que contém a partição EFI de inicialização, mesmo sem ter C:) deve ser BLOQUEADO!
        res0 = format_and_partition_disk(self.base_dir, disk0_efi, confirm_token="FORMATAR")
        self.assertFalse(res0["success"])
        self.assertTrue(res0.get("blocked_system_disk"))
        self.assertEqual(res0["error_code"], "PROTECTED_SYSTEM_OR_BOOT_DISK")

    def test_10_occupied_drive_letter_p_conflict_and_partitionless_disk(self):
        """Cenário 10: Letra P: já ocupada no sistema, volume sem letra elegível e bloqueio em disco sem partição ou RAW."""
        from backend.services.storage_recovery import assign_or_change_drive_letter

        usb_with_part = {
            "device_uid": "JMICRON_2TB_0119",
            "disk_number": 3,
            "model": "JMicron Tech SCSI Disk Device",
            "serial_number": "000000000119",
            "capacity": {"bytes": 2000398934016, "formatted": "2.0 TB"},
            "partitions_count": 1,
            "partitions": [{
                "partition_number": 1,
                "drive_letter": "Sem Letra",
                "filesystem": "EXFAT",
                "partition_role": "DATA_VOLUME",
                "is_raw": False,
                "capacity": {"bytes": 2000398934016},
            }],
            "drive_letters": [],
            "is_system_disk": False,
            "_mock_execution": True,
        }

        # 1. Tentativa de atribuir letra P: quando P: já está ocupada no sistema deve ser bloqueada!
        res_occ = assign_or_change_drive_letter(
            self.base_dir,
            usb_with_part,
            desired_letter="P",
            occupied_drive_letters=["C:", "D:", "E:", "P:"],
        )
        self.assertFalse(res_occ["success"])
        self.assertEqual(res_occ["error_code"], "DRIVE_LETTER_ALREADY_OCCUPIED")

        # 2. Atribuir letra livre (ex: R:) ao volume sem letra deve funcionar!
        res_free = assign_or_change_drive_letter(
            self.base_dir,
            usb_with_part,
            desired_letter="R",
            occupied_drive_letters=["C:", "D:", "E:", "P:"],
        )
        self.assertTrue(res_free["success"])
        self.assertIn("assign letter=R", res_free["diskpart_output"])

        # 3. Disco físico sem partições (0 partições) não pode receber letra diretamente!
        disk_no_parts = dict(usb_with_part, partitions=[], partitions_count=0)
        res_nop = assign_or_change_drive_letter(self.base_dir, disk_no_parts, desired_letter="R")
        self.assertFalse(res_nop["success"])
        self.assertEqual(res_nop["error_code"], "NO_PARTITION_AVAILABLE")

        # 4. Partição em estado RAW não deve receber atribuição cega de letra como se estivesse íntegra!
        disk_raw_part = dict(usb_with_part, partitions=[{
            "partition_number": 1,
            "drive_letter": "Sem Letra",
            "filesystem": "RAW",
            "partition_role": "DATA_VOLUME",
            "is_raw": True,
            "capacity": {"bytes": 2000398934016},
        }])
        res_raw = assign_or_change_drive_letter(self.base_dir, disk_raw_part, desired_letter="R")
        self.assertFalse(res_raw["success"])
        self.assertEqual(res_raw["error_code"], "RAW_VOLUME_CANNOT_ASSIGN_LETTER")

    def test_11_offline_readonly_and_ambiguous_target_identity_blocked(self):
        """Cenário 11: Disco offline/somente-leitura elegível vs bloqueio de destino com identidade ambígua."""
        from backend.services.storage_recovery import force_unlock_and_revive_disk, format_and_partition_disk

        # 1. Destino ambíguo (sem serial ou modelo Unknown ou capacidade 0) deve ser bloqueado!
        ambiguous_disk = {
            "device_uid": "DISK_3",
            "disk_number": 3,
            "model": "Unknown",
            "serial_number": "N/D",
            "capacity": {"bytes": 0},
            "is_ambiguous_identity": True,
            "is_system_disk": False,
        }
        res_amb = format_and_partition_disk(self.base_dir, ambiguous_disk, confirm_token="FORMATAR")
        self.assertFalse(res_amb["success"])
        self.assertEqual(res_amb["error_code"], "AMBIGUOUS_TARGET_IDENTITY")

        # 2. Disco secundário bem identificado que está Offline/Read-Only pode ser desbloqueado com segurança
        offline_usb = {
            "device_uid": "JMICRON_2TB_0119",
            "disk_number": 3,
            "model": "JMicron Tech SCSI Disk Device",
            "serial_number": "000000000119",
            "capacity": {"bytes": 2000398934016, "formatted": "2.0 TB"},
            "is_online": False,
            "is_read_only": True,
            "is_system_disk": False,
            "_mock_execution": True,
        }
        res_unl = force_unlock_and_revive_disk(self.base_dir, offline_usb)
        self.assertTrue(res_unl["success"])

    def test_12_disk_removed_or_changed_between_validation_and_execution(self):
        """Cenário 12: Disco removido ou alterado entre a validação e a execução é abortado pela revalidação live."""
        from backend.services.storage_recovery import format_and_partition_disk

        target_disk = {
            "device_uid": "JMICRON_2TB_0119",
            "disk_number": 3,
            "model": "JMicron Tech SCSI Disk Device",
            "serial_number": "000000000119",
            "capacity": {"bytes": 2000398934016, "formatted": "2.0 TB"},
            "partitions_count": 1,
            "partitions": [{"partition_number": 1, "capacity": {"bytes": 2000398934016}}],
            "drive_letters": [],
            "is_system_disk": False,
            "_mock_execution": True,
        }

        # 1. Disco foi desconectado antes do comando (lista live não contém mais Disk #3)
        res_removed = format_and_partition_disk(
            self.base_dir,
            target_disk,
            confirm_token="FORMATAR",
            live_devices_snapshot=[{"disk_number": 2, "model": "PC801 NVMe SK hynix 1TB", "serial_number": "ACE4", "capacity": {"bytes": 1024209543168}}],
        )
        self.assertFalse(res_removed["success"])
        self.assertEqual(res_removed["error_code"], "DISK_REMOVED_BEFORE_EXECUTION")

        # 2. Disk #3 mudou de identidade antes da execução (outro disco assumiu o número 3!)
        res_changed = format_and_partition_disk(
            self.base_dir,
            target_disk,
            confirm_token="FORMATAR",
            live_devices_snapshot=[{"disk_number": 3, "model": "Kingston DataTraveler 64GB", "serial_number": "KNG64", "capacity": {"bytes": 64000000000}}],
        )
        self.assertFalse(res_changed["success"])
        self.assertEqual(res_changed["error_code"], "DISK_IDENTITY_CHANGED_BEFORE_EXECUTION")

    def test_13_direct_backend_api_bypass_attempt_blocked(self):
        """Cenário 13: Tentativa de contornar a trava por chamada direta ao backend sem UID válido ou mirando no disco do Windows."""
        from backend.server import SESSION_STATE, _resolve_storage_device_strict
        from backend.services.storage_recovery import format_and_partition_disk

        SESSION_STATE["last_snapshot"] = {
            "storage_suite": {
                "occupied_drive_letters": ["C:", "F:"],
                "devices": [
                    {
                        "device_uid": "PC801_NVME_SK_HYNIX_1TB_ACE4",
                        "disk_number": 2,
                        "model": "PC801 NVMe SK hynix 1TB",
                        "serial_number": "ACE4",
                        "capacity": {"bytes": 1024209543168},
                        "drive_letters": ["C:", "F:"],
                        "is_system_disk": True,
                        "contains_windows_volume": True,
                    }
                ],
            }
        }
        # Se um cliente chamar o backend passando um UID inexistente e disk_number=None, _resolve_storage_device_strict NUNCA retorna devs[0] (Disk #2)!
        dev_resolved, _ = _resolve_storage_device_strict(disk_number=None, device_uid="UID_INEXISTENTE")
        self.assertIsNone(dev_resolved)

        res_null = format_and_partition_disk(self.base_dir, dev_resolved, confirm_token="FORMATAR")
        self.assertFalse(res_null["success"])
        self.assertEqual(res_null["error_code"], "TARGET_NOT_FOUND")

    def test_14_volume_enumeration_timeout_and_vds_service_unavailable(self):
        """Cenário 14: Timeout na enumeração de volumes e falha do VDS geram diagnóstico do diskmgmt.msc e bloqueiam ações destrutivas."""
        from backend.collectors.storage_advanced import collect_storage_forensics
        from backend.services.storage_recovery import format_and_partition_disk

        mock_vds_timeout = {
            "SystemDrive": "C:",
            "VolumeEnumerationTimeout": True,
            "ServiceUnavailable": True,
            "QueryTelemetry": {
                "wmi_duration_ms": 140,
                "vds_duration_ms": 5012,
                "vds_timeout_reached": True,
                "services": [{"Name": "vds", "Status": "StopPending", "StartType": "Manual"}],
                "active_storage_processes": [{"Name": "diskpart", "Id": 4412}, {"Name": "smartctl", "Id": 8820}],
            },
            "WmiDisks": [
                {"Index": 2, "DeviceID": r"\\.\PhysicalDrive2", "Model": "PC801 NVMe SK hynix 1TB", "SerialNumber": "ACE4", "Size": 1024209543168},
                {"Index": 3, "DeviceID": r"\\.\PhysicalDrive3", "Model": "JMicron Tech SCSI Disk Device", "SerialNumber": "000000000119", "Size": 2000398934016},
            ],
            "PhysicalDisks": [],
            "OsDisks": [],
            "Partitions": [],
            "Volumes": [],
            "DiskEvents": [{"Id": 153, "Message": "The IO operation at logical block address 0x0 for Disk 3 was retried."}],
        }
        forensics = collect_storage_forensics(raw_override=mock_vds_timeout)
        diag = forensics["diskmgmt_diagnostics"]
        self.assertEqual(diag["status"], "degraded_or_blocked")
        self.assertTrue(diag["vds_timeout_reached"])

        # Qualquer tentativa de formatar um disco enquanto a enumeração de volumes está em timeout deve ser bloqueada!
        disk3 = next(d for d in forensics["devices"] if d["disk_number"] == 3)
        res_fmt = format_and_partition_disk(
            self.base_dir,
            disk3,
            confirm_token="FORMATAR",
            query_telemetry=forensics["query_telemetry"],
        )
        self.assertFalse(res_fmt["success"])
        self.assertEqual(res_fmt["error_code"], "VDS_OR_VOLUME_ENUMERATION_TIMEOUT")

    def test_15_device_io_error_and_timeout_aborts_intensive_test(self):
        """Cenário 15: Erro de I/O ou timeout do dispositivo interrompe testes intensivos e recomenda backup."""
        from backend.services.storage_diagnostics import run_storage_integrity_test

        faulty_usb = {
            "device_uid": "JMICRON_IO_TIMEOUT",
            "disk_number": 3,
            "model": "JMicron Tech SCSI Disk Device",
            "serial_number": "000000000119",
            "capacity": {"bytes": 2000398934016},
            "smart_summary": {"pending_sectors": 7},
            "_simulate_io_timeout": True,
        }
        res = run_storage_integrity_test(self.base_dir, faulty_usb, test_type="surface_scan")
        self.assertFalse(res["success"])
        self.assertTrue(res.get("aborted_by_io_error"))
        self.assertIn("backup", res.get("recommendation", "").lower())

    def test_16_initializer_missing_dependencies_and_occupied_port(self):
        """Cenário 16: Inicialização do AegisPulse com porta 8765 ocupada (fallback automático) e verificação de dependências."""
        import socket
        from main import select_available_port, verify_runtime_dependencies

        deps = verify_runtime_dependencies(auto_install=False)
        self.assertIn("ok", deps)
        self.assertIn("python_version", deps)

        # Simula uma porta ocupada abrindo um socket temporário e verifica se select_available_port escolhe a próxima porta livre!
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv_sock:
            srv_sock.bind(("127.0.0.1", 0))
            srv_sock.listen(1)
            busy_port = srv_sock.getsockname()[1]
            chosen_port, used_fallback = select_available_port("127.0.0.1", preferred_port=busy_port)
            self.assertTrue(used_fallback)
            self.assertNotEqual(chosen_port, busy_port)


if __name__ == "__main__":
    unittest.main()
