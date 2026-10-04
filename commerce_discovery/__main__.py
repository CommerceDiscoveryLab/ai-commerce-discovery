"""Offline CLI. It never crawls a site, submits a feed or calls a model."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .audit import audit_page
from .build import build_catalog
from .catalog import load_catalog, require_catalog, validate_catalog
from .exporters import google_export, jsonld_export, openai_export


def write_output(content, path=None, sources=()):
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False, indent=2) + "\n"
    if not path:
        print(content, end="" if content.endswith("\n") else "\n")
        return
    target = Path(path)
    for source in sources:
        source = Path(source)
        same = target.resolve() == source.resolve()
        if target.exists() and source.exists():
            same = same or target.samefile(source)
        if same:
            raise ValueError("Output must differ from all input files.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(target.parent), delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI Commerce Discovery: validate and prepare factual product information offline")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Check catalog data and freshness")
    validate.add_argument("catalog")
    validate.add_argument("--strict", action="store_true", help="Warnings also produce exit code 1")
    validate.add_argument("--max-age-hours", type=float, default=48)
    validate.add_argument("--out")
    export = sub.add_parser("export", help="Generate a JSON-LD, OpenAI JSONL or Google RSS file")
    export.add_argument("catalog")
    export.add_argument("--format", choices=("jsonld", "openai", "google"), required=True)
    export.add_argument("--demo", action="store_true")
    export.add_argument("--out")
    build = sub.add_parser("build", help="Build a static snapshot, feeds and crawler templates; does not deploy")
    build.add_argument("catalog")
    build.add_argument("--out", required=True)
    build.add_argument("--demo", action="store_true")
    build.add_argument("--allow-training", action="store_true", help="Allow GPTBot in the generated production robots template")
    audit = sub.add_parser("audit-page", help="Inspect a local saved HTML file; does not fetch a URL")
    audit.add_argument("html")
    audit.add_argument("--catalog")
    audit.add_argument("--id", dest="product_id")
    audit.add_argument("--out")
    audit.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            report = validate_catalog(load_catalog(args.catalog), max_age_hours=args.max_age_hours)
            write_output(report, args.out, [args.catalog])
            return 1 if report["errors"] or (args.strict and report["warnings"]) else 0
        if args.command == "export":
            document = load_catalog(args.catalog)
            exporter = {"jsonld": jsonld_export, "openai": openai_export, "google": google_export}[args.format]
            write_output(exporter(document, args.demo), args.out, [args.catalog])
        elif args.command == "build":
            result = build_catalog(load_catalog(args.catalog), args.out, args.demo, args.allow_training)
            write_output(result)
        elif args.command == "audit-page":
            if bool(args.catalog) != bool(args.product_id):
                raise ValueError("Use --catalog and --id together for parity checks.")
            expected, sources = None, [args.html]
            if args.catalog:
                document = load_catalog(args.catalog)
                require_catalog(document, demo=True)
                matches = [p for p in document["products"] if p["id"] == args.product_id]
                if not matches:
                    raise ValueError("Product ID not present in the catalog.")
                expected = matches[0]
                sources.append(args.catalog)
            report = audit_page(Path(args.html).read_text(encoding="utf-8"), expected)
            write_output(report, args.out, sources)
            return 1 if report["errors"] or (args.strict and report["warnings"]) else 0
    except (ValueError, OSError, UnicodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
