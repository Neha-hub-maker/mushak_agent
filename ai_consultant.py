"""
ai_consultant.py
================
Loads dynamic multi-user session data via 'MUSHAK_DATA_DIR', asks a premium hosted LLM 
(Claude 3 Opus by default, Groq as a fallback) to interpret the findings for a
Bangladeshi VAT auditor working with Mushak 9.1, and writes a polished markdown report.
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

DATA_DIR = os.getenv("MUSHAK_DATA_DIR", os.path.join(BASE_DIR, "samples"))
os.makedirs(DATA_DIR, exist_ok=True)

ANOMALIES_PATH = os.path.join(DATA_DIR, "detected_anomalies.json")
REPORT_PATH = os.path.join(DATA_DIR, "NBR_Audit_Report.md")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# LLM endpoints
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

STANDARD_VAT_RATE = 0.15

# ---------------------------------------------------------------------------
# System prompt — tuned for a Bangladeshi VAT auditor / Mushak 9.1
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a senior VAT audit consultant for the National Board of Revenue (NBR) of Bangladesh.

Foundational compliance frameworks — these are the ONLY legal sources you may cite. Do not reference SRO 196-Law/2015 or any other SRO/notification:
  - The **Value Added Tax and Supplementary Duty Act, 2012** (the "Act").
  - The **VAT & SD Rules, 2016** (the "Rules").

File formats you validate against (each has a specific legal role):
  - **Mushak 9.1** — monthly VAT return form.
  - **Mushak 6.3** — VAT Challan.
  - **Mushak 6.6** — Purchase & Sales Statement.

Your task: read the structured anomaly data provided (JSON) and produce a concise, professional markdown report a Bangladeshi VAT officer can act on.

When you respond, ALWAYS follow this exact structure:

# NBR Mushak 9.1 Audit Report
## 1. Executive Summary
- 2-4 bullet points summarizing the overall risk and the most material findings.
- Quote the standard VAT rate of 15% when relevant.

## 2. Anomalies by Category
A short subsection per rule (e.g. VAT_RATE_MISMATCH, TIN_MISSING, DUPLICATE_INVOICE, CROSS_SHEET_INVOICE_COLLISION, TOTAL_MISMATCH, MISSING_CHALLAN_REF, LATE_FILING_RISK).
Explain the rule in plain Bangladeshi VAT terms, citing the relevant section of the Act or Rules.

## 3. Corrective Actions
Create EXACTLY ONE GitHub-flavored markdown table mapping unique anomalies. 
Headers MUST BE EXACTLY: | Invoice No | Source Sheet | Issue Detected | Legal Compliance Action |
Do not repeat rows. Collapse multiple issues for the same invoice into one row separated by semicolons.

## 4. Mushak 9.1 Filing Notes
- Mushak 9.1 is filed monthly by the 15th (Rule 25).
- Input VAT is admissible only against valid Mushak 6.1 from a registered person backed by a Mushak 6.3.
- Desk audit powers are under Section 53, and input tax disallowance is under Section 46.

Do not output anything outside of this markdown structure.
"""

def call_claude(api_key: str, user_payload: str) -> str:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    body = {
        "model": "claude-3-opus-20240229",
        "max_tokens": 2000,
        "temperature": 0.2,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_payload}]
    }
    resp = requests.post(ANTHROPIC_URL, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]

def call_groq(api_key: str, user_payload: str) -> str:
    body = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_payload},
        ],
        "temperature": 0.2,
        "max_tokens": 1800,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(GROQ_URL, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

def local_analysis(anomalies: list[dict], summary: dict) -> str:
    """Deterministic markdown report built safely from the JSON alone."""
    sev = summary.get("counts_by_severity", {})
    by_rule = summary.get("counts_by_rule", {})
    sources = summary.get("sources", {})

    lines: list[str] = []
    lines.append("# NBR Mushak 9.1 Audit Report\n")
    lines.append(f"_Generated locally on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_  ")
    lines.append(f"_Standard VAT rate: **{int(STANDARD_VAT_RATE*100)}%**_")
    lines.append("> Note: System generated fallback processing matrix active.\n")

    lines.append("## 1. Executive Summary\n")
    lines.append(f"- **{len(anomalies)}** anomalies detected.")
    if sev.get("HIGH", 0):
        lines.append(f"- **{sev.get('HIGH', 0)} HIGH-severity** issue(s) detected.\n")

    lines.append("## 2. Anomalies by Category\n")
    if not by_rule:
        lines.append("_No anomalies detected._\n")
    else:
        for rule, count in by_rule.items():
            lines.append(f"### {rule} ({count})\nSee anomaly records for specific compliance failures.\n")

    lines.append("## 3. Corrective Actions\n")
    if not anomalies:
        lines.append("_No corrective actions required — no anomalies detected._")
    else:
        n = 1
        seen_actions: set[tuple[str, str]] = set()
        for a in anomalies:
            inv = a.get("invoice_no") or "(no invoice no.)"
            rule = a.get("rule", "UNKNOWN")
            key = (rule, inv)
            if key in seen_actions:
                continue
            seen_actions.add(key)
            lines.append(f"{n}. Resolve the **{rule}** finding on invoice **{inv}** as documented.")
            n += 1
    lines.append("\n## 4. Mushak 9.1 Filing Notes\n")
    lines.append("- Mushak 9.1 must be filed monthly by the 15th (Rule 25).")
    lines.append("- Input VAT credit requires valid Mushak 6.1 and 6.3.")
    return "\n".join(lines)

def build_user_payload(anomalies_doc: dict) -> str:
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
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", os.getenv("anthropic_api_key", "")).strip()
    groq_key = os.getenv("GROQ_API_KEY", os.getenv("groq_api_key", "")).strip()

    # Fallback to local secrets parsing if environment context dropped during fork
    secrets_path = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
    if not anthropic_key and os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r") as sf:
                for line in sf:
                    if "=" in line and "ANTHROPIC_API_KEY" in line.upper():
                        anthropic_key = line.split("=")[1].strip().strip('"').strip("'")
                    elif "=" in line and "GROQ_API_KEY" in line.upper():
                        groq_key = line.split("=")[1].strip().strip('"').strip("'")
        except Exception:
            pass

    # Execution Priority Flow
    if anthropic_key:
        try:
            print("[*] Calling Anthropic Claude Opus ...")
            body = call_claude(anthropic_key, payload)
            source = "claude-3-opus"
        except Exception as e:
            print(f"[!] Claude call failed: {e}", file=sys.stderr)
            
    if not body and groq_key:
        try:
            print("[*] Calling Groq LLM ...")
            body = call_groq(groq_key, payload)
            source = f"groq:{GROQ_MODEL}"
        except Exception as e:
            print(f"[!] Groq call failed: {e}", file=sys.stderr)
            
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