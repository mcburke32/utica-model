import streamlit as st
import pandas as pd
from model import run_deal_model

st.set_page_config(page_title="Utica Deal Model", layout="wide")

st.title("Utica Deal Model")

# -----------------------------
# Deal-level inputs
# -----------------------------
st.sidebar.header("Deal-Level Inputs")

deal_inputs = {
    "oil_price": st.sidebar.number_input("Oil Price ($/bbl)", value=70.0),
    "gas_price": st.sidebar.number_input("Gas Price ($/mcf)", value=3.75),
}

# -----------------------------
# Slot table input
# -----------------------------
st.header("Slot Inputs")

default_slots = pd.DataFrame([
    {
        "slot_id": 1,
        "lateral_length": 7000,
        "gross_wells": 2.0,
        "net_acres": 28.6,
        "bid_per_acre": 8000.0,
        "unit_acres": 800.0,
        "pct_unitized": 0.90,
        "net_revenue_interest": 0.80,
        "dc_cost_per_ft": 750.0,
    },
    {
        "slot_id": 2,
        "lateral_length": 10000,
        "gross_wells": 2.0,
        "net_acres": 28.6,
        "bid_per_acre": 8000.0,
        "unit_acres": 800.0,
        "pct_unitized": 0.90,
        "net_revenue_interest": 0.80,
        "dc_cost_per_ft": 750.0,
    }
])

slot_df = st.data_editor(
    default_slots,
    num_rows="dynamic",
    use_container_width=True
)

# -----------------------------
# Clean / fill blank rows
# -----------------------------
slot_df = slot_df.copy()

default_values = {
    "slot_id": 0,
    "lateral_length": 10000,
    "gross_wells": 0.0,
    "net_acres": 0.0,
    "bid_per_acre": 0.0,
    "unit_acres": 800.0,
    "pct_unitized": 0.90,
    "net_revenue_interest": 0.80,
    "dc_cost_per_ft": 750.0,
}

for col, default_val in default_values.items():
    if col in slot_df.columns:
        slot_df[col] = slot_df[col].fillna(default_val)

# optional: drop fully blank rows if any sneak in
slot_df = slot_df.dropna(how="all")

# -----------------------------
# Run model for each slot
# -----------------------------
results_list = []

for _, row in slot_df.iterrows():
    slot_inputs = {
        **deal_inputs,
        "gross_wells": row["gross_wells"],
        "net_acres": row["net_acres"],
        "bid_per_acre": row["bid_per_acre"],
        "lateral_length": row["lateral_length"],
        "dc_cost_per_ft": row["dc_cost_per_ft"],
        "unit_acres": row["unit_acres"],
        "pct_unitized": row["pct_unitized"],
        "net_revenue_interest": row["net_revenue_interest"],
        "flowback_delay": 4,
        "acq_cost_override": None,
    }

    result = run_deal_model(slot_inputs)
    result["slot_id"] = row["slot_id"]

    results_list.append(result)

results_df = pd.DataFrame(results_list)

# -----------------------------
# Slot-level results
# -----------------------------
st.subheader("Slot-Level Results")
st.dataframe(results_df, use_container_width=True)

# -----------------------------
# Deal rollup
# -----------------------------
st.subheader("Deal Summary")

deal_summary = results_df.sum(numeric_only=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Net Revenue", f"${deal_summary['net_revenue']:,.0f}")

with col2:
    st.metric("Total Capex", f"${deal_summary['gross_capex']:,.0f}")

with col3:
    st.metric("Total Acquisition", f"${deal_summary['acquisition_cost']:,.0f}")
