"""Map a validated snapshot into public, source-grounded product representations."""

import json
import xml.etree.ElementTree as ET

from .catalog import require_catalog


AVAILABILITY_URLS = {"in_stock": "https://schema.org/InStock", "out_of_stock": "https://schema.org/OutOfStock",
                     "pre_order": "https://schema.org/PreOrder", "backorder": "https://schema.org/BackOrder"}
CONDITION_URLS = {"new": "https://schema.org/NewCondition", "used": "https://schema.org/UsedCondition",
                  "refurbished": "https://schema.org/RefurbishedCondition"}
GOOGLE_NAMESPACE = "http://base.google.com/ns/1.0"


def product_jsonld(merchant, product):
    offer = {"@type": "Offer", "url": product["url"], "price": product["price"],
             "priceCurrency": product["currency"], "itemCondition": CONDITION_URLS[product["condition"]],
             "seller": {"@type": "Organization", "name": merchant["name"], "url": merchant["url"]}}
    if product["availability"] in AVAILABILITY_URLS:
        offer["availability"] = AVAILABILITY_URLS[product["availability"]]
    result = {"@context": "https://schema.org", "@type": "Product", "@id": product["url"] + "#product",
              "url": product["url"], "name": product["title"], "description": product["description"],
              "image": [product["image_url"]] + product.get("additional_images", []),
              "brand": {"@type": "Brand", "name": product["brand"]}, "sku": product.get("sku", product["id"]),
              "offers": offer}
    for key in ("mpn", "category"):
        if key in product:
            result[key] = product[key]
    if "gtin" in product:
        result["gtin" + str(len(product["gtin"]))] = product["gtin"]
    if "group_id" in product:
        result["inProductGroupWithID"] = product["group_id"]
    for key, value in product.get("variant", {}).items():
        result[key] = value
    if "attributes" in product:
        result["additionalProperty"] = [{"@type": "PropertyValue", "name": key, "value": value}
                                       for key, value in sorted(product["attributes"].items())]
    return result


def jsonld_export(document, demo=False):
    require_catalog(document, demo)
    return [{"id": product["id"], "url": product["url"], "jsonld": product_jsonld(document["merchant"], product)}
            for product in document["products"]]


def openai_export(document, demo=False):
    """Discovery-only US/USD baseline of the stable 2026-10-04 file spec."""
    require_catalog(document, demo)
    if document["merchant"]["country"] != "US" or any(p["currency"] != "USD" for p in document["products"]):
        raise ValueError("OpenAI adapter currently supports the US/USD baseline only; confirm other market support with your platform integration.")
    rows = []
    for product in document["products"]:
        row = {"item_id": product["id"], "title": product["title"], "description": product["description"],
               "url": product["url"], "brand": product["brand"], "seller_name": document["merchant"]["name"],
               "image_url": product["image_url"], "availability": product["availability"],
               "price": product["price"] + " " + product["currency"], "condition": product["condition"],
               "is_eligible_search": True, "is_eligible_checkout": False, "is_ads_eligible": False}
        for key in ("gtin", "mpn"):
            if key in product:
                row[key] = product[key]
        if "category" in product:
            row["product_category"] = product["category"]
        if "additional_images" in product:
            row["additional_image_urls"] = product["additional_images"]
        if "return_policy_url" in document["merchant"]:
            row["return_policy"] = document["merchant"]["return_policy_url"]
        if "group_id" in product:
            row.update({"group_id": product["group_id"], "listing_has_variations": True,
                        "variant_dict": dict(product["variant"])})
            row.update(product["variant"])
        rows.append(row)
    return "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)


def google_export(document, demo=False):
    """RSS baseline, not full Merchant Center/category-policy validation."""
    require_catalog(document, demo)
    if any(product["availability"] == "unknown" for product in document["products"]):
        raise ValueError("Google feed cannot encode unknown availability; refresh stock before exporting.")
    ET.register_namespace("g", GOOGLE_NAMESPACE)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    for key, value in (("title", document["merchant"]["name"]), ("link", document["merchant"]["url"]),
                       ("description", "Merchant product catalog")):
        ET.SubElement(channel, key).text = value
    for product in document["products"]:
        item = ET.SubElement(channel, "item")
        values = {"id": product["id"], "title": product["title"], "description": product["description"],
                  "link": product["url"], "image_link": product["image_url"], "brand": product["brand"],
                  "availability": "preorder" if product["availability"] == "pre_order" else product["availability"],
                  "price": product["price"] + " " + product["currency"], "condition": product["condition"]}
        for key in ("gtin", "mpn", "availability_date"):
            if key in product:
                values[key] = product[key]
        if "identifier_exists" in product:
            values["identifier_exists"] = "yes" if product["identifier_exists"] else "no"
        if "category" in product:
            values["product_type"] = product["category"]
        if "group_id" in product:
            values["item_group_id"] = product["group_id"]
            values.update(product["variant"])
        for key, value in values.items():
            ET.SubElement(item, "{" + GOOGLE_NAMESPACE + "}" + key).text = value
        for image in product.get("additional_images", []):
            ET.SubElement(item, "{" + GOOGLE_NAMESPACE + "}additional_image_link").text = image
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True).decode("utf-8") + "\n"


def script_json(value):
    """Prevent merchant text from terminating an HTML script element."""
    return json.dumps(value, ensure_ascii=False, indent=2).replace("<", "\\u003c").replace(
        ">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
