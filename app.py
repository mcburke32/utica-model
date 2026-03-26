import streamlit as st
from model import run_simple_model

st.set_page_config(page_title="Utica Deal Model", layout="wide")

st.title("Utica Deal Model")
st.header("Basic Test Model")

st.subheader("Inputs")
oil_price = st.number_input("Oil Price ($/bbl)", value=70.0)
gas_price = st.number_input("Gas Price ($/mcf)", value=3.75)
wells = st.number_input("Number of Wells", value=2.0)

results = run_simple_model(oil_price, gas_price, wells)

st.subheader("Outputs")
st.metric("Revenue / Well", f"${results['revenue_per_well']:,.0f}")
st.metric("Total Revenue", f"${results['total_revenue']:,.0f}")
