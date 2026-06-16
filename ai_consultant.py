"""
ai_consultant.py
================
Loads dynamic multi-user session data via 'MUSHAK_DATA_DIR', asks a free hosted LLM 
(Groq by default, Google AI Studio as a fallback) to interpret the findings for a
Bangladeshi VAT auditor working with Mushak 9.1, and writes a polished markdown report.

Enhanced with systemic knowledge of advanced rules:
  - MISSING_CHALLAN_REF (Missing Mushak 6.3 Challan for input tax eligibility)
  - LATE_FILING_RISK (Transactions bypassing the statutory 15th-of-the-month rule)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration (Dynamic Multi-User Session Isolation)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Grab the secure isolated session path passed down by app.py. 
# Fallback to standard "samples" folder for local terminal testing.
DATA_DIR = os.getenv("MUSHAK_DATA_DIR", os.path.join(BASE_DIR, "samples"))
os.makedirs(DATA_DIR, exist_ok=True)

ANOMALIES_PATH = os.path.join(DATA_DIR, "detected_anomalies.json")
REPORT_PATH = os.path.join(DATA_DIR, "NBR_Audit_Report.md")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Free LLM endpoints
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)

STANDARD_VAT_RATE = 0.15

# ---------------------------------------------------------------------------
# System prompt — tuned for a Bangladeshi VAT auditor / Mushak 9.1
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a senior VAT audit consultant for the National Board of Revenue (NBR) of Bangladesh.

Foundational compliance frameworks — these are the ONLY legal sources you
may cite. Do not reference SRO 196-Law/2015 or any other SRO/notification:
  - The **Value Added Tax and Supplementary Duty Act, 2012** (the "Act"),
    including all sections cited below (e.g. section 46 on input-tax
    disallowance, section 53 on desk-audit powers).
  - The **VAT & SD Rules, 2016** (the "Rules"), including their schedules
    that prescribe the Mushak forms.

File formats you validate against (each has a specific legal role):
  - **Mushak 9.1** — monthly VAT return form (output VAT, input VAT credit,
    net payable). This is the primary reconciliation target.
  - **Mushak 6.3** — VAT Challan (deposit of VAT into a government treasury
    account). The amount on Mushak 9.1 must reconcile with the total paid
    in via valid Mushak 6.3 challans.
  - **Mushak 6.6** — Purchase & Sales Statement / Annexure supporting
    Mushak 9.1. Each line in Mushak 6.6 must reconcile with the underlying
    Mushak 6.1 (Tax Invoice) and the TIN of the counter-party.

Your task: read the structured anomaly data provided (JSON) and produce a
concise, professional markdown report a Bangladeshi VAT officer can act on.

When you respond, ALWAYS follow this exact structure:

# NBR Mushak 9.1 Audit Report
## 1. Executive Summary
- 2-4 bullet points summarizing the overall risk and the most material findings.
- Quote the **standard VAT rate of 15%** when relevant.
- Frame findings against the **Value Added Tax and Supplementary Duty Act, 2012**
  and the **VAT & SD Rules, 2016**.

## 2. Anomalies by Category
A short subsection per rule (e.g. VAT_RATE_MISMATCH, TIN_MISSING,
DUPLICATE_INVOICE, CROSS_SHEET_INVOICE_COLLISION, TOTAL_MISMATCH,
NEGATIVE_TOTAL, TIN_FORMAT_INVALID, NEGATIVE_VAT, NEGATIVE_BASE_VALUE,
MISSING_CHALLAN_REF, LATE_FILING_RISK).
For each: one paragraph explaining the rule in plain Bangladeshi VAT terms,
citing the relevant section of the Act or Rules, and how it affects the
Mushak 9.1 return, the supporting Mushak 6.3 challan, and the Mushak 6.6
purchase/sales statement.

## 3. Corrective Actions
For Section 3, extract the unique anomalies from the JSON and map them
directly into a clean markdown table. Ensure every row corresponds to a
real anomaly inside the data. Absolutely do not repeat or loop rows.

The table must be laid out EXACTLY as a GitHub-flavored markdown table
with these column headers, in this order, and nothing else:

| Invoice No | Source Sheet | Issue Detected | Legal Compliance Action |

Formatting rules for the table:
- One row per unique anomaly (deduplicate by `invoice_no` + `rule`).
- Leave the table header row followed by a single separator row
  (`|---|---|---|---|`); do not add extra divider rows.
- If multiple anomalies share the same `invoice_no`, collapse them into
  ONE row and join the issues with a semicolon inside the
  "Issue Detected" cell. The "Legal Compliance Action" cell must then
  list every corrective step (re-issue invoice, update Mushak 6.6,
  re-submit Mushak 9.1, provide Mushak 6.3 record, etc.) joined by semicolons.
- Use `sales` or `purchase` verbatim in the "Source Sheet" column.
- Never output a row that is not backed by a record in the JSON.
- Never loop, pad, or repeat rows — the number of data rows must equal
  the number of unique anomaly clusters, full stop.
- If there are zero anomalies, output the table header + separator
  rows only and a single note row "| _No corrective actions required._ |  |  |  |".

## 4. Mushak 9.1 Filing Notes
- Mushak 9.1 is filed monthly by the **15th of the following month** under
  the **VAT & SD Rules, 2016** (specifically Rule 25). Late entries pose statutory interest penalties.
- Input VAT on Mushak 9.1 is admissible **only** against a valid Tax Invoice
  (Mushak 6.1) from a registered person with a verified 12-digit TIN, backed strictly by a corresponding **Mushak 6.3** tax challan, and must reconcile with the supporting Mushak 6.6 (Purchase & Sales Statement).
- The tax payable declared in Mushak 9.1 must equal the VAT actually
  deposited via valid **Mushak 6.3** challans; any mismatch is a
  red-flag for a desk audit under **section 53 of the Value Added Tax
  and Supplementary Duty Act, 2012**, and may trigger disallowance of
  input tax credit under **section 46** of the same Act.

Rules you must obey:
- Write in English, professional but plain enough for a tax officer.
- Cite ONLY the **Value Added Tax and Supplementary Duty Act, 2012** and
  the **VAT & SD Rules, 2016**. Do not cite SROs, circulars, or any
  1991-era Rules — those are superseded.
- Never invent invoice numbers, TINs, or amounts not present in the JSON.
- For Section 3, extract the unique anomalies from the JSON and map them
  directly into a clean markdown table. Ensure every row corresponds to a
  real anomaly inside the data. Absolutely do not repeat or loop rows.
- If no anomalies are provided, still output the report with empty sections
  and state "No anomalies detected."
- Output ONLY the markdown report. Do not add code fences, preamble, or
  any text outside the report.
"""

def call_groq(api_key: str, user_payload: str) -> str:
    body = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_payload},
        ],
        "temperature": 0.2,
        "max_tokens": 1800,
        "frequency_penalty": 0.5,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(GROQ_URL, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

def call_gemini(api_key: str, user_payload: str) -> str:
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": user_payload}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1800,
            "frequencyPenalty": 0.5,
        },
    }
    resp = requests.post(
        f"{GEMINI_URL}?key={api_key}", json=body, timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

def local_analysis(anomalies: list[dict], summary: dict) -> str:
    """Deterministic markdown report built safely from the JSON alone."""
    sev = summary.get("counts_by_severity", {})
    by_rule = summary.get("counts_by_rule", {})
    sources = summary.get("sources", {})

    lines: list[str] = []
    lines.append("# NBR Mushak 9.1 Audit Report")
    lines.append("")
    lines.append(f"_Generated locally on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_  ")
    lines.append(f"_Standard VAT rate: **{int(STANDARD_VAT_RATE*100)}%** per the VAT & SD Act, 2012._")
    lines.append("")
    lines.append("> Note: System generated fallback processing matrix active.")
    lines.append("")

    # 1. Executive summary
    lines.append("## 1. Executive Summary")
    lines.append("")
    total = len(anomalies)
    high = sev.get("HIGH", 0)
    medium = sev.get("MEDIUM", 0)
    low = sev.get("LOW", 0)
    lines.append(f"- **{total}** anomalies detected in the Mushak 9.1 dataset "
                 f"(HIGH: {high}, MEDIUM: {medium}, LOW: {low}).")
    lines.append(f"- Sources audited: **{sources.get('sales_rows', 0)}** sales rows "
                 f"and **{sources.get('purchase_rows', 0)}** purchase rows.")
    if high:
        lines.append(f"- **{high} HIGH-severity** issue(s) — these will likely cause the "
                     "Mushak 9.1 return to be rejected or flagged in a desk audit.")
    else:
        lines.append("- No HIGH-severity issues detected.")
    lines.append("")

    # 2. Anomalies by category
    lines.append("## 2. Anomalies by Category")
    lines.append("")
    rule_descriptions = {
        "VAT_RATE_MISMATCH": (
            "VAT was not calculated at the standard 15% rate prescribed by the "
            "VAT & SD Act, 2012. Mushak 9.1 requires VAT to be reported at the "
            "applicable rate; under- or over-charging causes a mismatch with "
            "Mushak 6.1 (Tax Invoice) and may trigger a demand notice under "
            "section 53 of the Act."
        ),
        "TIN_MISSING": (
            "A 12-digit Taxpayer Identification Number (TIN) is mandatory on "
            "every Mushak 9.1 line. Without a TIN, the corresponding input VAT "
            "cannot be claimed and the output VAT line may be disallowed."
        ),
        "TIN_FORMAT_INVALID": (
            "TINs issued by NBR are exactly 12 numeric digits. Anything shorter, "
            "longer, or containing non-digits will be rejected by the Mushak "
            "software's validation routine."
        ),
        "DUPLICATE_INVOICE": (
            "An invoice number was used more than once within the same register. "
            "Mushak 9.1 expects every invoice to be unique; duplicates can be "
            "interpreted as double-counting of turnover or input VAT."
        ),
        "CROSS_SHEET_INVOICE_COLLISION": (
            "The same invoice number appears in both the sales and purchase "
            "registers. This is a strong red flag for circular/recycled invoices "
            "and can lead to cancellation of input tax credit under section 46."
        ),
        "TOTAL_MISMATCH": (
            "The declared invoice total does not equal value_excl_vat + VAT. "
            "Mushak 9.1 cross-foots every line; mismatches cause the return to "
            "fail validation."
        ),
        "NEGATIVE_TOTAL": (
            "A negative invoice total was posted. Sales returns and discounts "
            "must be reported as separate credit notes (Mushak 6.2), not as a "
            "negative line on the original invoice."
        ),
        "NEGATIVE_VAT": (
            "Negative VAT on a line. Credit notes for VAT must follow the "
            "credit-note procedure under the VAT Rules, 1991."
        ),
        "NEGATIVE_BASE_VALUE": (
            "Negative base value. Refunds/returns must be processed as a "
            "distinct credit-note line in Mushak 9.1."
        ),
        "MISSING_CHALLAN_REF": (
            "A corresponding Mushak 6.3 invoice/challan tracking number is missing on a purchase "
            "transaction line. Under Section 46 of the Act, input tax credit cannot be claimed "
            "unless backed by an explicit, verifiable government tax token reference."
        ),
        "LATE_FILING_RISK": (
            "The transaction processing date or submission record bypasses the absolute 15th of the month "
            "cutoff rule established by Rule 25 of the VAT & SD Rules, 2016. Delayed filings trigger "
            "statutory interest costs and standard corporate audit exposure."
        ),
    }
    if not by_rule:
        lines.append("_No anomalies detected._")
        lines.append("")
    else:
        for rule, count in by_rule.items():
            desc = rule_descriptions.get(rule, "See anomaly records for details.")
            lines.append(f"### {rule} ({count})")
            lines.append("")
            lines.append(desc)
            lines.append("")

    # 3. Corrective actions
    lines.append("## 3. Corrective Actions")
    lines.append("")
    if not anomalies:
        lines.append("_No corrective actions required — no anomalies detected._")
    else:
        n = 1
        seen_actions: set[tuple[str, str]] = set()
        for a in anomalies:
            inv = a.get("invoice_no") or "(no invoice no.)"
            tin = a.get("tin") or "(no TIN)"
            rule = a.get("rule", "UNKNOWN")
            key = (rule, inv)
            if key in seen_actions:
                continue
            seen_actions.add(key)
            if rule == "VAT_RATE_MISMATCH":
                lines.append(
                    f"{n}. Re-issue invoice **{inv}** with VAT recomputed at the "
                    f"standard {int(STANDARD_VAT_RATE*100)}% rate (target VAT = "
                    f"BDT {a.get('expected')}). Re-submit Mushak 9.1 for the period."
                )
            elif rule == "TIN_MISSING":
                lines.append(
                    f"{n}. Collect a valid 12-digit TIN from the counter-party on "
                    f"invoice **{inv}** (current: '{a.get('actual')}') before claiming "
                    f"any related input VAT."
                )
            elif rule == "TIN_FORMAT_INVALID":
                lines.append(
                    f"{n}. Correct the TIN on invoice **{inv}** to a 12-digit numeric "
                    f"value (current: '{a.get('actual')}', expected: '{a.get('expected')}')."
                )
            elif rule == "DUPLICATE_INVOICE":
                lines.append(
                    f"{n}. Renumber the duplicate invoice **{inv}** so each line in the "
                    f"register is unique, then re-submit Mushak 9.1."
                )
            elif rule == "CROSS_SHEET_INVOICE_COLLISION":
                lines.append(
                    f"{n}. Investigate invoice **{inv}** which appears in BOTH the sales "
                    f"and purchase registers. Confirm whether it is a recycled invoice; "
                    f"if so, remove it from the offending register and report the "
                    f"correct transaction in Mushak 9.1."
                )
            elif rule == "TOTAL_MISMATCH":
                lines.append(
                    f"{n}. Reconcile invoice **{inv}**: total should be "
                    f"BDT {a.get('expected')} (base + VAT), but is BDT {a.get('actual')}. "
                    f"Re-foot and re-submit."
                )
            elif rule == "MISSING_CHALLAN_REF":
                lines.append(
                    f"{n}. Locate and supply the valid government Mushak 6.3 Tax Challan tracking reference "
                    f"for purchase entry **{inv}** to preserve legal eligibility for input VAT rebate under Section 46."
                )
            elif rule == "LATE_FILING_RISK":
                lines.append(
                    f"{n}. Review filing delay context for invoice **{inv}** (filed: '{a.get('actual')}'). "
                    f"Ensure future transactions are logged by the statutory 15th-of-the-month deadline to avoid penalties under Rule 25."
                )
            elif rule.startswith("NEGATIVE_"):
                lines.append(
                    f"{n}. Reverse the negative line on **{inv}** and record the "
                    f"return/credit via a proper Mushak 6.2 credit note in Mushak 9.1."
                )
            else:
                lines.append(
                    f"{n}. Resolve the **{rule}** finding on invoice **{inv}** "
                    f"(TIN {tin}) as documented in the anomaly register."
                )
            n += 1
    lines.append("")

    # 4. Filing notes
    lines.append("## 4. Mushak 9.1 Filing Notes")
    lines.append("")
    lines.append("- Mushak 9.1 (VAT Return) must be filed **monthly by the 15th of the "
                 "following month** (Rule 25 of VAT & SD Rules, 2016).")
    lines.append("- Input VAT credit is admissible **only** against a valid Mushak 6.1 "
                 "(Tax Invoice) issued by a registered person holding a verified "
                 "12-digit TIN, explicitly supported by a matching **Mushak 6.3**.")
    lines.append("- Any inconsistency between turnover declared in Mushak 9.1 and the "
                 "purchase/sales ledgers may trigger a desk audit under **section 53** "
                 "of the VAT & SD Act, 2012, and disallowance of input credit under "
                 "**section 46**.")
    lines.append("- Negative entries and credit notes must be reported through the "
                 "credit-note mechanism in Mushak 9.1, never as a negative line.")
    lines.append("")
    return "\n".join(lines)

def build_user_payload(anomalies_doc: dict) -> str:
    """Compact, model-friendly summary of the audit JSON."""
    return (
        "Below is the JSON output of our local Mushak 9.1 audit engine. "
        "Analyze it and produce the markdown report as instructed.\n\n"
        f"```json\n{json.dumps(anomalies_doc, indent=2, ensure_ascii=False)}\n```"
    )

def render_report(markdown_body: str, source: str) -> str:
    return "\n\n" + markdown_body.strip() + "\n"

def main() -> None:
    load_dotenv(ENV_PATH)
    if not os.path.exists(ANOMALIES_PATH):
        print(f"[!] {ANOMALIES_PATH} not found. Run audit_engine.py first.", file=sys.stderr)
        sys.exit(1)

    with open(ANOMALIES_PATH, "r", encoding="utf-8") as f:
        anomalies_doc: dict[str, Any] = json.load(f)

    anomalies = anomalies_doc.get("anomalies", [])
    payload = build_user_payload(anomalies_doc)

    source = "local"
    body: str = ""
    
    # Advanced Environment Variable Lookahead for Streamlit Subprocess context
    groq_key = os.getenv("GROQ_API_KEY", os.getenv("groq_api_key", "")).strip()
    google_key = os.getenv("GOOGLE_API_KEY", os.getenv("google_api_key", "")).strip()

    # Fallback to local secrets parsing if environment context dropped during fork
    secrets_path = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
    if not groq_key and os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r") as sf:
                for line in sf:
                    if "=" in line and "GROQ_API_KEY" in line.upper():
                        groq_key = line.split("=")[1].strip().strip('"').strip("'")
        except Exception:
            pass

    if groq_key:
        try:
            print("[*] Calling Groq LLM ...")
            body = call_groq(groq_key, payload)
            source = f"groq:{GROQ_MODEL}"
        except Exception as e:
            print(f"[!] Groq call failed: {e}", file=sys.stderr)
            
    if not body and google_key:
        try:
            print("[*] Calling Google AI Studio (Gemini) ...")
            body = call_gemini(google_key, payload)
            source = "gemini-1.5-flash"
        except Exception as e:
            print(f"[!] Gemini call failed: {e}", file=sys.stderr)
            
    if not body:
        print("[*] No LLM reachable — generating local report.")
        body = local_analysis(anomalies, anomalies_doc)
        source = "local-fallback"

    # Clean off any system code block fences wrapped around the output markdown
    if body.strip().startswith("```"):
        lines = body.strip().split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        body = "\n".join(lines)

    if not body.lstrip().lower().startswith("# nbr"):
        body = "# NBR Mushak 9.1 Audit Report\n\n" + body.lstrip()

    final = render_report(body, source)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(final)
    print(f"[+] Wrote {REPORT_PATH} (source={source}, {len(anomalies)} anomalies)")

if __name__ == "__main__":
    main()