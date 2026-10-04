"""Build a portable static example and discovery files, without publishing them."""

import html
import json
import shutil
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .catalog import require_catalog, timestamp
from .exporters import google_export, openai_export, product_jsonld, script_json


STYLE = """body{font:17px/1.65 system-ui,sans-serif;background:#f4f6f2;color:#17342b;margin:0}
main{max-width:850px;margin:42px auto;padding:32px;background:white;border-radius:14px}
a{color:#145d48}h1{line-height:1.2}dt{font-weight:650}dd{margin:0 0 12px}nav a{margin-right:20px}
.price{font-size:28px;font-weight:650}.note{background:#fff0ca;padding:14px;border-radius:8px}
img{max-width:100%;height:auto}li{margin:12px 0}footer{font-size:14px;color:#476057}
@media(max-width:700px){main{margin:12px;padding:20px}}"""


def _page(title, description, canonical, language, body, demo, structured=None):
    escape = html.escape
    robots = "<meta name=\"robots\" content=\"noindex,nofollow\">" if demo else ""
    jsonld = "<script type=\"application/ld+json\">" + script_json(structured) + "</script>" if structured else ""
    return """<!doctype html>
<html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><meta name="description" content="{description}"><link rel="canonical" href="{canonical}">
{robots}<style>{style}</style>{jsonld}</head><body><main>{body}</main></body></html>
""".format(language=escape(language, quote=True), title=escape(title), description=escape(description, quote=True),
           canonical=escape(canonical, quote=True), robots=robots, style=STYLE, jsonld=jsonld, body=body)


def product_page(merchant, product, demo=False):
    escape = html.escape
    links = " ".join('<a href="{}">{}</a>'.format(escape(merchant[key], quote=True), label)
                     for key, label in (("support_url", "Contact"), ("shipping_policy_url", "Shipping"),
                                        ("return_policy_url", "Returns")) if key in merchant)
    attributes = {"Brand": product["brand"], "Item": product["id"], "Condition": product["condition"],
                  **product.get("attributes", {}), **product.get("variant", {})}
    details = "".join("<dt>{}</dt><dd>{}</dd>".format(escape(key), escape(value)) for key, value in attributes.items())
    demo_note = '<p class="note">Synthetic demonstration. Prices, products and example URLs are not real offers.</p>' if demo else ""
    media = ('<p class="note">Demo image placeholder: <code>{}</code></p>'.format(escape(product["image_url"]))
             if demo else '<img src="{}" alt="{}" loading="lazy">'.format(
                 escape(product["image_url"], quote=True), escape(product["title"], quote=True)))
    body = """<nav><a href="/">Catalog</a></nav>{demo_note}<h1>{title}</h1><p>{description}</p>
<p class="price">{price} {currency}</p><p>Availability: {stock}</p>
{media}<dl>{details}</dl>
<p>Seller: {seller}</p><p>{links}</p><footer>Catalog snapshot updated: {updated}. Confirm current terms and stock with the merchant.</footer>""".format(
        demo_note=demo_note, title=escape(product["title"]), description=escape(product["description"]),
        price=escape(product["price"]), currency=escape(product["currency"]), stock=escape(product["availability"]),
        media=media, details=details, seller=escape(merchant["name"]),
        links=links, updated=escape(product["updated_at"]))
    if "availability_date" in product:
        body += "<p>Expected availability date: {}</p>".format(escape(product["availability_date"]))
    return _page(product["title"], product["description"], product["url"], merchant["language"], body,
                 demo, product_jsonld(merchant, product))


def page_path(url):
    parts = urlsplit(url)
    if parts.query:
        raise ValueError("Static build requires distinct URL paths; export feeds/JSON-LD for query-selected variants instead.")
    raw = parts.path
    if not raw or raw == "/" or any(token in raw.lower() for token in ("%2f", "%5c")):
        raise ValueError("Product pages need explicit paths without encoded separators.")
    path = Path(unquote(raw).lstrip("/"))
    if path.suffix and path.suffix.lower() != ".html":
        raise ValueError("Static product paths must be extensionless or end in .html.")
    return path if path.suffix else path / "index.html"


def robots_template(origin, demo=False, allow_training=False):
    if demo:
        return "# Demo only: do not index or ingest synthetic merchandise.\nUser-agent: *\nDisallow: /\n"
    private = ("/account", "/admin", "/cart", "/checkout", "/private")
    groups = []
    for agent in ("*", "OAI-SearchBot", "ChatGPT-User"):
        groups.append("User-agent: " + agent + "\n" + "\n".join("Disallow: " + path for path in private))
    groups.append("User-agent: GPTBot\n" + ("\n".join("Disallow: " + path for path in private)
                                            if allow_training else "Disallow: /"))
    return "# Merge with existing site rules; robots.txt is not authentication.\n" + "\n\n".join(groups) + "\n\nSitemap: " + origin.rstrip("/") + "/sitemap.xml\n"


def build_catalog(document, output, demo=False, allow_training=False):
    validation = require_catalog(document, demo)
    effective_demo = demo or document["demo"]
    merchant = document["merchant"]
    files = {}

    def add(path, content):
        path = Path(path)
        if path.is_absolute() or ".." in path.parts or any(str(existing).casefold() == str(path).casefold()
                or existing in path.parents or path in existing.parents for existing in files):
            raise ValueError("Output path collision or unsafe path: " + str(path))
        files[path] = content

    links = "".join('<li><a href="{}">{}</a> — {} {}</li>'.format(
        html.escape(urlsplit(product["url"]).path, quote=True), html.escape(product["title"]),
        html.escape(product["price"]), html.escape(product["currency"])) for product in document["products"])
    note = '<p class="note">Synthetic local demonstration; do not submit these example products to platforms.</p>' if effective_demo else ""
    add("index.html", _page(merchant["name"], "Product catalog for " + merchant["name"], merchant["url"],
                            merchant["language"], "<h1>{}</h1>{}<ul>{}</ul>".format(html.escape(merchant["name"]), note, links), effective_demo))
    add("catalog.json", json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    add("robots.txt", robots_template(merchant["url"], effective_demo, allow_training))
    add("feeds/google.xml", google_export(document, demo))
    openai_status = "generated: discovery only, no submission"
    if merchant["country"] == "US" and all(p["currency"] == "USD" for p in document["products"]):
        add("feeds/openai.jsonl", openai_export(document, demo))
    else:
        openai_status = "skipped: adapter supports the US/USD baseline; other markets require confirmed platform support"
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", namespace)
    sitemap = ET.Element("{" + namespace + "}urlset")
    for product in document["products"]:
        add(page_path(product["url"]), product_page(merchant, product, effective_demo))
        add("jsonld/" + product["id"] + ".json", json.dumps(product_jsonld(merchant, product), ensure_ascii=False, indent=2) + "\n")
        node = ET.SubElement(sitemap, "{" + namespace + "}url")
        ET.SubElement(node, "{" + namespace + "}loc").text = product["url"]
        ET.SubElement(node, "{" + namespace + "}lastmod").text = timestamp(product["updated_at"]).isoformat()
    add("sitemap.xml", ET.tostring(sitemap, encoding="utf-8", xml_declaration=True).decode("utf-8") + "\n")
    info = {"generator": "AI Commerce Discovery 0.1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
            "demo": effective_demo, "products": len(document["products"]), "openai_feed": openai_status,
            "validation": validation, "limitations": ["Offline build only; no publication or vendor submission.",
            "Replace demo URLs/images and integrate into your own purchasable merchant pages.",
            "Policy links are supplied; shipping quotes, rich return markup and checkout are not implemented."]}
    add("BUILD_INFO.json", json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    target = Path(output)
    if target.is_symlink() or (target.exists() and (not target.is_dir() or any(target.iterdir()))):
        raise ValueError("Build output must be a new or empty directory; publish a fresh snapshot to avoid stale product files.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".commerce-build-", dir=str(target.parent)))
    try:
        for path, content in files.items():
            destination = temporary / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
        if target.exists():
            target.rmdir()  # Only the verified empty output directory.
        temporary.rename(target)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"output": str(target.resolve()), "files_written": len(files), "products": len(document["products"]),
            "demo": effective_demo, "openai_feed": openai_status}
