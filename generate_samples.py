"""
generate_samples.py
===================
Generates two synthetic Mushak 9.1 style spreadsheets (Sales and Purchase)
inside ./samples/ for the NBR VAT reconciliation engine to audit.

Deliberate anomalies are seeded so the audit_engine has something to flag:
  - Missing TIN
  - VAT calculated at wrong rate (not 15%)
  - Negative invoice total
  - Duplicate invoice number across sheets
  - Mismatch between (value_excl_vat + vat) and total

Only standard libraries + pandas + openpyxl are used.
"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
SALES_PATH = os.path.join(SAMPLES_DIR, "mushak_9_1_sales.xlsx")
PURCHASE_PATH = os.path.join(SAMPLES_DIR, "mushak_9_1_purchase.xlsx")

# Mushak 9.1 (Bangladesh) standard VAT rate
STANDARD_VAT_RATE = 0.15

# Mushak 9.1 column layout (commonly used by the NBR VAT software)
COLUMNS = [
    "invoice_no",
    "invoice_date",
    "supplier_name",
    "supplier_tin",
    "buyer_name",
    "buyer_tin",
    "value_excl_vat",
    "vat",
    "total",
    "remarks",
]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def _clean(rows: list[dict]) -> pd.DataFrame:
    """Build a DataFrame, round monetary fields, and order columns."""
    df = pd.DataFrame(rows, columns=COLUMNS)
    for c in ("value_excl_vat", "vat", "total"):
        df[c] = df[c].astype(float).round(2)
    return df


def build_sales_rows() -> list[dict]:
    """Return a small but realistic-ish sales register with seeded anomalies."""
    return [
        # Clean row
        {
            "invoice_no": "INV-S-1001",
            "invoice_date": "2026-04-02",
            "supplier_name": "N/A (Sales)",
            "supplier_tin": "000000000000",
            "buyer_name": "Rahim Trading",
            "buyer_tin": "123456789012",
            "value_excl_vat": 100000.00,
            "vat": round(100000.00 * STANDARD_VAT_RATE, 2),
            "total": 100000.00 + round(100000.00 * STANDARD_VAT_RATE, 2),
            "remarks": "Local sales",
        },
        # Anomaly: missing buyer TIN
        {
            "invoice_no": "INV-S-1002",
            "invoice_date": "2026-04-03",
            "supplier_name": "N/A (Sales)",
            "supplier_tin": "000000000000",
            "buyer_name": "Karim & Sons",
            "buyer_tin": "",
            "value_excl_vat": 50000.00,
            "vat": round(50000.00 * STANDARD_VAT_RATE, 2),
            "total": 50000.00 + round(50000.00 * STANDARD_VAT_RATE, 2),
            "remarks": "Walk-in customer",
        },
        # Anomaly: VAT charged at 10% instead of 15%
        {
            "invoice_no": "INV-S-1003",
            "invoice_date": "2026-04-05",
            "supplier_name": "N/A (Sales)",
            "supplier_tin": "000000000000",
            "buyer_name": "Hossain Enterprise",
            "buyer_tin": "987654321098",
            "value_excl_vat": 200000.00,
            "vat": round(200000.00 * 0.10, 2),  # wrong rate
            "total": 200000.00 + round(200000.00 * 0.10, 2),
            "remarks": "Under-charged VAT",
        },
        # Anomaly: duplicate of INV-S-1003 (duplicate invoice number)
        {
            "invoice_no": "INV-S-1003",
            "invoice_date": "2026-04-05",
            "supplier_name": "N/A (Sales)",
            "supplier_tin": "000000000000",
            "buyer_name": "Hossain Enterprise",
            "buyer_tin": "987654321098",
            "value_excl_vat": 200000.00,
            "vat": round(200000.00 * 0.10, 2),
            "total": 200000.00 + round(200000.00 * 0.10, 2),
            "remarks": "Duplicate entry",
        },
        # Anomaly: negative total (return/refund entered as positive)
        {
            "invoice_no": "INV-S-1004",
            "invoice_date": "2026-04-08",
            "supplier_name": "N/A (Sales)",
            "supplier_tin": "000000000000",
            "buyer_name": "Babul Store",
            "buyer_tin": "192837465091",
            "value_excl_vat": 30000.00,
            "vat": round(30000.00 * STANDARD_VAT_RATE, 2),
            "total": -(30000.00 + round(30000.00 * STANDARD_VAT_RATE, 2)),
            "remarks": "Sales return",
        },
    ]


def build_purchase_rows() -> list[dict]:
    """Return a purchase register with a few seeded anomalies."""
    return [
        # Clean row
        {
            "invoice_no": "INV-P-2001",
            "invoice_date": "2026-04-02",
            "supplier_name": "ACI Limited",
            "supplier_tin": "111222333444",
            "buyer_name": "My Business",
            "buyer_tin": "000000000000",
            "value_excl_vat": 80000.00,
            "vat": round(80000.00 * STANDARD_VAT_RATE, 2),
            "total": 80000.00 + round(80000.00 * STANDARD_VAT_RATE, 2),
            "remarks": "Raw materials",
        },
        # Anomaly: TIN length invalid (Bangladesh TIN = 12 digits)
        {
            "invoice_no": "INV-P-2002",
            "invoice_date": "2026-04-04",
            "supplier_name": "Pran RFL",
            "supplier_tin": "12345",  # too short
            "buyer_name": "My Business",
            "buyer_tin": "000000000000",
            "value_excl_vat": 40000.00,
            "vat": round(40000.00 * STANDARD_VAT_RATE, 2),
            "total": 40000.00 + round(40000.00 * STANDARD_VAT_RATE, 2),
            "remarks": "Packaging goods",
        },
        # Anomaly: total does not equal value_excl_vat + vat
        {
            "invoice_no": "INV-P-2003",
            "invoice_date": "2026-04-06",
            "supplier_name": "Square Textiles",
            "supplier_tin": "555666777888",
            "buyer_name": "My Business",
            "buyer_tin": "000000000000",
            "value_excl_vat": 60000.00,
            "vat": round(60000.00 * STANDARD_VAT_RATE, 2),
            "total": 60000.00 + round(60000.00 * STANDARD_VAT_RATE, 2) + 500.00,  # off by 500
            "remarks": "Total mismatch",
        },
        # Anomaly: duplicate invoice number matches INV-S-1003 (cross-sheet)
        {
            "invoice_no": "INV-S-1003",
            "invoice_date": "2026-04-05",
            "supplier_name": "Cross-Reference Co.",
            "supplier_tin": "777888999000",
            "buyer_name": "My Business",
            "buyer_tin": "000000000000",
            "value_excl_vat": 200000.00,
            "vat": round(200000.00 * 0.10, 2),
            "total": 200000.00 + round(200000.00 * 0.10, 2),
            "remarks": "Same invoice no. used in sales register",
        },
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    os.makedirs(SAMPLES_DIR, exist_ok=True)

    sales_df = _clean(build_sales_rows())
    purchase_df = _clean(build_purchase_rows())

    sales_df.to_excel(SALES_PATH, index=False, sheet_name="Sales")
    purchase_df.to_excel(PURCHASE_PATH, index=False, sheet_name="Purchase")

    print(f"[+] Wrote {SALES_PATH}   ({len(sales_df)} rows)")
    print(f"[+] Wrote {PURCHASE_PATH} ({len(purchase_df)} rows)")
    print(f"[i] Generated at: {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
