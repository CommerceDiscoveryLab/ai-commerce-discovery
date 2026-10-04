import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from commerce_discovery.audit import audit_page
from commerce_discovery.build import build_catalog, page_path, product_page, robots_template
from commerce_discovery.exporters import google_export, openai_export, product_jsonld, script_json
from test_catalog import sample


class ExportBuildTests(unittest.TestCase):
    def test_jsonld_and_both_feeds_preserve_price_stock_and_identity(self):
        document = sample()
        products = document["products"]
        openai = [json.loads(row) for row in openai_export(document, demo=True).splitlines()]
        google = ET.fromstring(google_export(document, demo=True))
        items = google.findall("./channel/item")
        ns = {"g": "http://base.google.com/ns/1.0"}
        for index, product in enumerate(products):
            structured = product_jsonld(document["merchant"], product)
            self.assertEqual(structured["offers"]["price"], product["price"])
            self.assertEqual(openai[index]["item_id"], product["id"])
            self.assertEqual(openai[index]["price"], product["price"] + " USD")
            self.assertEqual(items[index].find("g:id", ns).text, product["id"])
            self.assertEqual(items[index].find("g:price", ns).text, openai[index]["price"])
        self.assertFalse(openai[0]["is_eligible_checkout"])
        self.assertFalse(openai[0]["is_ads_eligible"])
        self.assertEqual(openai[0]["variant_dict"], {"color": "Blue"})
        self.assertEqual(openai[0]["group_id"], products[0]["group_id"])

    def test_unknown_stock_never_turns_into_in_stock(self):
        document = sample()
        document["products"][0]["availability"] = "unknown"
        self.assertNotIn("availability", product_jsonld(document["merchant"], document["products"][0])["offers"])
        self.assertEqual(json.loads(openai_export(document, demo=True).splitlines()[0])["availability"], "unknown")
        with self.assertRaisesRegex(ValueError, "unknown"):
            google_export(document, demo=True)

    def test_openai_market_scope_is_explicit(self):
        document = sample()
        document["merchant"]["country"] = "CN"
        with self.assertRaisesRegex(ValueError, "US/USD"):
            openai_export(document, demo=True)

    def test_currency_and_brand_are_not_fabricated(self):
        document = sample()
        document["products"][0]["gtin"] = "09506000134352"
        structured = product_jsonld(document["merchant"], document["products"][0])
        self.assertEqual(structured["gtin14"], "09506000134352")
        self.assertNotIn("aggregateRating", structured)
        self.assertNotIn("review", structured)

    def test_html_xml_and_script_escaping(self):
        document = sample()
        payload = 'Tea & Cups "Quoted" </script><script>alert("inert")</script>'
        document["products"][0]["title"] = payload
        page = product_page(document["merchant"], document["products"][0])
        self.assertNotIn('</script><script>alert', page)
        self.assertIn("&amp;", page)
        self.assertIn("\\u003c/script", page)
        self.assertEqual(json.loads(script_json({"text": payload}))["text"], payload)
        ET.fromstring(google_export(document, demo=True))
        report = audit_page(page, document["products"][0])
        self.assertEqual(report["errors"], 0, report)

    def test_demo_build_is_safe_and_complete(self):
        document = sample()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "site"
            report = build_catalog(document, target, demo=True)
            self.assertEqual(report["products"], 3)
            self.assertTrue((target / "feeds/openai.jsonl").exists())
            self.assertTrue((target / "feeds/google.xml").exists())
            self.assertIn("Disallow: /", (target / "robots.txt").read_text())
            self.assertIn('content="noindex,nofollow"', (target / "products/mug-blue/index.html").read_text())
            self.assertTrue(json.loads((target / "BUILD_INFO.json").read_text())["demo"])
            sitemap = ET.fromstring((target / "sitemap.xml").read_text())
            self.assertEqual(len(sitemap), 3)
            for product in document["products"]:
                self.assertEqual(json.loads((target / "jsonld" / (product["id"] + ".json")).read_text())["name"], product["title"])

    def test_nonempty_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "site"
            target.mkdir()
            existing = target / "valuable.txt"
            existing.write_text("keep")
            with self.assertRaisesRegex(ValueError, "empty"):
                build_catalog(sample(), target, demo=True)
            self.assertEqual(existing.read_text(), "keep")

    def test_static_path_query_and_collision_rejected_before_writes(self):
        with self.assertRaisesRegex(ValueError, "query-selected"):
            page_path("https://shop.example.com/products/mug?color=blue")
        document = sample()
        document["products"][1]["url"] = document["products"][0]["url"] + "/index.html"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "site"
            with self.assertRaisesRegex(ValueError, "collision"):
                build_catalog(document, target, demo=True)
            self.assertFalse(target.exists())

    def test_non_us_build_omits_openai_file_instead_of_false_compatibility(self):
        document = sample()
        document["merchant"]["country"] = "CN"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "site"
            report = build_catalog(document, target, demo=True)
            self.assertIn("skipped", report["openai_feed"])
            self.assertFalse((target / "feeds/openai.jsonl").exists())

    def test_search_and_training_robot_rules_are_separate(self):
        robots = robots_template("https://shop.example.com")
        for agent in ("*", "OAI-SearchBot", "ChatGPT-User"):
            group = next(part for part in robots.split("\n\n") if "User-agent: " + agent + "\n" in part)
            self.assertIn("Disallow: /checkout", group)
            self.assertNotIn("Disallow: /\n", group)
        self.assertIn("User-agent: GPTBot\nDisallow: /", robots)
        self.assertNotIn("User-agent: GPTBot\nDisallow: /\n", robots_template("https://shop.example.com", allow_training=True))


if __name__ == "__main__":
    unittest.main()
