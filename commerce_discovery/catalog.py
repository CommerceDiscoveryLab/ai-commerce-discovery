"""Validate a merchant's factual product snapshot without downloading URLs."""

import ipaddress
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlsplit


AVAILABILITY = {"in_stock", "out_of_stock", "pre_order", "backorder", "unknown"}
CONDITIONS = {"new", "used", "refurbished"}
VARIANT_KEYS = {"color", "size", "material", "pattern"}
MERCHANT_REQUIRED = {"name", "url", "country", "language"}
MERCHANT_OPTIONAL = {"support_url", "shipping_policy_url", "return_policy_url", "privacy_policy_url", "terms_url"}
PRODUCT_REQUIRED = {"id", "title", "description", "url", "image_url", "brand", "price", "currency",
                    "availability", "condition", "updated_at"}
PRODUCT_OPTIONAL = {"sku", "gtin", "mpn", "identifier_exists", "additional_images", "category", "group_id",
                    "variant", "attributes", "availability_date"}
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,49}$")
PRICE_PATTERN = re.compile(r"^(?:0|[1-9][0-9]{0,14})(?:\.[0-9]{1,4})?$")
CURRENCY_DECIMALS = {"USD": 2, "CNY": 2, "EUR": 2, "GBP": 2, "AUD": 2, "CAD": 2,
                     "HKD": 2, "SGD": 2, "JPY": 0, "KRW": 0, "KWD": 3, "BHD": 3}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError("non-finite JSON number: " + value)


def parse_json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    except RecursionError as error:
        raise ValueError("JSON nesting exceeds parser limits") from error


def load_catalog(path):
    return parse_json(Path(path).read_text(encoding="utf-8"))


def timestamp(value):
    if not isinstance(value, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T", value):
        raise ValueError("expected ISO 8601 timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("invalid ISO 8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("timestamp needs a timezone")
    return parsed.astimezone(timezone.utc)


def valid_gtin(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9]{8}|[0-9]{12}|[0-9]{13}|[0-9]{14})", value):
        return False
    weighted = sum(int(digit) * (3 if i % 2 == 0 else 1) for i, digit in enumerate(reversed(value[:-1])))
    return (10 - weighted % 10) % 10 == int(value[-1])


def public_url(value):
    """A syntax guard; it never authenticates ownership or public reachability."""
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname or parts.username is not None
                or parts.password is not None or parts.fragment or "\\" in value):
            return False
        parts.port
        host = parts.hostname.lower()
        if host == "localhost" or host.endswith((".localhost", ".local")) or "." not in host:
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            pass
        decoded = unquote(parts.path)
        if any(segment in {"..", "."} for segment in decoded.split("/")) or "\\" in decoded or "\x00" in decoded:
            return False
        return True
    except (ValueError, UnicodeError):
        return False


def placeholder_url(value):
    host = (urlsplit(value).hostname or "").lower()
    return host in {"example.com", "example.org", "example.net"} or host.endswith(
        (".example.com", ".example.org", ".example.net", ".example", ".invalid", ".test"))


def validate_catalog(document, now=None, max_age_hours=48):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("validation clock must have a timezone")
    if not isinstance(max_age_hours, (int, float)) or isinstance(max_age_hours, bool) or not 0 < max_age_hours <= 87600:
        raise ValueError("max_age_hours must be positive and at most 87600")
    findings = []

    def issue(severity, code, path, message):
        findings.append({"severity": severity, "code": code, "path": path, "message": message})

    def shape(value, required, optional, path):
        if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
            issue("error", "object_required", path, "Must be an object.")
            return False
        missing, extra = required - set(value), set(value) - required - optional
        for key in sorted(missing):
            issue("error", "missing_field", path + "." + key, "Required field is missing.")
        for key in sorted(extra):
            issue("error", "unknown_field", path + "." + key, "Unknown field; use the documented catalog contract.")
        return True

    def text(value, path, maximum):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            issue("error", "invalid_text", path, "Must be nonblank text of at most {} characters.".format(maximum))
            return False
        if any(ord(c) < 32 and c not in "\n\t" for c in value):
            issue("error", "control_character", path, "Unsupported control character.")
            return False
        return True

    def url(value, path):
        if not public_url(value):
            issue("error", "invalid_url", path, "Use an absolute HTTPS URL without credentials, fragments, local hosts or unsafe paths.")
            return False
        if placeholder_url(value):
            issue("warning", "placeholder_url", path, "Example/reserved URL; replace before production use.")
        return True

    if not shape(document, {"schema_version", "demo", "merchant", "products"}, set(), "catalog"):
        return _report(findings, 0)
    if document.get("schema_version") != "1.0":
        issue("error", "unsupported_version", "schema_version", "Use catalog schema_version 1.0.")
    if type(document.get("demo")) is not bool:
        issue("error", "invalid_demo", "demo", "Must be a boolean.")
    elif document["demo"]:
        issue("warning", "demo_catalog", "demo", "Synthetic demonstration only; exports require an explicit --demo flag.")
    merchant = document.get("merchant")
    merchant_origin = None
    if shape(merchant, MERCHANT_REQUIRED, MERCHANT_OPTIONAL, "merchant"):
        text(merchant.get("name"), "merchant.name", 200)
        if url(merchant.get("url"), "merchant.url"):
            merchant_origin = urlsplit(merchant["url"])
            if merchant_origin.path not in {"", "/"} or merchant_origin.query:
                issue("error", "merchant_origin", "merchant.url", "Merchant URL must be a site origin, with no path or query.")
        if not isinstance(merchant.get("country"), str) or not re.fullmatch(r"[A-Z]{2}", merchant["country"]):
            issue("error", "country_format", "merchant.country", "Use a two-letter uppercase country code.")
        if not isinstance(merchant.get("language"), str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", merchant["language"]):
            issue("error", "language_format", "merchant.language", "Use a language tag such as en-US or zh-CN.")
        for key in MERCHANT_OPTIONAL:
            if key in merchant:
                url(merchant[key], "merchant." + key)
        for key in ("shipping_policy_url", "return_policy_url", "support_url"):
            if key not in merchant:
                issue("warning", "missing_merchant_context", "merchant." + key, "Provide this merchant context to help shoppers verify terms.")
    products = document.get("products")
    if not isinstance(products, list) or not 1 <= len(products) <= 50000:
        issue("error", "products_required", "products", "Supply between 1 and 50000 product records.")
        return _report(findings, 0)
    ids, skus, urls, groups = set(), set(), set(), {}
    for index, product in enumerate(products):
        path = "products[{}]".format(index)
        if not shape(product, PRODUCT_REQUIRED, PRODUCT_OPTIONAL, path):
            continue
        for key, maximum in (("id", 50), ("title", 150), ("description", 5000), ("brand", 100)):
            text(product.get(key), path + "." + key, maximum)
        identifier = product.get("id")
        if not isinstance(identifier, str) or not ID_PATTERN.fullmatch(identifier):
            issue("error", "invalid_id", path + ".id", "Use 1-50 ASCII letters, digits, underscores or hyphens; start with a letter or digit.")
        elif identifier in ids:
            issue("error", "duplicate_id", path + ".id", "Item IDs must be unique and stable.")
        else:
            ids.add(identifier)
        for key in ("url", "image_url"):
            valid = url(product.get(key), path + "." + key)
            if key == "url" and valid:
                parts = urlsplit(product[key])
                if merchant_origin and (parts.hostname, parts.port) != (merchant_origin.hostname, merchant_origin.port):
                    issue("error", "different_merchant_origin", path + ".url", "Product URLs must belong to the merchant site.")
                if product[key] in urls:
                    issue("error", "duplicate_product_url", path + ".url", "Each item needs a distinct product/selected-variant URL.")
                urls.add(product[key])
        if "additional_images" in product:
            images = product["additional_images"]
            if not isinstance(images, list) or len(images) > 10:
                issue("error", "invalid_images", path + ".additional_images", "Use an array of at most ten image URLs.")
            else:
                for image_index, image in enumerate(images):
                    url(image, path + ".additional_images[{}]".format(image_index))
        price = product.get("price")
        if not isinstance(price, str) or not PRICE_PATTERN.fullmatch(price) or Decimal(price) <= 0:
            issue("error", "invalid_price", path + ".price", "Use a positive decimal string without currency, separators or exponents; at most four decimal places.")
        currency = product.get("currency")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            issue("error", "currency_format", path + ".currency", "Use a three-letter uppercase currency code.")
        elif currency not in CURRENCY_DECIMALS:
            issue("error", "unsupported_currency", path + ".currency", "This release supports only the currency codes documented in the catalog contract.")
        elif isinstance(price, str) and PRICE_PATTERN.fullmatch(price):
            precision = len(price.partition(".")[2])
            if precision > CURRENCY_DECIMALS[currency]:
                issue("error", "currency_precision", path + ".price", "Price has more decimal places than this currency permits; no automatic rounding is performed.")
        availability = product.get("availability")
        if not isinstance(availability, str) or availability not in AVAILABILITY:
            issue("error", "invalid_availability", path + ".availability", "Unsupported availability value.")
        elif availability == "unknown":
            issue("warning", "unknown_availability", path + ".availability", "Stock is unknown; Google export cannot represent this value.")
        condition = product.get("condition")
        if not isinstance(condition, str) or condition not in CONDITIONS:
            issue("error", "invalid_condition", path + ".condition", "Use new, used or refurbished.")
        try:
            observed = timestamp(product.get("updated_at"))
            if observed > now + timedelta(minutes=5):
                issue("error", "future_update", path + ".updated_at", "Product observation time cannot be in the future.")
            elif now - observed > timedelta(hours=max_age_hours):
                issue("warning", "stale_snapshot", path + ".updated_at", "Refresh price and stock; this snapshot exceeds the configured freshness threshold.")
        except ValueError as error:
            issue("error", "invalid_timestamp", path + ".updated_at", str(error))
        for key in ("sku", "mpn", "category"):
            if key in product:
                valid = text(product[key], path + "." + key, 200 if key == "category" else 70)
                if key == "sku" and valid:
                    if product[key] in skus:
                        issue("error", "duplicate_sku", path + ".sku", "SKUs must be unique.")
                    skus.add(product[key])
        if "gtin" in product and not valid_gtin(product["gtin"]):
            issue("error", "invalid_gtin", path + ".gtin", "GTIN must have 8, 12, 13 or 14 digits and a valid check digit; assignment is not verified.")
        if "identifier_exists" in product:
            if type(product["identifier_exists"]) is not bool:
                issue("error", "identifier_boolean", path + ".identifier_exists", "Must be boolean; false requires merchant confirmation that appropriate identifiers do not exist.")
            elif product["identifier_exists"] is False and ("gtin" in product or "mpn" in product):
                issue("error", "identifier_conflict", path + ".identifier_exists", "Do not declare identifiers absent while supplying GTIN or MPN.")
        if "gtin" not in product and "mpn" not in product and product.get("identifier_exists") is not False:
            issue("warning", "identifier_missing", path, "Provide assigned identifiers if they exist; never invent one or set false merely to silence this warning.")
        if "availability_date" in product:
            try:
                timestamp(product["availability_date"])
            except ValueError as error:
                issue("error", "invalid_availability_date", path + ".availability_date", str(error))
        elif isinstance(availability, str) and availability in {"pre_order", "backorder"}:
            issue("error", "availability_date_missing", path + ".availability_date", "Pre-order/backorder requires a timezone-aware availability date.")
        for key in ("attributes", "variant"):
            if key in product:
                values = product[key]
                if not isinstance(values, dict) or not values or len(values) > 20:
                    issue("error", "invalid_attributes", path + "." + key, "Use 1-20 nonempty text attribute pairs.")
                    continue
                for attribute, value in values.items():
                    text(attribute, path + "." + key + ".key", 100)
                    text(value, path + "." + key + "." + str(attribute), 500)
                    if key == "variant" and attribute not in VARIANT_KEYS:
                        issue("error", "unsupported_variant", path + ".variant", "This release supports color, size, material and pattern options.")
        if ("group_id" in product) != ("variant" in product):
            issue("error", "incomplete_variant", path, "group_id and variant must be supplied together.")
        if isinstance(product.get("attributes"), dict) and isinstance(product.get("variant"), dict):
            for key in set(product["attributes"]) & set(product["variant"]):
                if product["attributes"][key] != product["variant"][key]:
                    issue("error", "variant_attribute_conflict", path, "Selected variant disagrees with the same named product attribute.")
        if "group_id" in product:
            group = product["group_id"]
            if not isinstance(group, str) or not ID_PATTERN.fullmatch(group) or group == identifier:
                issue("error", "invalid_group_id", path + ".group_id", "Group ID must be valid and differ from the item ID.")
            elif isinstance(product.get("variant"), dict) and all(isinstance(k, str) and isinstance(v, str)
                    for k, v in product["variant"].items()):
                groups.setdefault(group, []).append((path, product))
        description = product.get("description")
        if isinstance(description, str) and re.search(r"<\s*/?\s*[A-Za-z][^>]*>", description):
            issue("error", "description_html", path + ".description", "Use factual plain text, without HTML tags.")
    for group, members in groups.items():
        variants, keys, brands = set(), None, set()
        if group in ids:
            issue("error", "group_item_collision", "group:" + group, "A group ID cannot equal any item ID in the catalog.")
        for path, product in members:
            option_keys = frozenset(product["variant"])
            if keys is not None and option_keys != keys:
                issue("error", "variant_keys_mismatch", path + ".variant", "All members of a group must use the same option names.")
            keys = option_keys
            selection = tuple(sorted(product["variant"].items()))
            if selection in variants:
                issue("error", "duplicate_variant", path + ".variant", "Variant selections must be unique within their group.")
            variants.add(selection)
            if isinstance(product.get("brand"), str):
                brands.add(product["brand"])
        if len(brands) > 1:
            issue("error", "group_brand_mismatch", "group:" + group, "Group only variants of one product/brand.")
    return _report(findings, len(products))


def _report(findings, count):
    errors = sum(item["severity"] == "error" for item in findings)
    warnings = len(findings) - errors
    return {"schema_version": "1.0", "valid": errors == 0, "products_checked": count,
            "errors": errors, "warnings": warnings, "findings": findings,
            "limitations": ["Local syntax and consistency only; no URL fetching or platform submission.",
                            "Country/currency code shape and GTIN checksum do not verify assignment or authenticity.",
                            "Successful validation does not guarantee indexing, recommendation or sales."]}


def require_catalog(document, demo=False):
    report = validate_catalog(document)
    if report["errors"]:
        first = next(item for item in report["findings"] if item["severity"] == "error")
        raise ValueError("Invalid catalog: {}: {}".format(first["path"], first["message"]))
    if document["demo"] and not demo:
        raise ValueError("Demo catalog requires --demo; never submit examples as real merchandise.")
    if not demo and any(item["code"] == "placeholder_url" for item in report["findings"]):
        raise ValueError("Replace all example/reserved URLs before production export, or use --demo for local samples.")
    return report
