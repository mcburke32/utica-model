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
# Slot template builder
# -----------------------------
def build_slot_template(num_slots):
    rows = []
    for i in range(1, num_slots + 1):
        rows.append({
            "slot_id": i,
            "lateral_length": 10000,
            "gross_wells": 2.0,
            "net_acres": 28.6,
            "bid_per_acre": 8000.0,
            "unit_acres": 800.0,
            "pct_unitized": 0.90,
            "net_revenue_interest": 0.80,
            "dc_cost_per_ft": 750.0,
        })
    return pd.DataFrame(rows)

# -----------------------------
# Slot loader controls
# -----------------------------
st.header("Slot Inputs")

col_a, col_b = st.columns([1, 1])

with col_a:
    num_slots = st.number_input("Number of Slots", min_value=1, value=2, step=1)

with col_b:
    if st.button("Load Slots"):
        st.session_state["slot_df"] = build_slot_template(num_slots)

# initialize once
if "slot_df" not in st.session_state:
    st.session_state["slot_df"] = build_slot_template(2)

slot_df = st.data_editor(
    st.session_state["slot_df"],
    num_rows="dynamic",
    use_container_width=True,
    key="slot_editor",
    column_config={
        "slot_id": st.column_config.NumberColumn(
            "Slot",
            format="%d"
        ),
        "lateral_length": st.column_config.NumberColumn(
            "Lateral Length (ft)",
            format="%,d"
        ),
        "gross_wells": st.column_config.NumberColumn(
            "Gross Wells",
            format="%.2f"
        ),
        "net_acres": st.column_config.NumberColumn(
            "Net Acres",
            format="%,.1f"
        ),
        "bid_per_acre": st.column_config.NumberColumn(
            "$/Acre Bid",
            format="$%,d"
        ),
        "unit_acres": st.column_config.NumberColumn(
            "Unit Acres",
            format="%,.0f"
        ),
        "pct_unitized": st.column_config.NumberColumn(
            "% Unitized", format="%.2f"
        ),
        "net_revenue_interest": st.column_config.NumberColumn(
            "NRI", format="%.2f"
        ),
        "dc_cost_per_ft": st.column_config.NumberColumn(
            "D&C ($/ft)",
            format="$%,.0f"
        ),
    }
)

slot_df = slot_df.copy()
default_values = {
    "slot_id": 0,
    "lateral_length": 10000,
    "gross_wells": 2.0,
    "net_acres": 28.6,
    "bid_per_acre": 8000.0,
    "unit_acres": 800.0,
    "pct_unitized": 0.90,
    "net_revenue_interest": 0.80,
    "dc_cost_per_ft": 750.0,
}

for col, default_val in default_values.items():
    if col in slot_df.columns:
        slot_df[col] = slot_df[col].fillna(default_val)

st.session_state["slot_df"] = slot_df

# -----------------------------
# Slot-level results
# -----------------------------
st.subheader("Slot-Level Results")

st.dataframe(
    results_df.style.format({
        "acquisition_cost": "${:,.0f}",
        "gross_capex": "${:,.0f}",
        "gross_revenue": "${:,.0f}",
        "net_revenue": "${:,.0f}",
        "revenue_per_well": "${:,.0f}",
        "working_interest": "{:.4f}",
        "net_wells_calc": "{:.4f}",
    }),
    use_container_width=True
)

# -----------------------------
# Deal rollup
# -----------------------------
st.subheader("Deal Summary")

total_net_acres = slot_df["net_acres"].sum()
total_acquisition = results_df["acquisition_cost"].sum()

blended_bid = (
    total_acquisition / total_net_acres
    if total_net_acres > 0 else 0
)

# placeholder until we wire real returns
deal_irr = 0.25
deal_moic = 2.0

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Net Acres", f"{total_net_acres:,.1f}")

with col2:
    st.metric("Acquisition Price", f"${total_acquisition:,.0f}")

with col3:
    st.metric("$/Acre Bid", f"${blended_bid:,.0f}")

with col4:
    st.metric("IRR", f"{deal_irr:.1%}")

with col5:
    st.metric("MOIC", f"{deal_moic:.2f}x")

# -----------------------------
# Monthly Deal Cash Flow
# -----------------------------
st.subheader("Monthly Deal Cash Flow")

st.dataframe(
    deal_df.style.format({
        "oil": "{:,.0f}",
        "gas": "{:,.0f}",
        "ngl": "{:,.0f}",
        "oil_rev": "${:,.0f}",
        "gas_rev": "${:,.0f}",
        "ngl_rev": "${:,.0f}",
        "total_revenue": "${:,.0f}",
        "loe": "${:,.0f}",
        "tax": "${:,.0f}",
        "total_cost": "${:,.0f}",
        "cash_flow": "${:,.0f}",
    }),
    use_container_width=True,
    hide_index=True
)
