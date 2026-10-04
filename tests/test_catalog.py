import copy
import unittest
from datetime import datetime, timezone
from pathlib import Path

from commerce_discovery.catalog import (load_catalog, parse_json, public_url, require_catalog,
                                        valid_gtin, validate_catalog)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def sample():
    return load_catalog(ROOT / "examples/catalog.demo.json")


class CatalogTests(unittest.TestCase):
    def assert_code(self, document, code):
        report = validate_catalog(document, now=NOW)
        self.assertIn(code, [item["code"] for item in report["findings"]])
        return report

    def test_demo_valid_with_explicit_warnings(self):
        report = validate_catalog(sample(), now=NOW)
        self.assertEqual(report["errors"], 0)
        self.assertEqual(report["products_checked"], 3)
        self.assertGreater(report["warnings"], 0)
        self.assert_code(sample(), "demo_catalog")

    def test_production_export_rejects_unacknowledged_demo(self):
        with self.assertRaisesRegex(ValueError, "--demo"):
            require_catalog(sample())

    def test_marking_demo_false_does_not_allow_placeholder_urls(self):
        document = sample()
        document["demo"] = False
        with self.assertRaisesRegex(ValueError, "reserved URLs"):
            require_catalog(document)

    def test_duplicate_and_missing_ids(self):
        document = sample()
        document["products"][1]["id"] = document["products"][0]["id"]
        self.assert_code(document, "duplicate_id")
        del document["products"][0]["id"]
        self.assert_code(document, "missing_field")

    def test_identity_stays_separate_from_offer_price(self):
        document = sample()
        old_id = document["products"][0]["id"]
        document["products"][0]["price"] = "19.00"
        self.assertEqual(validate_catalog(document, now=NOW)["errors"], 0)
        self.assertEqual(document["products"][0]["id"], old_id)

    def test_bad_money_values_and_precision(self):
        for price in (0, "0", "NaN", "1e3", "-1", "1,000", " 18", "18 USD", "0.00000", "18.001"):
            document = sample()
            document["products"][0]["price"] = price
            with self.subTest(price=price):
                self.assertGreater(validate_catalog(document, now=NOW)["errors"], 0)
        document = sample()
        document["products"][0].update(price="1800.50", currency="JPY")
        self.assert_code(document, "currency_precision")

    def test_stock_not_guessed_and_dates_required(self):
        document = sample()
        document["products"][0]["availability"] = "unknown"
        self.assert_code(document, "unknown_availability")
        for stock in ("pre_order", "backorder"):
            document["products"][0]["availability"] = stock
            self.assert_code(document, "availability_date_missing")
        document["products"][0]["availability_date"] = "2026-10-15T12:00:00Z"
        self.assertEqual(validate_catalog(document, now=NOW)["errors"], 0)

    def test_freshness_future_and_timezone_checks(self):
        for value, code in (("2026-09-30T00:00:00Z", "stale_snapshot"),
                            ("2026-10-05T00:00:00Z", "future_update"),
                            ("2026-10-04T00:00:00", "invalid_timestamp"),
                            ("2026-02-30T00:00:00Z", "invalid_timestamp")):
            document = sample()
            document["products"][0]["updated_at"] = value
            self.assert_code(document, code)

    def test_gtin_checksum_and_string_preservation(self):
        self.assertTrue(valid_gtin("09506000134352"))
        for value in (9506000134352, "09506000134353", "123", "0950 6000134352"):
            self.assertFalse(valid_gtin(value))
        document = sample()
        document["products"][0]["gtin"] = "09506000134353"
        self.assert_code(document, "invalid_gtin")

    def test_identifier_absence_not_silently_inferred(self):
        document = sample()
        del document["products"][0]["mpn"]
        self.assert_code(document, "identifier_missing")
        self.assertNotIn("identifier_exists", document["products"][0])
        document["products"][0]["identifier_exists"] = False
        self.assertNotIn("identifier_missing", [f["code"] for f in validate_catalog(document, now=NOW)["findings"]])
        document["products"][0]["gtin"] = "09506000134352"
        self.assert_code(document, "identifier_conflict")

    def test_variants_have_consistent_keys_unique_selections_and_groups(self):
        for change, code in (({"color": "Blue"}, "duplicate_variant"), ({"size": "Large"}, "variant_keys_mismatch")):
            document = sample()
            document["products"][1]["variant"] = change
            self.assert_code(document, code)
        document = sample()
        document["products"][0]["attributes"]["color"] = "Red"
        self.assert_code(document, "variant_attribute_conflict")
        document = sample()
        del document["products"][0]["group_id"]
        self.assert_code(document, "incomplete_variant")

    def test_url_guard_blocks_credentials_local_hosts_and_traversal(self):
        for url in ("file:///etc/passwd", "https://user:pass@shop.example.com", "https://localhost/item",
                    "https://127.0.0.1/item", "https://192.168.1.10/item", "https://[::1]/item",
                    "javascript:alert(1)", "https://shop.example.com/a/%2e%2e/private", "https://shop.example.com/a\\b",
                    "https://shop.example.com:invalid/item", "https://shop.example.com/item#different"):
            with self.subTest(url=url):
                self.assertFalse(public_url(url))
        self.assertTrue(public_url("https://shop.example.com/products/mug?color=blue"))

    def test_cross_merchant_urls_rejected(self):
        document = sample()
        document["products"][0]["url"] = "https://another.example.com/products/mug"
        self.assert_code(document, "different_merchant_origin")

    def test_malformed_types_do_not_crash(self):
        for value in (None, [], True, {1: "bad"}, {}):
            with self.subTest(value=value):
                self.assertGreater(validate_catalog(value, now=NOW)["errors"], 0)
        for field, value in (("price", []), ("currency", {}), ("availability", []), ("brand", False),
                             ("variant", []), ("group_id", {}), ("attributes", []), ("updated_at", None)):
            document = sample()
            document["products"][0][field] = value
            with self.subTest(field=field):
                self.assertGreater(validate_catalog(document, now=NOW)["errors"], 0)

    def test_untrusted_json_rejects_duplicates_and_nonfinite_numbers(self):
        for raw in ('{"id":1,"id":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError):
                parse_json(raw)

    def test_no_html_in_product_description_and_input_unchanged(self):
        document = sample()
        document["products"][0]["description"] = "<b>Claim</b>"
        original = copy.deepcopy(document)
        self.assert_code(document, "description_html")
        self.assertEqual(document, original)


if __name__ == "__main__":
    unittest.main()
