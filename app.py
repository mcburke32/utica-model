import streamlit as st
import pandas as pd
from model import run_deal_model

st.set_page_config(page_title="Utica Deal Model", layout="wide")

st.title("Utica Deal Model")


# -----------------------------
# Helpers
# -----------------------------
@st.cache_data
def load_tc_names():
    tc_metadata = pd.read_excel("type_curve_library.xlsx", sheet_name="tc_metadata")
    return tc_metadata["tc_name"].dropna().unique().tolist()


def build_slot_template(num_slots):
    rows = []
    for i in range(1, num_slots + 1):
        rows.append({
            "slot_id": i,
            "tc_name": "Choose TC",
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


def resize_slot_df(existing_df, target_slots):
    existing_df = existing_df.copy().reset_index(drop=True)
    current_slots = len(existing_df)

    if current_slots == target_slots:
        return existing_df

    if current_slots < target_slots:
        new_rows = []
        for i in range(current_slots + 1, target_slots + 1):
            new_rows.append({
                "slot_id": i,
                "tc_name": "Choose TC",
                "lateral_length": 10000,
                "gross_wells": 2.0,
                "net_acres": 28.6,
                "bid_per_acre": 8000.0,
                "unit_acres": 800.0,
                "pct_unitized": 0.90,
                "net_revenue_interest": 0.80,
                "dc_cost_per_ft": 750.0,
            })
        if new_rows:
            existing_df = pd.concat([existing_df, pd.DataFrame(new_rows)], ignore_index=True)
        return existing_df

    trimmed_df = existing_df.iloc[:target_slots].copy().reset_index(drop=True)
    trimmed_df["slot_id"] = range(1, target_slots + 1)
    return trimmed_df


# -----------------------------
# Session state init
# -----------------------------
if "slot_df" not in st.session_state:
    st.session_state["slot_df"] = build_slot_template(2)

if "deal_df" not in st.session_state:
    st.session_state["deal_df"] = None

if "irr" not in st.session_state:
    st.session_state["irr"] = None

if "moic" not in st.session_state:
    st.session_state["moic"] = None

if "model_has_run" not in st.session_state:
    st.session_state["model_has_run"] = False


# -----------------------------
# Deal-level inputs
# -----------------------------
st.sidebar.header("Deal-Level Inputs")

deal_inputs = {
    "oil_price": st.sidebar.number_input("Oil Price ($/bbl)", value=70.0),
    "gas_price": st.sidebar.number_input("Gas Price ($/mcf)", value=3.75),
}


# -----------------------------
# Slot controls
# -----------------------------
st.header("Slot Inputs")

tc_names = ["Choose TC"] + load_tc_names()

col_a, col_b, col_c = st.columns([1, 1, 1])

with col_a:
    num_slots = st.number_input("Number of Slots", min_value=1, value=len(st.session_state["slot_df"]), step=1)

with col_b:
    if st.button("Load Slots"):
        st.session_state["slot_df"] = resize_slot_df(st.session_state["slot_df"], num_slots)
        st.session_state["model_has_run"] = False

with col_c:
    run_model_clicked = st.button("Run Model")


# -----------------------------
# Editable slot table
# -----------------------------
slot_df = st.data_editor(
    st.session_state["slot_df"],
    num_rows="fixed",
    use_container_width=True,
    key="slot_editor",
    column_config={
        "slot_id": st.column_config.NumberColumn("Slot", format="%d", disabled=True),
        "tc_name": st.column_config.SelectboxColumn(
            "Type Curve",
            options=tc_names,
            required=True,
        ),
        "lateral_length": st.column_config.NumberColumn("Lateral Length (ft)", format="%,d"),
        "gross_wells": st.column_config.NumberColumn("Gross Wells", format="%.2f"),
        "net_acres": st.column_config.NumberColumn("Net Acres", format="%,.1f"),
        "bid_per_acre": st.column_config.NumberColumn("$/Acre Bid", format="$%,d"),
        "unit_acres": st.column_config.NumberColumn("Unit Acres", format="%,.0f"),
        "pct_unitized": st.column_config.NumberColumn("% Unitized", format="%.2f"),
        "net_revenue_interest": st.column_config.NumberColumn("NRI", format="%.2f"),
        "dc_cost_per_ft": st.column_config.NumberColumn("D&C ($/ft)", format="$%,.0f"),
    }
).copy()

default_values = {
    "slot_id": 0,
    "tc_name": "Choose TC",
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

slot_df["slot_id"] = range(1, len(slot_df) + 1)

st.session_state["slot_df"] = slot_df


# -----------------------------
# Run model only when button clicked
# -----------------------------
if run_model_clicked:
    if (slot_df["tc_name"] == "Choose TC").any():
        st.warning("Please select a Type Curve for all slots before running the model.")
        st.session_state["model_has_run"] = False
    else:
        all_slots_df, deal_df, irr, moic = run_deal_model(slot_df, deal_inputs)
        st.session_state["deal_df"] = deal_df
        st.session_state["irr"] = irr
        st.session_state["moic"] = moic
        st.session_state["model_has_run"] = True


# -----------------------------
# Show results only after model run
# -----------------------------
if st.session_state["model_has_run"] and st.session_state["deal_df"] is not None:
    deal_df = st.session_state["deal_df"]
    irr = st.session_state["irr"]
    moic = st.session_state["moic"]

    st.subheader("Deal Summary")

    total_net_acres = slot_df["net_acres"].sum()
    total_acquisition = (slot_df["net_acres"] * slot_df["bid_per_acre"]).sum()
    blended_bid = total_acquisition / total_net_acres if total_net_acres > 0 else 0

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Net Acres", f"{total_net_acres:,.1f}")

    with col2:
        st.metric("Acquisition Price", f"${total_acquisition:,.0f}")

    with col3:
        st.metric("$/Acre Bid", f"${blended_bid:,.0f}")

    with col4:
        st.metric("IRR", f"{irr:.1%}" if irr is not None else "N/A")

    with col5:
        st.metric("MOIC", f"{moic:.2f}x" if moic is not None else "N/A")

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
else:
    st.info("Set your slot inputs and click Run Model.")
