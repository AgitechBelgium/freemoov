#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recherche de GTIN (EAN-13) pour les produits du flux GMC sans code-barres.

Deux modes :
1. Depuis le CSV optimise : lit gmc_feed_optimized.csv, liste les produits sans GTIN,
   optionnellement interroge l API EAN-Search.org (token requis).
2. Depuis Odoo (odoo shell) : pour les produits multi-variantes, suggere le barcode
   de la premiere variante active.

Usage CSV seul (sans API) :
  python3 gmc_gtin_lookup.py

Usage avec API EAN-Search (recherche par nom) :
  export EAN_SEARCH_API_KEY=your_token
  python3 gmc_gtin_lookup.py

Usage depuis Odoo (enrichissement variantes) :
  docker exec -i CONTAINER odoo shell -d DB < gmc_gtin_lookup.py

Sortie : gmc_gtin_suggestions.csv (id, title, brand, suggested_gtin, source)
"""
from __future__ import print_function
import csv
import os
import re
import sys
import urllib.parse
import urllib.request

try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = "/mnt/extra-addons/google_merchant_center/scripts"
BASE_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
CSV_FEED = os.path.join(BASE_PATH, "gmc_feed_optimized.csv")
OUTPUT_SUGGESTIONS = os.path.join(BASE_PATH, "gmc_gtin_suggestions.csv")

def ean13_check_digit(digits12):
    if len(digits12) != 12 or not digits12.isdigit():
        return None
    s = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digits12))
    return str((10 - s % 10) % 10)

def is_valid_ean13(code):
    if not code or len(code) != 13 or not code.isdigit():
        return False
    return ean13_check_digit(code[:12]) == code[12]

def search_ean_api(query, token, max_results=5):
    if not token or not query:
        return []
    url = "https://api.ean-search.org/api?token=%s&op=product-search&name=%s" % (
        token, urllib.parse.quote(query[:200])
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Freemoov-GMC-GTIN-Lookup/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print("API error: %s" % e, file=sys.stderr)
        return []
    results = []
    if data.strip().startswith("{"):
        import json
        try:
            obj = json.loads(data)
            if isinstance(obj, list):
                for item in obj[:max_results]:
                    ean = (item.get("ean") or item.get("code") or "").strip()
                    if len(ean) >= 13 and ean[:13].isdigit() and is_valid_ean13(ean[:13]):
                        results.append({"ean": ean[:13], "name": item.get("name", "")})
            elif isinstance(obj, dict) and "products" in obj:
                for item in obj["products"][:max_results]:
                    ean = (item.get("ean") or item.get("code") or "").strip()
                    if len(ean) >= 13 and ean[:13].isdigit() and is_valid_ean13(ean[:13]):
                        results.append({"ean": ean[:13], "name": item.get("name", "")})
        except Exception:
            pass
    if not results and "<ean>" in data.lower():
        for m in re.finditer(r"<ean>(\d{13})</ean>", data, re.IGNORECASE):
            if is_valid_ean13(m.group(1)):
                results.append({"ean": m.group(1), "name": ""})
            if len(results) >= max_results:
                break
    return results

def run_from_csv():
    if not os.path.isfile(CSV_FEED):
        print("Fichier introuvable: %s" % CSV_FEED, file=sys.stderr)
        return 1
    token = os.environ.get("EAN_SEARCH_API_KEY", "").strip()
    with open(CSV_FEED, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    missing = [r for r in rows if not (r.get("gtin") or "").strip()]
    print("Produits sans GTIN: %d / %d" % (len(missing), len(rows)), file=sys.stderr)
    suggestions = []
    for r in missing:
        offer_id = r.get("id", "")
        title = (r.get("title") or "")[:200]
        brand = (r.get("brand") or "").strip()
        suggested_gtin = ""
        source = ""
        if token:
            query = "%s %s" % (brand, title) if brand else title
            api_results = search_ean_api(query, token, max_results=3)
            for res in api_results:
                if is_valid_ean13(res["ean"]):
                    suggested_gtin = res["ean"]
                    source = "ean_search_api"
                    break
        suggestions.append({
            "id": offer_id, "title": title, "brand": brand,
            "current_gtin": "", "suggested_gtin": suggested_gtin, "source": source or "none",
        })
    fieldnames = ["id", "title", "brand", "current_gtin", "suggested_gtin", "source"]
    with open(OUTPUT_SUGGESTIONS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(suggestions)
    with_suggestion = sum(1 for s in suggestions if s["suggested_gtin"])
    print("Suggestions: %s | Avec EAN: %d / %d" % (OUTPUT_SUGGESTIONS, with_suggestion, len(suggestions)), file=sys.stderr)
    return 0

def run_from_odoo():
    try:
        env
    except NameError:
        return run_from_csv()
    feed_path = CSV_FEED
    if not os.path.isfile(feed_path):
        feed_path = os.path.join("/mnt/extra-addons/google_merchant_center", "gmc_feed_optimized.csv")
        out_path = os.path.join("/mnt/extra-addons/google_merchant_center", "gmc_gtin_suggestions.csv")
    else:
        out_path = OUTPUT_SUGGESTIONS
    Product = env["product.template"].with_context(active_test=True)
    with open(feed_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    missing = [r for r in rows if not (r.get("gtin") or "").strip()]
    id_to_product = {}
    for r in rows:
        oid = r.get("id", "")
        if not oid: continue
        prod = Product.search([("default_code", "=", oid)], limit=1)
        if not prod:
            try:
                prod = Product.browse(int(oid))
                if not prod.exists(): prod = Product.search([("id", "=", int(oid))], limit=1)
            except (ValueError, TypeError): pass
        if prod: id_to_product[oid] = prod[0]
    suggestions = []
    for r in missing:
        offer_id = r.get("id", "")
        title = (r.get("title") or "")[:200]
        brand = (r.get("brand") or "").strip()
        suggested_gtin = ""
        source = ""
        prod = id_to_product.get(offer_id)
        if prod and prod.product_variant_ids:
            for v in prod.product_variant_ids:
                if v.barcode and is_valid_ean13(str(v.barcode).strip()):
                    suggested_gtin = str(v.barcode).strip()[:13]
                    source = "odoo_variant"
                    break
        suggestions.append({
            "id": offer_id, "title": title, "brand": brand,
            "current_gtin": "", "suggested_gtin": suggested_gtin, "source": source or "none",
        })
    fieldnames = ["id", "title", "brand", "current_gtin", "suggested_gtin", "source"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(suggestions)
    with_suggestion = sum(1 for s in suggestions if s["suggested_gtin"])
    print("Suggestions (Odoo): %s | Avec EAN: %d / %d" % (out_path, with_suggestion, len(suggestions)), file=sys.stderr)
    return 0

if __name__ == "__main__":
    try:
        env
        sys.exit(run_from_odoo())
    except NameError:
        sys.exit(run_from_csv())
