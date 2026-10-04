"""Inspect saved HTML for baseline crawl signals and structured offer parity."""

from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

from .catalog import parse_json, public_url
from .exporters import AVAILABILITY_URLS


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.robots = []
        self.documents = []
        self.in_title = False
        self.in_jsonld = False
        self.script_text = ""

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if tag == "title":
            self.in_title = True
        if tag == "meta" and (values.get("name") or "").lower() == "description":
            self.description = values.get("content") or ""
        if tag == "meta" and (values.get("name") or "").lower() in {"robots", "googlebot"}:
            self.robots.append(values.get("content") or "")
        if tag == "link" and "canonical" in (values.get("rel") or "").lower().split():
            self.canonical = values.get("href") or ""
        if tag == "script" and (values.get("type") or "").lower() == "application/ld+json":
            self.in_jsonld = True
            self.script_text = ""

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.in_jsonld:
            self.documents.append(self.script_text)
            self.in_jsonld = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_jsonld:
            self.script_text += data


def _products(document):
    # Iterative traversal avoids recursion on untrusted nested JSON.
    stack, results = [document], []
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            kind = current.get("@type")
            if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
                results.append(current)
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return results


def audit_page(raw, expected=None):
    parser = PageParser()
    parser.feed(raw)
    findings = []

    def issue(severity, code, message):
        findings.append({"severity": severity, "code": code, "message": message})

    if not parser.title.strip():
        issue("error", "missing_title", "Supply a human-readable page title.")
    if not parser.description.strip():
        issue("warning", "missing_description", "Supply a factual meta description.")
    if not public_url(parser.canonical):
        issue("error", "missing_canonical", "Supply an absolute HTTPS canonical product URL.")
    if any("noindex" in text.lower().replace(",", " ").split() for text in parser.robots):
        issue("error", "noindex", "Saved HTML contains a noindex directive.")
    products = []
    for script in parser.documents:
        try:
            products.extend(_products(parse_json(script)))
        except ValueError as error:
            issue("error", "invalid_jsonld", "Malformed JSON-LD: " + str(error))
    if not products:
        issue("error", "missing_product_jsonld", "No Product JSON-LD found in saved HTML; client-side scripts are not executed.")
    for product in products:
        if not product.get("name") or not product.get("image"):
            issue("error", "missing_product_basics", "Each Product needs a name and image.")
        offers = product.get("offers")
        offers = offers if isinstance(offers, list) else [offers]
        if not offers or any(not isinstance(offer, dict) or not offer.get("priceCurrency") or "price" not in offer for offer in offers):
            issue("error", "missing_offer_basics", "Baseline offer needs price and priceCurrency.")
    if expected is not None:
        if parser.canonical != expected["url"]:
            issue("error", "canonical_mismatch", "Canonical URL differs from the catalog item.")
        matches = [p for p in products if p.get("url") == expected["url"] or
                   any(p.get("sku") == value for value in (expected["id"], expected.get("sku", expected["id"])))]
        if len(matches) != 1:
            issue("error", "ambiguous_product", "Expected exactly one matching structured Product for this catalog item.")
        else:
            product = matches[0]
            offer = product.get("offers")
            if isinstance(offer, list) and len(offer) == 1:
                offer = offer[0]
            if not isinstance(offer, dict):
                issue("error", "ambiguous_offer", "Parity audit requires one explicit offer.")
            else:
                try:
                    same_price = Decimal(str(offer.get("price"))) == Decimal(expected["price"])
                except InvalidOperation:
                    same_price = False
                if not same_price or offer.get("priceCurrency") != expected["currency"]:
                    issue("error", "price_mismatch", "Structured price/currency differs from the catalog.")
                actual_stock = offer.get("availability")
                desired_stock = AVAILABILITY_URLS.get(expected["availability"])
                if actual_stock != desired_stock:
                    issue("error", "stock_mismatch", "Structured stock status differs from the catalog; unknown must not assert in-stock.")
    errors = sum(f["severity"] == "error" for f in findings)
    return {"valid": errors == 0, "errors": errors, "warnings": len(findings) - errors,
            "products_found": len(products), "findings": findings,
            "limitations": ["Saved HTML only: no HTTP headers, robots.txt, JavaScript rendering, images or live checkout are checked.",
                            "Parity compares JSON-LD with the supplied catalog, not the visible price or a live transactional backend.",
                            "This is a baseline audit, not a full Schema.org/Google validator or a ranking prediction."]}
