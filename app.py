import streamlit as st
import os
import sys
import subprocess
import pandas as pd
import markdown
import tempfile
from xhtml2pdf import pisa
from io import BytesIO
import json

# --- CORPORATE THEME & PAGE SETUP ---
st.set_page_config(
    page_title="MushakGuard Enterprise Agent", 
    layout="wide", 
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)

# Custom Minimalist Corporate CSS Injection
st.markdown("""
    <style>
        /* Global Body & Minimal Background adjustments */
        .main { background-color: #fafbfc; }
        
        /* Premium Sidebar Customization */
        section[data-testid="stSidebar"] {
            background-color: #111827 !important;
            color: #ffffff;
        }
        section[data-testid="stSidebar"] h1, 
        section[data-testid="stSidebar"] h2, 
        section[data-testid="stSidebar"] h3, 
        section[data-testid="stSidebar"] p {
            color: #f3f4f6 !important;
        }
        
        /* Custom Metric Cards Design */
        .kpi-card {
            background-color: #ffffff;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            border-left: 4px solid #cccccc;
            margin-bottom: 10px;
        }
        .kpi-high { border-left-color: #ef4444; }
        .kpi-med { border-left-color: #f59e0b; }
        .kpi-total { border-left-color: #3b82f6; }
        
        .kpi-val { font-size: 24px; font-weight: bold; color: #111827; margin: 0; }
        .kpi-lbl { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin: 0; }
    </style>
""", unsafe_allow_html=True)

# --- APPLICATION HEADER ---
st.write("### 🛡️ MushakGuard Enterprise Agent")
st.caption("Enterprise-grade pre-filing compliance validation and automated risk analysis for NBR Mushak 9.1 registries.")
st.write("---")

# --- MULTI-USER SESSION ISOLATION SETUP ---
if "user_data_dir" not in st.session_state:
    st.session_state["user_data_dir"] = tempfile.mkdtemp(prefix="mushakguard_")

USER_DIR = st.session_state["user_data_dir"]

# --- SIDEBAR CONTROL CONTROL PANEL ---
st.sidebar.markdown("## 📥 Registry Ingestion")
sales_file = st.sidebar.file_uploader("Sales Registry (Excel)", type=["xlsx"])
purchase_file = st.sidebar.file_uploader("Purchase Registry (Excel)", type=["xlsx"])

st.sidebar.write("---")
st.sidebar.markdown("## ⚙️ Processing Core")

if sales_file and purchase_file:
    if st.sidebar.button("🚀 Execute Audit Analytics"):
        with st.spinner("Crunching data registries against NBR framework..."):
            try:
                sales_path = os.path.join(USER_DIR, "sales_register.xlsx")
                purchase_path = os.path.join(USER_DIR, "purchase_register.xlsx")
                
                with open(sales_path, "wb") as f:
                    f.write(sales_file.getbuffer())
                with open(purchase_path, "wb") as f:
                    f.write(purchase_file.getbuffer())
                
                env_context = os.environ.copy()
                env_context["MUSHAK_DATA_DIR"] = USER_DIR
                
                # FIXED: Execute using sys.executable to stay within virtual env path boundaries
                subprocess.run([sys.executable, "audit_engine.py"], env=env_context, check=True)
                subprocess.run([sys.executable, "ai_consultant.py"], env=env_context, check=True)
                
                st.sidebar.success("Analysis cycle completed!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Pipeline error: {e}")
else:
    st.sidebar.info("Upload active sales & purchase registries to unlock core audit analytics engine.")

# --- DYNAMIC RISK METRIC CARDS OVERVIEW ---
anomalies_json_path = os.path.join(USER_DIR, "detected_anomalies.json")
if os.path.exists(anomalies_json_path):
    try:
        with open(anomalies_json_path, "r", encoding="utf-8") as jf:
            audit_data = json.load(jf)
            
        counts = audit_data.get("counts_by_severity", {})
        total_issues = len(audit_data.get("anomalies", []))
        
        # Display Row Cards layout dynamically
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="kpi-card kpi-total"><p class="kpi-val">{total_issues}</p><p class="kpi-lbl">Total Anomalies</p></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="kpi-card kpi-high"><p class="kpi-val" style="color: #ef4444;">{counts.get("HIGH", 0)}</p><p class="kpi-lbl">High Risk (Sec 46/53)</p></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="kpi-card kpi-med"><p class="kpi-val" style="color: #f59e0b;">{counts.get("MEDIUM", 0)}</p><p class="kpi-lbl">Medium Risk (Rule 25)</p></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="kpi-card kpi-total" style="border-left-color: #10b981;"><p class="kpi-val" style="color: #10b981;">{audit_data["sources"].get("sales_rows", 0) + audit_data["sources"].get("purchase_rows", 0)}</p><p class="kpi-lbl">Total Audited Lines</p></div>', unsafe_allow_html=True)
    except Exception:
        pass

st.write(" ")

# --- INTERACTIVE DATA PREVIEW ZONE ---
if sales_file or purchase_file:
    with st.expander("📊 Inspect Uploaded Registry Records", expanded=False):
        tab1, tab2 = st.tabs(["Sales Ledger View", "Purchase Ledger View"])
        with tab1:
            if sales_file:
                # UPDATED: Replaced deprecated use_container_width parameter 
                st.dataframe(pd.read_excel(sales_file).head(10), width="stretch")
        with tab2:
            if purchase_file:
                # UPDATED: Replaced deprecated use_container_width parameter 
                st.dataframe(pd.read_excel(purchase_file).head(10), width="stretch")

# --- PDF GENERATOR HELPER ---
def convert_md_to_pdf(md_text):
    html_content = markdown.markdown(md_text, extensions=['tables'])
    pdf_style = """
    <style>
        body { font-family: Helvetica, Arial, sans-serif; color: #333333; }
        h1 { color: #111827; font-size: 24px; border-bottom: 2px solid #111827; padding-bottom: 5px; }
        h2 { color: #1f2937; font-size: 16px; margin-top: 18px; border-bottom: 1px solid #e5e7eb; padding-bottom: 3px; }
        h3 { color: #4b5563; font-size: 12px; margin-top: 12px; }
        p, ul, li { font-size: 11px; line-height: 1.5; text-align: justify; }
        table { width: 100%; margin-top: 15px; border: 1px solid #e5e7eb; border-collapse: collapse; }
        th { background-color: #f9fafb; font-weight: bold; font-size: 11px; border: 1px solid #e5e7eb; padding: 6px; text-align: left; }
        td { font-size: 10px; border: 1px solid #e5e7eb; padding: 6px; }
    </style>
    """
    full_html = f"<html><body>{pdf_style}{html_content}</body></html>"
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(full_html, dest=pdf_buffer)
    return None if pisa_status.err else pdf_buffer.getvalue()

# --- AUTOMATED COMPLIANCE ASSESSMENT VIEWER ---
report_path = os.path.join(USER_DIR, "NBR_Audit_Report.md")
if os.path.exists(report_path):
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("#### 📋 Compiled Audit Certificate Findings")
    with col2:
        pdf_bytes = convert_md_to_pdf(report_content)
        if pdf_bytes:
            # UPDATED: Replaced deprecated use_container_width parameter 
            st.download_button(
                label="📥 Export Certified PDF",
                data=pdf_bytes,
                file_name="MushakGuard_Audit_Report.pdf",
                mime="application/pdf",
                width="stretch"
            )
            
    st.markdown(report_content)
else:
    st.info("No compliance reports compiled in the current system session. Use the ingestion module to start.")