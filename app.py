import streamlit as st
import pandas as pd
from model import run_deal_model

st.set_page_config(page_title="Utica Deal Model", layout="wide")

st.title("Utica Deal Model")

# -----------------------------
# Sidebar inputs
# -----------------------------
st.sidebar.header("Deal Inputs")

use_acq_override = st.sidebar.checkbox("Use Acquisition Cost Override", value=False)

acq_cost_override = None
if use_acq_override:
    acq_cost_override = st.sidebar.number_input("Acquisition Cost Override ($)", value=0.0)

deal_inputs = {
    "oil_price": st.sidebar.number_input("Oil Price ($/bbl)", value=70.0),
    "gas_price": st.sidebar.number_input("Gas Price ($/mcf)", value=3.75),
    "gross_wells": st.sidebar.number_input("Gross Wells", value=2.0),
    "net_acres": st.sidebar.number_input("Net Acres", value=28.6),
    "bid_per_acre": st.sidebar.number_input("Bid per Acre ($)", value=8000.0),
    "lateral_length": st.sidebar.number_input("Lateral Length (ft)", value=10000),
    "dc_cost_per_ft": st.sidebar.number_input("D&C Cost ($/ft)", value=750.0),
    "unit_acres": st.sidebar.number_input("Unit Acres", value=800.0),
    "pct_unitized": st.sidebar.number_input("Pct Unitized", value=0.90),
    "net_revenue_interest": st.sidebar.number_input("Net Revenue Interest", value=0.80),
    "flowback_delay": st.sidebar.number_input("Flowback Delay (months)", value=4),
    "acq_cost_override": acq_cost_override,
}

results = run_deal_model(deal_inputs)

# -----------------------------
# Top summary
# -----------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Working Interest", f"{results['working_interest']:.4f}")

with col2:
    st.metric("Net Wells", f"{results['net_wells_calc']:.4f}")

with col3:
    st.metric("Acquisition Cost", f"${results['acquisition_cost']:,.0f}")

with col4:
    st.metric("Gross Capex", f"${results['gross_capex']:,.0f}")

# -----------------------------
# Revenue summary
# -----------------------------
col5, col6, col7 = st.columns(3)

with col5:
    st.metric("Revenue / Well", f"${results['revenue_per_well']:,.0f}")

with col6:
    st.metric("Gross Revenue", f"${results['gross_revenue']:,.0f}")

with col7:
    st.metric("Net Revenue", f"${results['net_revenue']:,.0f}")

# -----------------------------
# Input summary
# -----------------------------
st.subheader("Deal Input Summary")

input_summary = pd.DataFrame([
    {"Input": k, "Value": v} for k, v in deal_inputs.items()
])

st.dataframe(input_summary, use_container_width=True, hide_index=True)

# -----------------------------
# Results summary
# -----------------------------
st.subheader("Results Summary")

results_summary = pd.DataFrame([
    {"Metric": k, "Value": v} for k, v in results.items()
])

st.dataframe(results_summary, use_container_width=True, hide_index=True)
