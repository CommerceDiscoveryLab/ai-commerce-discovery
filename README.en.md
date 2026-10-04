# AI Commerce Discovery

Make factual merchant product information easier for AI search, shopping assistants and retrieval systems to read, verify and cite.

[中文](README.md) · [Catalog contract](docs/catalog-contract.md) · [Integration](docs/integration.md) · [Branding](docs/branding.md)

**Contact:** [petterzhang0514@gmail.com](mailto:petterzhang0514@gmail.com)

One catalog snapshot produces Schema.org Product/Offer JSON-LD, OpenAI discovery JSONL, Google Merchant RSS XML, reference static product pages, a sitemap and crawler templates. Offline checks cover identities, variant consistency, GTIN checksums, money precision, freshness, and parity between saved HTML JSON-LD and catalog price/stock.

Python 3.9+, standard library runtime, no API key:

```sh
git clone https://github.com/CommerceDiscoveryLab/ai-commerce-discovery.git
cd ai-commerce-discovery
python3 -m commerce_discovery validate examples/catalog.demo.json
python3 -m commerce_discovery build examples/catalog.demo.json --demo --out dist/demo
python3 -m commerce_discovery export examples/catalog.demo.json --format openai --demo --out dist/openai.jsonl
python3 -m commerce_discovery export examples/catalog.demo.json --format google --demo --out dist/google.xml
python3 -m unittest discover -s tests -v
```

Use a new or empty build directory. Demo products are fictional: generated HTML is noindex, crawler access is blocked, and image addresses are placeholders. Do not submit demo feeds. Replace them with authoritative merchant data and set `demo=false` for real use. Product identifiers, reviews and certifications must never be invented.

For an existing store, integrate exported JSON-LD into purchasable pages and deliver refreshed feeds through the platform's approved workflow. The static builder is a reference publication artifact without cart/checkout. It supports distinct URL paths; query-selected variants can use export commands instead. The page auditor reads saved HTML without executing JavaScript or fetching URLs, and compares structured data rather than visible/live checkout prices.

The OpenAI adapter is a discovery-only US/USD baseline checked against the Stable file specification on 2026-10-04. Ads and checkout remain disabled. Other markets need confirmed support and adapter changes. Official feed onboarding requires platform approval. Google feeds require separate account, category and market verification. This release emits individual Products with group IDs, not a complete ProductGroup rich-result implementation. No built-in Shopify/WooCommerce connector or live submission is included.

Exit codes: `0` no blocking errors, `1` blocking findings or warnings in strict mode, `2` invalid input/I/O/unsupported operation. Always read the report. Public data, valid markup and successful exports do not guarantee indexing, recommendation, traffic or sales, and publishing this repository does not submit any products.

[Primary references](docs/references.md), [discovery checklist](docs/discovery-checklist.md), [contributing](CONTRIBUTING.md), [security](SECURITY.md). MIT for original project material; external sources retain their licenses.
