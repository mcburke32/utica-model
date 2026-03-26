import pandas as pd
import numpy as np
from datetime import timedelta

try:
    import pyxirr
except:
    pyxirr = None


# -----------------------------
# Load Type Curve Library
# -----------------------------
def load_type_curve_library(file_path="type_curve_library.xlsx"):
    tc_monthly = pd.read_excel(file_path, sheet_name="tc_monthly")
    tc_metadata = pd.read_excel(file_path, sheet_name="tc_metadata")

    return tc_monthly, tc_metadata


# -----------------------------
# Get Type Curve
# -----------------------------
def get_type_curve(tc_name, tc_monthly, tc_metadata):
    tc = tc_monthly[tc_monthly["tc_name"] == tc_name].copy()

    base_length = tc_metadata.loc[
        tc_metadata["tc_name"] == tc_name, "base_lateral"
    ].values[0]

    return tc, base_length


# -----------------------------
# Build Production Timeline
# -----------------------------
def build_production(tc, lateral_length, base_length, start_date):
    scale_factor = lateral_length / base_length

    tc = tc.copy()
    tc["oil"] = tc["oil"] * scale_factor
    tc["gas"] = tc["gas"] * scale_factor

    tc["date"] = tc["month"].apply(
        lambda x: start_date + pd.DateOffset(months=int(x - 1))
    )

    return tc


# -----------------------------
# NGL Calculations
# -----------------------------
def calc_ngl(gas_series, ngl_yield):
    # mcf → barrels
    return gas_series * ngl_yield / 6


# -----------------------------
# Revenue
# -----------------------------
def calc_revenue(df, oil_price, gas_price, ngl_price=25):
    df = df.copy()

    df["oil_rev"] = df["oil"] * oil_price
    df["gas_rev"] = df["gas"] * gas_price
    df["ngl_rev"] = df["ngl"] * ngl_price

    df["total_revenue"] = df["oil_rev"] + df["gas_rev"] + df["ngl_rev"]

    return df


# -----------------------------
# Costs
# -----------------------------
def calc_costs(df, loe_per_month=5000, tax_rate=0.07):
    df = df.copy()

    df["loe"] = loe_per_month
    df["tax"] = df["total_revenue"] * tax_rate

    df["total_cost"] = df["loe"] + df["tax"]

    return df


# -----------------------------
# Slot Cash Flow
# -----------------------------
def build_slot_cashflow(
    tc_name,
    lateral_length,
    spud_date,
    flowback_delay,
    tc_monthly,
    tc_metadata,
    oil_price,
    gas_price,
    ngl_yield,
):
    tc, base_length = get_type_curve(tc_name, tc_monthly, tc_metadata)

    start_date = spud_date + pd.DateOffset(months=flowback_delay)

    prod = build_production(tc, lateral_length, base_length, start_date)

    prod["ngl"] = calc_ngl(prod["gas"], ngl_yield)

    prod = calc_revenue(prod, oil_price, gas_price)
    prod = calc_costs(prod)

    prod["cash_flow"] = prod["total_revenue"] - prod["total_cost"]

    return prod


# -----------------------------
# Roll Up Slots
# -----------------------------
def roll_up_deal(slot_dfs):
    deal_df = pd.concat(slot_dfs)

    deal_df = (
        deal_df.groupby("date")
        .sum(numeric_only=True)
        .reset_index()
    )

    return deal_df


# -----------------------------
# IRR
# -----------------------------
def calc_irr(df):
    if pyxirr is None:
        return None

    try:
        return pyxirr.xirr(df["date"], df["cash_flow"])
    except:
        return None


# -----------------------------
# MOIC
# -----------------------------
def calc_moic(df):
    total_investment = abs(df["cash_flow"][df["cash_flow"] < 0].sum())
    total_return = df["cash_flow"][df["cash_flow"] > 0].sum()

    if total_investment == 0:
        return None

    return total_return / total_investment


# -----------------------------
# Run Deal Model
# -----------------------------
def run_deal_model(slot_df, deal_inputs):
    tc_monthly, tc_metadata = load_type_curve_library()

    slot_results = []

    for _, row in slot_df.iterrows():
        spud_date = pd.to_datetime("2027-01-01")

        slot_cf = build_slot_cashflow(
            tc_name="chestnut_farms",
            lateral_length=row["lateral_length"],
            spud_date=spud_date,
            flowback_delay=4,
            tc_monthly=tc_monthly,
            tc_metadata=tc_metadata,
            oil_price=deal_inputs["oil_price"],
            gas_price=deal_inputs["gas_price"],
            ngl_yield=5.2,
        )

        acquisition = row["net_acres"] * row["bid_per_acre"]

        capex = row["gross_wells"] * row["lateral_length"] * row["dc_cost_per_ft"]

        # add upfront costs
        first_date = slot_cf["date"].min()
        slot_cf.loc[slot_cf["date"] == first_date, "cash_flow"] -= (
            acquisition + capex
        )

        slot_results.append(slot_cf)

    deal_df = roll_up_deal(slot_results)

    irr = calc_irr(deal_df)
    moic = calc_moic(deal_df)

    return deal_df, irr, moic
