import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from commerce_discovery.__main__ import main
from commerce_discovery.audit import audit_page
from commerce_discovery.build import product_page
from test_catalog import sample


class AuditCliTests(unittest.TestCase):
    def call(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_baseline_generated_html_has_expected_parity(self):
        document = sample()
        report = audit_page(product_page(document["merchant"], document["products"][0]), document["products"][0])
        self.assertEqual(report["errors"], 0, report)

    def test_stock_and_price_mismatch_are_reported(self):
        document = sample()
        product = document["products"][0]
        page = product_page(document["merchant"], product)
        for changed, code in ((page.replace('"price": "18.00"', '"price": "19.00"'), "price_mismatch"),
                              (page.replace("https://schema.org/InStock", "https://schema.org/OutOfStock"), "stock_mismatch")):
            self.assertIn(code, [f["code"] for f in audit_page(changed, product)["findings"]])

    def test_noindex_missing_markup_and_duplicate_json_keys(self):
        report = audit_page('<title>Saved page</title><meta name="robots" content="noindex">')
        self.assertIn("noindex", [f["code"] for f in report["findings"]])
        self.assertIn("missing_product_jsonld", [f["code"] for f in report["findings"]])
        report = audit_page('<script type="application/ld+json">{"x":1,"x":2}</script>')
        self.assertIn("invalid_jsonld", [f["code"] for f in report["findings"]])

    def test_malformed_attribute_and_product_types_do_not_crash(self):
        raw = '<meta name><link rel><script type></script><script type="application/ld+json">{"@type":"Product","sku":[]}</script>'
        self.assertGreater(audit_page(raw, sample()["products"][0])["errors"], 0)

    def test_cli_demo_export_and_local_page_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            catalog.write_text(json.dumps(sample()))
            code, stdout, stderr = self.call(["export", str(catalog), "--format", "openai", "--demo"])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(len(stdout.splitlines()), 3)
            page = Path(directory) / "page.html"
            page.write_text(product_page(sample()["merchant"], sample()["products"][0]))
            code, stdout, stderr = self.call(["audit-page", str(page), "--catalog", str(catalog), "--id", "DEMO-MUG350-BLUE"])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["errors"], 0)

    def test_cli_invalid_and_structurally_bad_input_have_distinct_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            catalog.write_text("not json")
            code, _, stderr = self.call(["validate", str(catalog)])
            self.assertEqual(code, 2)
            self.assertIn("error", json.loads(stderr))
            catalog.write_text("{}")
            code, stdout, _ = self.call(["validate", str(catalog)])
            self.assertEqual(code, 1)
            self.assertFalse(json.loads(stdout)["valid"])

    def test_cli_protects_input_from_same_path_and_hardlink_output(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog, linked = Path(directory) / "catalog.json", Path(directory) / "hardlink.json"
            original = json.dumps(sample())
            catalog.write_text(original)
            os.link(catalog, linked)
            for output in (catalog, linked):
                code, _, stderr = self.call(["validate", str(catalog), "--out", str(output)])
                self.assertEqual(code, 2, stderr)
                self.assertEqual(catalog.read_text(), original)

    def test_strict_validation_flags_demo_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            catalog.write_text(json.dumps(sample()))
            code, _, _ = self.call(["validate", str(catalog), "--strict"])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
