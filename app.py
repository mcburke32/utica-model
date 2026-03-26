import streamlit as st
import pandas as pd
from model import run_simple_model

st.set_page_config(page_title="Utica Deal Model", layout="wide")

st.title("Utica Deal Model")

# -----------------------------
# Sidebar inputs
# -----------------------------
st.sidebar.header("Deal Inputs")

oil_price = st.sidebar.number_input("Oil Price ($/bbl)", value=70.0)
gas_price = st.sidebar.number_input("Gas Price ($/mcf)", value=3.75)
wells = st.sidebar.number_input("Number of Wells", value=2.0)
bid_per_acre = st.sidebar.number_input("Bid per Acre ($)", value=8000.0)
net_acres = st.sidebar.number_input("Net Acres", value=28.6)

# -----------------------------
# Run placeholder model
# -----------------------------
results = run_deal_model(oil_price, gas_price, wells)

acquisition_cost = bid_per_acre * net_acres

# -----------------------------
# Top summary
# -----------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Revenue / Well", f"${results['revenue_per_well']:,.0f}")

with col2:
    st.metric("Total Revenue", f"${results['total_revenue']:,.0f}")

with col3:
    st.metric("Acquisition Cost", f"${acquisition_cost:,.0f}")

# -----------------------------
# Input summary table
# -----------------------------
st.subheader("Input Summary")

input_summary = pd.DataFrame([
    {"Input": "Oil Price", "Value": oil_price},
    {"Input": "Gas Price", "Value": gas_price},
    {"Input": "Number of Wells", "Value": wells},
    {"Input": "Bid per Acre", "Value": bid_per_acre},
    {"Input": "Net Acres", "Value": net_acres},
    {"Input": "Acquisition Cost", "Value": acquisition_cost},
])

st.dataframe(input_summary, use_container_width=True, hide_index=True)
