from __future__ import annotations

from contextlib import redirect_stderr
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.validate_quasar_release import (
    EDITION_IDS,
    EDITION_LABELS,
    validate_android_report,
)


class AndroidReportValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.report_path = Path(self.temp_directory.name) / "apk-verification.json"
        signer = "a" * 64
        self.report = []
        for edition in EDITION_IDS:
            abis = {
                abi: ["libexample.so"]
                for abi in ("arm64-v8a", "armeabi-v7a", "x86", "x86_64")
            }
            self.report.append(
                {
                    "edition": edition,
                    "applicationLabel": EDITION_LABELS[edition],
                    "applicationId": "com.quasar.mobile",
                    "version": "0.4.0",
                    "versionCode": 6,
                    "minSdk": 26,
                    "targetSdk": 35,
                    "sha256": edition.encode().hex().ljust(64, "0"),
                    "signerSHA256": signer,
                    "sameSignerAs032": True,
                    "abis": abis,
                    "zipalign16KB": True,
                    "native16KBStaticCompatible": True,
                    "nativeLibraries": [
                        {
                            "file": f"lib/{abi}/libexample.so",
                            "abi": abi,
                            "load16KB": True,
                            "relro16KB": True,
                        }
                        for abi in abis
                    ],
                }
            )

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def write_report(self, report: list[dict[str, object]]) -> None:
        self.report_path.write_text(json.dumps(report), encoding="utf-8")

    def assert_rejected(self, report: list[dict[str, object]]) -> None:
        self.write_report(report)
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                validate_android_report(self.report_path)

    def test_accepts_complete_passing_report(self) -> None:
        self.write_report(self.report)
        validate_android_report(self.report_path)

    def test_rejects_failed_aggregate_alignment(self) -> None:
        report = copy.deepcopy(self.report)
        report[0]["zipalign16KB"] = False
        self.assert_rejected(report)

    def test_rejects_failed_native_library(self) -> None:
        report = copy.deepcopy(self.report)
        report[0]["nativeLibraries"][0]["relro16KB"] = False
        self.assert_rejected(report)

    def test_rejects_inconsistent_signer(self) -> None:
        report = copy.deepcopy(self.report)
        report[0]["signerSHA256"] = "b" * 64
        self.assert_rejected(report)

    def test_rejects_missing_edition(self) -> None:
        self.assert_rejected(self.report[:-1])


if __name__ == "__main__":
    unittest.main()
