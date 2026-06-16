"""
audit_engine.py
================
Local, programmatic anomaly detection for Mushak 9.1 VAT data.
Enhanced with Advanced Tax Intelligence rules (Late Filing Risk & Challan Tracking).

Reads:
  Dynamic session files via 'MUSHAK_DATA_DIR' environment variable.
  - sales_register.xlsx
  - purchase_register.xlsx

Writes:
  - detected_anomalies.json
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration (Dynamic Multi-User Session Isolation)
# ---------------------------------------------------------------------------
DATA_DIR = os.getenv("MUSHAK_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples"))
os.makedirs(DATA_DIR, exist_ok=True)

SALES_PATH = os.path.join(DATA_DIR, "sales_register.xlsx")
PURCHASE_PATH = os.path.join(DATA_DIR, "purchase_register.xlsx")
OUTPUT_PATH = os.path.join(DATA_DIR, "detected_anomalies.json")

STANDARD_VAT_RATE = 0.15
TIN_LENGTH = 12
VAT_TOLERANCE = 0.01  
TOTAL_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_float(x: Any) -> float:
    try:
        if pd.isna(x):
            return 0.0
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _to_str(x: Any) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def _parse_date(date_val: Any) -> datetime | None:
    """Safely parse various Excel date formats into standard datetime object."""
    if pd.isna(date_val):
        return None
    if isinstance(date_val, datetime):
        return date_val
    
    # If it's an Excel timestamp object or string
    date_str = str(date_val).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.split()[0], fmt)
        except (ValueError, IndexError):
            continue
    return None


def _expected_vat(base: float) -> float:
    return round(base * STANDARD_VAT_RATE, 2)


def _make_record(
    rule: str,
    severity: str,
    source: str,
    invoice_no: str,
    tin: str,
    field: str,
    expected: Any,
    actual: Any,
    explanation: str,
) -> dict:
    return {
        "rule": rule,
        "severity": severity,
        "source": source,
        "invoice_no": invoice_no,
        "tin": tin,
        "field": field,
        "expected": expected,
        "actual": actual,
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# Rule checks (per row, per source sheet)
# ---------------------------------------------------------------------------
def check_row(row: pd.Series, source: str) -> list[dict]:
    issues: list[dict] = []
    inv = _to_str(row.get("invoice_no", ""))
    tin = _to_str(row.get("supplier_tin" if source == "purchase" else "buyer_tin", ""))
    base = _to_float(row.get("value_excl_vat"))
    vat = _to_float(row.get("vat"))
    total = _to_float(row.get("total"))
    
    # Extract new fields for tax intelligence rules
    challan_no = _to_str(row.get("mushak_6_3_no" if "mushak_6_3_no" in row else row.get("challan_no", "")))
    invoice_date = _parse_date(row.get("invoice_date"))
    filing_date = _parse_date(row.get("filing_date"))

    # 1) TIN missing
    if not tin:
        issues.append(_make_record(
            "TIN_MISSING", "HIGH", source, inv, tin, "tin",
            "12-digit TIN required (Mushak 9.1)",
            tin or "<empty>",
            "Buyer/supplier TIN is blank. A valid 12-digit TIN is mandatory on every Mushak 9.1 line.",
        ))

    # 2) TIN length invalid
    elif not tin.isdigit() or len(tin) != TIN_LENGTH:
        issues.append(_make_record(
            "TIN_FORMAT_INVALID", "MEDIUM", source, inv, tin, "tin",
            f"{TIN_LENGTH}-digit numeric TIN",
            tin,
            "TIN must be exactly 12 numeric digits as per NBR TIN registration rules.",
        ))

    # 3) Negative monetary values
    if base < 0:
        issues.append(_make_record(
            "NEGATIVE_BASE_VALUE", "HIGH", source, inv, tin, "value_excl_vat",
            ">= 0",
            base,
            "Negative base value detected. Returns/refunds should be recorded in a separate credit-note column, not as a negative line.",
        ))
    if vat < 0:
        issues.append(_make_record(
            "NEGATIVE_VAT", "HIGH", source, inv, tin, "vat",
            ">= 0",
            vat,
            "Negative VAT detected on a Mushak 9.1 line. Credit notes must be reported distinctly.",
        ))
    if total < 0:
        issues.append(_make_record(
            "NEGATIVE_TOTAL", "HIGH", source, inv, tin, "total",
            ">= 0",
            total,
            "Negative invoice total detected. Sales returns require a separate Mushak 9.1 credit-note entry.",
        ))

    # 4) VAT rate mismatch
    if base > 0 and abs(vat - _expected_vat(base)) > VAT_TOLERANCE:
        issues.append(_make_record(
            "VAT_RATE_MISMATCH", "HIGH", source, inv, tin, "vat",
            round(_expected_vat(base), 2),
            round(vat, 2),
            f"Standard VAT rate is 15% under the Value Added Tax and Supplementary Duty Act, 2012. Expected 15% of base, got an effective rate of {(vat/base*100 if base else 0):.2f}%.",
        ))

    # 5) Total mismatch (base + vat != total)
    expected_total = round(base + vat, 2)
    if base > 0 and abs(total - expected_total) > TOTAL_TOLERANCE:
        issues.append(_make_record(
            "TOTAL_MISMATCH", "MEDIUM", source, inv, tin, "total",
            expected_total,
            round(total, 2),
            "Invoice total does not equal value_excl_vat + vat. Mushak 9.1 requires the declared total to reconcile.",
        ))

    # ADVANCED RULE 6) Missing Mushak 6.3 Challan Number (For Purchase Credit Protection)
    if source == "purchase" and base > 0 and not challan_no:
        issues.append(_make_record(
            "MISSING_CHALLAN_REF", "HIGH", source, inv, tin, "challan_no",
            "Valid Mushak 6.3 Number",
            "<missing>",
            "Under Section 46 of the Act, input VAT rebate is strictly inadmissible without holding the corresponding Mushak 6.3 Tax Challan transaction reference.",
        ))

    # ADVANCED RULE 7) Late Filing & Submission Deadline Risk (The 15th Rule)
    if invoice_date and filing_date:
        # Check if filed in a later month, and if filing day bypassed the 15th
        if filing_date.year > invoice_date.year or filing_date.month > invoice_date.month:
            # If it's a submission past the immediate next month's 15th day
            if filing_date.month > (invoice_date.month + 1) or (filing_date.month == invoice_date.month + 1 and filing_date.day > 15):
                issues.append(_make_record(
                    "LATE_FILING_RISK", "MEDIUM", source, inv, tin, "filing_date",
                    f"Filing by 15th of next month",
                    filing_date.strftime("%Y-%m-%d"),
                    f"Filing date breaks Rule 25 of the VAT Rules, 2016. Invoices from {invoice_date.strftime('%B')} must be declared by the 15th of the following month to avoid standard statutory penalties.",
                ))

    return issues


def check_duplicates(df: pd.DataFrame, source: str) -> list[dict]:
    issues: list[dict] = []
    counts = defaultdict(list)
    for idx, inv in enumerate(df["invoice_no"].astype(str).str.strip()):
        if inv and inv != "nan":
            counts[inv].append(idx)
    for inv, idxs in counts.items():
        if len(idxs) > 1:
            for idx in idxs:
                row = df.iloc[idx]
                issues.append(_make_record(
                    "DUPLICATE_INVOICE", "HIGH", source, inv,
                    _to_str(row.get("supplier_tin" if source == "purchase" else "buyer_tin", "")),
                    "invoice_no",
                    "unique invoice_no within register",
                    f"{len(idxs)} occurrences",
                    f"Invoice number '{inv}' appears {len(idxs)} times in the {source} register. Each Mushak 9.1 line must have a unique invoice reference.",
                ))
    return issues


def check_cross_sheet_duplicates(sales: pd.DataFrame, purchase: pd.DataFrame) -> list[dict]:
    issues: list[dict] = []
    s_set = {str(x).strip() for x in sales["invoice_no"].tolist() if str(x).strip() and str(x).strip() != "nan"}
    p_set = {str(x).strip() for x in purchase["invoice_no"].tolist() if str(x).strip() and str(x).strip() != "nan"}
    overlap = s_set & p_set
    for inv in sorted(overlap):
        issues.append(_make_record(
            "CROSS_SHEET_INVOICE_COLLISION", "HIGH",
            "sales+purchase", inv, "",
            "invoice_no",
            "distinct invoice numbering between sales and purchase",
            f"sales ∩ purchase = {{{inv}}}",
            f"Invoice '{inv}' is used in both the sales and purchase registers. Mushak 9.1 output is rejected if the same invoice number is claimed in both directions.",
        ))
    return issues


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_audit() -> dict:
    if not (os.path.exists(SALES_PATH) and os.path.exists(PURCHASE_PATH)):
        print(f"[!] Target spreadsheets not found in environment: {DATA_DIR}", file=sys.stderr)
        sys.exit(1)

    sales = pd.read_excel(SALES_PATH, sheet_name=0, dtype=str)
    purchase = pd.read_excel(PURCHASE_PATH, sheet_name=0, dtype=str)

    anomalies: list[dict] = []

    for _, row in sales.iterrows():
        anomalies.extend(check_row(row, "sales"))
    for _, row in purchase.iterrows():
        anomalies.extend(check_row(row, "purchase"))

    anomalies.extend(check_duplicates(sales, "sales"))
    anomalies.extend(check_duplicates(purchase, "purchase"))
    anomalies.extend(check_cross_sheet_duplicates(sales, purchase))

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "standard_vat_rate": STANDARD_VAT_RATE,
        "tin_length": TIN_LENGTH,
        "sources": {
            "sales_rows": len(sales),
            "purchase_rows": len(purchase),
        },
        "counts_by_severity": {
            "HIGH": sum(1 for a in anomalies if a["severity"] == "HIGH"),
            "MEDIUM": sum(1 for a in anomalies if a["severity"] == "MEDIUM"),
            "LOW": sum(1 for a in anomalies if a["severity"] == "LOW"),
        },
        "counts_by_rule": _count_by(anomalies, "rule"),
        "anomalies": anomalies,
    }
    return summary


def _count_by(records: list[dict], key: str) -> dict:
    out: dict[str, int] = defaultdict(int)
    for r in records:
        out[r[key]] += 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main() -> None:
    result = run_audit()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[+] Wrote {OUTPUT_PATH}")
    print(f"[i] Total anomalies: {len(result['anomalies'])}")


if __name__ == "__main__":
    main()