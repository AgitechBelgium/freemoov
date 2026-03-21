#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audit des produits actuels du Google Merchant Center vs le flux optimise (CSV).

Compare les 126 produits (ou plus) presents dans GMC avec les 340 produits du
fichier gmc_feed_optimized.csv et genere un rapport d actions (ADD/DELETE/UPDATE/OK).

Usage:
  Export des credentials (obligatoire pour appeler l API list) :
    export GMC_MERCHANT_ID=123456789
    export GMC_DATA_SOURCE_ID=987654321
    export GMC_CREDENTIALS_JSON=/path/to/service-account.json

  Puis :
    python3 gmc_audit_existing.py

  Sans credentials : charge uniquement le CSV et affiche les stats (mode sec).
"""
from __future__ import print_function
import csv
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
CSV_FEED = os.path.join(BASE_PATH, "gmc_feed_optimized.csv")
OUTPUT_REPORT = os.path.join(BASE_PATH, "gmc_audit_report.csv")
RUNNER_SCRIPT = os.path.join(SCRIPT_DIR, "gmc_api_runner.py")


def load_gmc_products():
    """Appelle gmc_api_runner.py action=list et retourne la liste de produits."""
    merchant_id = os.environ.get("GMC_MERCHANT_ID", "").strip()
    data_source_id = os.environ.get("GMC_DATA_SOURCE_ID", "").strip()
    creds_path = os.environ.get("GMC_CREDENTIALS_JSON", "").strip()
    if not merchant_id or not data_source_id or not creds_path:
        return None, "GMC_MERCHANT_ID, GMC_DATA_SOURCE_ID et GMC_CREDENTIALS_JSON requis"
    if not os.path.isfile(creds_path):
        return None, "Fichier credentials introuvable: %s" % creds_path
    with open(creds_path, "r", encoding="utf-8") as f:
        credentials_json = json.load(f)
    payload = {
        "action": "list",
        "merchant_id": merchant_id,
        "data_source_id": data_source_id,
        "credentials_json": credentials_json,
    }
    try:
        proc = subprocess.Popen(
            [sys.executable, RUNNER_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(RUNNER_SCRIPT),
        )
        out, err = proc.communicate(input=json.dumps(payload).encode("utf-8"), timeout=120)
        stdout = out.decode("utf-8", errors="ignore").strip()
        stderr = err.decode("utf-8", errors="ignore").strip()
        if not stdout:
            return None, stderr[:500] if stderr else "No output from runner (exit=%d)" % proc.returncode
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as e:
            return None, "JSON parse error: %s | stdout: %s | stderr: %s" % (e, stdout[:200], stderr[:200])
        if not result.get("success"):
            return None, result.get("error", "Unknown error")
        return result.get("products", []), None
    except subprocess.TimeoutExpired:
        proc.kill()
        return None, "Timeout"
    except Exception as e:
        return None, str(e)


def load_csv_feed():
    if not os.path.isfile(CSV_FEED):
        return None, "Fichier introuvable: %s" % CSV_FEED
    with open(CSV_FEED, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows, None


def main():
    csv_rows, err = load_csv_feed()
    if err:
        print(err, file=sys.stderr)
        return 1
    csv_by_id = {r["id"]: r for r in csv_rows}
    csv_ids = set(csv_by_id.keys())

    gmc_products, err = load_gmc_products()
    if err:
        print("GMC list non disponible: %s" % err, file=sys.stderr)
        print("Mode sec: utilisation du CSV seul (%d produits)." % len(csv_rows), file=sys.stderr)
        gmc_products = []
    gmc_by_offer_id = {p["offer_id"]: p for p in gmc_products}
    gmc_ids = set(gmc_by_offer_id.keys())

    report = []
    # ADD: dans CSV, pas dans GMC
    for oid in csv_ids - gmc_ids:
        r = csv_by_id[oid]
        report.append({
            "offer_id": oid,
            "action": "ADD",
            "in_csv": "yes",
            "in_gmc": "no",
            "title_csv": (r.get("title") or "")[:80],
            "title_gmc": "",
            "price_csv": r.get("price", ""),
            "price_gmc": "",
            "availability_csv": r.get("availability", ""),
            "availability_gmc": "",
            "issues": "A ajouter au GMC",
        })
    # DELETE: dans GMC, pas dans CSV
    for oid in gmc_ids - csv_ids:
        p = gmc_by_offer_id[oid]
        report.append({
            "offer_id": oid,
            "action": "DELETE",
            "in_csv": "no",
            "in_gmc": "yes",
            "title_csv": "",
            "title_gmc": (p.get("title") or "")[:80],
            "price_csv": "",
            "price_gmc": "%s %s" % (p.get("currency_code", "EUR"), (p.get("price_micros") or 0) / 1e6),
            "availability_csv": "",
            "availability_gmc": p.get("availability", ""),
            "issues": "Supprimer du GMC (absent du flux optimise)",
        })
    # UPDATE / OK: dans les deux
    for oid in csv_ids & gmc_ids:
        r = csv_by_id[oid]
        p = gmc_by_offer_id[oid]
        price_micros = p.get("price_micros") or 0
        price_gmc_eur = "%.2f EUR" % (price_micros / 1e6)
        price_csv = r.get("price", "")
        title_csv = (r.get("title") or "")[:80]
        title_gmc = (p.get("title") or "")[:80]
        av_csv = r.get("availability", "")
        av_gmc = p.get("availability", "")
        issues = []
        if price_csv != price_gmc_eur:
            issues.append("Prix different")
        if title_csv != title_gmc:
            issues.append("Titre different")
        if av_csv and av_gmc and av_csv.upper().replace(" ", "_") != av_gmc.upper().replace(" ", "_"):
            issues.append("Disponibilite differente")
        action = "UPDATE" if issues else "OK"
        report.append({
            "offer_id": oid,
            "action": action,
            "in_csv": "yes",
            "in_gmc": "yes",
            "title_csv": title_csv,
            "title_gmc": title_gmc,
            "price_csv": price_csv,
            "price_gmc": price_gmc_eur,
            "availability_csv": av_csv,
            "availability_gmc": av_gmc,
            "issues": " | ".join(issues) if issues else "",
        })

    fieldnames = ["offer_id", "action", "in_csv", "in_gmc", "title_csv", "title_gmc",
                  "price_csv", "price_gmc", "availability_csv", "availability_gmc", "issues"]
    with open(OUTPUT_REPORT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(report)

    add_n = sum(1 for x in report if x["action"] == "ADD")
    del_n = sum(1 for x in report if x["action"] == "DELETE")
    up_n = sum(1 for x in report if x["action"] == "UPDATE")
    ok_n = sum(1 for x in report if x["action"] == "OK")
    print("Rapport: %s" % OUTPUT_REPORT)
    print("  ADD:    %d" % add_n)
    print("  DELETE: %d" % del_n)
    print("  UPDATE: %d" % up_n)
    print("  OK:     %d" % ok_n)
    print("  Total:  %d" % len(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
