import os
from datetime import date
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from model import run_deal_model

st.set_page_config(page_title="Utica Deal Model", layout="wide")


# ----------------------------- 
# Helpers
# -----------------------------
def pretty_column_name(col):
    name_map = {
        "date": "Date",
        "slot_id": "Slot ID",
        "tc_name": "Type Curve",
        "slot_net_oil_production": "Net Oil Production",
        "slot_net_gas_production": "Net Gas Production",
        "slot_net_ngl_production": "Net NGL Production",
        "slot_oil_revenue": "Net Oil Revenue",
        "slot_gas_revenue": "Net Gas Revenue",
        "slot_ngl_revenue": "Net NGL Revenue",
        "slot_total_revenue": "Total Revenue",
        "slot_loe": "Total LOE",
        "slot_tax": "Total Tax",
        "slot_operating_profit": "Operating Profit",
        "slot_capex": "Capex",
        "slot_asset_purchase": "Acquisition",
        "slot_promote": "Promote",
        "slot_total_cash_flow": "Total Cash Flow",
        "cum_total_cf": "Cumulative Total Cash Flow",
    }
    return name_map.get(col, col.replace("_", " ").title())


def is_effectively_zero(x, tol=1e-9):
    return pd.notnull(x) and abs(float(x)) < tol


def format_accounting_number(
    x,
    decimals=1,
    prefix="",
    suffix="",
    zero_as_dash=True,
    null_as_blank=True,
):
    if pd.isnull(x):
        return "" if null_as_blank else "-"

    x = float(x)

    if zero_as_dash and is_effectively_zero(x):
        return "-"

    abs_text = f"{abs(x):,.{decimals}f}"
    text = f"{prefix}{abs_text}{suffix}"

    return f"({text})" if x < 0 else text


def format_accounting_percent(
    x,
    decimals=0,
    zero_as_dash=True,
    null_as_blank=True,
):
    if pd.isnull(x):
        return "" if null_as_blank else "-"

    x = float(x)

    if zero_as_dash and is_effectively_zero(x):
        return "-"

    abs_text = f"{abs(x):.{decimals}%}"
    return f"({abs_text})" if x < 0 else abs_text


def format_accounting_production(
    x,
    large_decimals=0,
    small_decimals=2,
    threshold=10,
    zero_as_dash=True,
    null_as_blank=True,
):
    if pd.isnull(x):
        return "" if null_as_blank else "-"

    x = float(x)

    if zero_as_dash and is_effectively_zero(x):
        return "-"

    decimals = large_decimals if abs(x) >= threshold else small_decimals
    abs_text = f"{abs(x):,.{decimals}f}"
    return f"({abs_text})" if x < 0 else abs_text


def format_display_df(df):
    display_df = df.copy()

    for col in display_df.columns:
        if pd.api.types.is_datetime64_any_dtype(display_df[col]):
            display_df[col] = display_df[col].dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_numeric_dtype(display_df[col]):
            display_df[col] = display_df[col].map(
                lambda x: format_accounting_number(x, decimals=1)
            )

    display_df.columns = [pretty_column_name(col) for col in display_df.columns]
    return display_df


def format_thousands_short(
    x,
    decimals=1,
    prefix="$",
    suffix="k",
    zero_as_dash=True,
    null_as_blank=True,
):
    if pd.isnull(x):
        return "" if null_as_blank else "-"

    x = float(x)

    if zero_as_dash and is_effectively_zero(x):
        return "-"

    x_thousands = x / 1000.0
    abs_text = f"{abs(x_thousands):,.{decimals}f}"
    text = f"{prefix}{abs_text}{suffix}"

    return f"({text})" if x < 0 else text


QUARTERLY_HEADER_COLOR = "#4E80B1"
BUTTON_DARK = "#2E4D6A"
MONTHLY_BTN = "#C0D4E4"
YEAR_FILL = "#CADEEE"


def inject_app_css():
    st.markdown(
        f"""
        <style>
        div[data-testid="stButton"] button[kind="primary"] {{
            background-color: {BUTTON_DARK} !important;
            color: white !important;
            border: 1px solid {BUTTON_DARK} !important;
            font-weight: 700 !important;
            border-radius: 10px !important;
        }}

        div[data-testid="stButton"] button[kind="primary"]:hover,
        div[data-testid="stButton"] button[kind="primary"]:focus,
        div[data-testid="stButton"] button[kind="primary"]:active {{
            background-color: {BUTTON_DARK} !important;
            color: white !important;
            border: 1px solid {BUTTON_DARK} !important;
            box-shadow: none !important;
            filter: brightness(1.05) !important;
        }}

        div[data-testid="stButton"] button[kind="secondary"] {{
            background-color: {MONTHLY_BTN} !important;
            color: #1f2d3d !important;
            border: 1px solid {MONTHLY_BTN} !important;
            font-weight: 700 !important;
            border-radius: 10px !important;
        }}

        div[data-testid="stButton"] button[kind="secondary"]:hover,
        div[data-testid="stButton"] button[kind="secondary"]:focus,
        div[data-testid="stButton"] button[kind="secondary"]:active {{
            background-color: {MONTHLY_BTN} !important;
            color: #1f2d3d !important;
            border: 1px solid {MONTHLY_BTN} !important;
            box-shadow: none !important;
            filter: brightness(1.05) !important;
        }}

        div[data-testid="stDownloadButton"] button {{
            background-color: {MONTHLY_BTN} !important;
            color: #1f2d3d !important;
            border: 1px solid {MONTHLY_BTN} !important;
            font-weight: 700 !important;
            border-radius: 10px !important;
        }}

        div[data-testid="stDownloadButton"] button:hover {{
            background-color: {MONTHLY_BTN} !important;
            filter: brightness(1.03) !important;
        }}

        div[data-testid="stExpander"] summary {{
            background-color: {QUARTERLY_HEADER_COLOR} !important;
            color: white !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            padding: 8px 12px !important;
        }}

        div[data-testid="stDataEditor"] [role="columnheader"],
        div[data-testid="stDataEditor"] thead th {{
            background-color: {QUARTERLY_HEADER_COLOR} !important;
            color: white !important;
            font-weight: 700 !important;
        }}

        div[data-testid="stDataEditor"] [role="columnheader"] *,
        div[data-testid="stDataEditor"] thead th * {{
            color: white !important;
            fill: white !important;
            font-weight: 700 !important;
        }}

        div[data-testid="stDataEditor"] [role="gridcell"] {{
            border-color: #e6e6e6 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_app_css()
st.title("Utica Deal Model")


@st.cache_data(show_spinner=False)
def load_tc_names(file_mtime):
    tc_metadata = pd.read_excel("type_curve_library.xlsx", sheet_name="tc_metadata")
    tc_metadata["tc_name"] = tc_metadata["tc_name"].astype(str).str.strip()
    return tc_metadata["tc_name"].dropna().unique().tolist()


def next_month_start():
    today = date.today()
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


def build_slot_template(num_slots):
    rows = []
    for i in range(1, num_slots + 1):
        rows.append(
            {
                "slot_id": i,
                "tc_name": "Choose TC",
                "gross_wells": 2.0,
                "net_acres": 28.6,
                "unit_acres": 800.0,
                "use_calc_unit_acres": False,
                "pct_unitized": 0.90,
                "drilling_spud_month": next_month_start(),
                "flowback_delay": 4,
                "net_revenue_interest": 0.80,
                "lateral_length": 10000,
                "dc_costs": 750.0,
                "tc_risk": 1.00,
                "bid_per_acre": 8000.0,
                "oil_diff": -10.00,
                "gas_diff": -3.00,
                "ngl_diff": 0.00,
                "oil_opex_bbl": 1.78,
                "gas_opex_mcf": 0.04,
                "ngl_opex": 2.50,
                "fixed_loe": 3534.0,
                "ngl_yield": 5.2,
            }
        )
    return pd.DataFrame(rows)


def resize_slot_df(existing_df, target_slots):
    existing_df = existing_df.copy().reset_index(drop=True)
    current_slots = len(existing_df)

    if current_slots == target_slots:
        existing_df["slot_id"] = range(1, target_slots + 1)
        return existing_df

    if current_slots < target_slots:
        new_rows = build_slot_template(target_slots).iloc[current_slots:].copy()
        existing_df = pd.concat([existing_df, new_rows], ignore_index=True)
        existing_df["slot_id"] = range(1, target_slots + 1)
        return existing_df

    trimmed_df = existing_df.iloc[:target_slots].copy().reset_index(drop=True)
    trimmed_df["slot_id"] = range(1, target_slots + 1)
    return trimmed_df


def to_excel_bytes(deal_df, slot_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        deal_df.to_excel(writer, index=False, sheet_name="Deal Audit")
        slot_df.to_excel(writer, index=False, sheet_name="Slot Audit")
    output.seek(0)
    return output.getvalue()


def apply_calc_unit_acres(df):
    df = df.copy()
    mask = df["use_calc_unit_acres"].fillna(False)

    df.loc[mask, "unit_acres"] = (
        df.loc[mask, "lateral_length"] / 50.0 * df.loc[mask, "gross_wells"]
    )

    return df


def build_sensitivity_range(base_value, step, steps_each_way=3):
    return [base_value + step * i for i in range(-steps_each_way, steps_each_way + 1)]


@st.cache_data(show_spinner=False)
def run_bid_dc_sensitivity(slot_df, deal_inputs, base_dc, base_bid):
    dc_values = build_sensitivity_range(base_dc, 50.0, 3)
    bid_values = build_sensitivity_range(base_bid, 500.0, 3)

    irr_table = pd.DataFrame(index=bid_values, columns=dc_values)
    moic_table = pd.DataFrame(index=bid_values, columns=dc_values)

    for dc in dc_values:
        for bid in bid_values:
            sens_deal_inputs = deal_inputs.copy()
            sens_deal_inputs["use_dc_override"] = True
            sens_deal_inputs["dc_override"] = float(dc)
            sens_deal_inputs["use_bid_override"] = True
            sens_deal_inputs["bid_override"] = float(bid)

            try:
                _, _, _, _, irr, moic = run_deal_model(slot_df.copy(), sens_deal_inputs)
                irr_table.loc[bid, dc] = irr
                moic_table.loc[bid, dc] = moic
            except Exception:
                irr_table.loc[bid, dc] = None
                moic_table.loc[bid, dc] = None

    return irr_table, moic_table


@st.cache_data(show_spinner=False)
def run_oil_bid_sensitivity(slot_df, deal_inputs, oil_values, bid_values):
    irr_table = pd.DataFrame(index=bid_values, columns=oil_values, dtype=float)
    moic_table = pd.DataFrame(index=bid_values, columns=oil_values, dtype=float)

    for oil in oil_values:
        for bid in bid_values:
            sens_deal_inputs = deal_inputs.copy()
            sens_deal_inputs["oil_price"] = float(oil)
            sens_deal_inputs["use_bid_override"] = True
            sens_deal_inputs["bid_override"] = float(bid)

            try:
                _, _, _, _, irr, moic = run_deal_model(slot_df.copy(), sens_deal_inputs)
                irr_table.loc[bid, oil] = irr
                moic_table.loc[bid, oil] = moic
            except Exception:
                irr_table.loc[bid, oil] = None
                moic_table.loc[bid, oil] = None

    return irr_table, moic_table


@st.cache_data(show_spinner=False)
def run_gas_bid_sensitivity(slot_df, deal_inputs, gas_values, bid_values):
    irr_table = pd.DataFrame(index=bid_values, columns=gas_values, dtype=float)
    moic_table = pd.DataFrame(index=bid_values, columns=gas_values, dtype=float)

    for gas in gas_values:
        for bid in bid_values:
            sens_deal_inputs = deal_inputs.copy()
            sens_deal_inputs["gas_price"] = float(gas)
            sens_deal_inputs["use_bid_override"] = True
            sens_deal_inputs["bid_override"] = float(bid)

            try:
                _, _, _, _, irr, moic = run_deal_model(slot_df.copy(), sens_deal_inputs)
                irr_table.loc[bid, gas] = irr
                moic_table.loc[bid, gas] = moic
            except Exception:
                irr_table.loc[bid, gas] = None
                moic_table.loc[bid, gas] = None

    return irr_table, moic_table


@st.cache_data(show_spinner=False)
def run_tcrisk_bid_sensitivity(slot_df, deal_inputs, tc_risk_values, bid_values):
    irr_table = pd.DataFrame(index=bid_values, columns=tc_risk_values, dtype=float)
    moic_table = pd.DataFrame(index=bid_values, columns=tc_risk_values, dtype=float)

    for tc_risk in tc_risk_values:
        for bid in bid_values:
            sens_deal_inputs = deal_inputs.copy()
            sens_deal_inputs["use_bid_override"] = True
            sens_deal_inputs["bid_override"] = float(bid)

            sens_slot_df = slot_df.copy()
            sens_slot_df["tc_risk"] = float(tc_risk)

            try:
                _, _, _, _, irr, moic = run_deal_model(sens_slot_df, sens_deal_inputs)
                irr_table.loc[bid, tc_risk] = irr
                moic_table.loc[bid, tc_risk] = moic
            except Exception:
                irr_table.loc[bid, tc_risk] = None
                moic_table.loc[bid, tc_risk] = None

    return irr_table, moic_table


def build_heatmap(
    df,
    title,
    metric="irr",
    x_title="",
    y_title="",
    x_format="dollar",
    y_format="dollar",
    base_x=None,
    base_y=None,
):
    heatmap_df = df.copy()

    def format_axis_value(v, fmt):
        if fmt == "dollar":
            return f"${int(v):,}" if float(v).is_integer() else f"${v:,.2f}"
        if fmt == "percent":
            return f"{v:.0%}"
        if fmt == "float2":
            return f"{v:.2f}"
        return str(v)

    x_vals = [format_axis_value(x, x_format) for x in heatmap_df.columns]
    y_vals = [format_axis_value(y, y_format) for y in heatmap_df.index]

    def clamp01(x):
        return max(0.0, min(1.0, x))

    if metric == "irr":
        text_vals = heatmap_df.map(lambda x: f"{x:.2%}" if pd.notnull(x) else "")
        zmin = 0.0
        zmax = max(0.40, float(heatmap_df.max().max()))

        low_cut = 0.15
        high_cut = 0.25

        low_norm = clamp01((low_cut - zmin) / (zmax - zmin)) if zmax > zmin else 0.33
        high_norm = clamp01((high_cut - zmin) / (zmax - zmin)) if zmax > zmin else 0.66

        colorscale = [
            [0.00, "rgb(255,180,180)"],
            [low_norm, "rgb(255,180,180)"],
            [low_norm, "rgb(255,255,204)"],
            [high_norm, "rgb(255,255,204)"],
            [high_norm, "rgb(214,232,202)"],
            [1.00, "rgb(214,232,202)"],
        ]
    elif metric == "moic":
        text_vals = heatmap_df.map(lambda x: f"{x:.2f}x" if pd.notnull(x) else "")
        zmin = min(0.0, float(heatmap_df.min().min()))
        zmax = max(2.0, float(heatmap_df.max().max()))

        low_cut = 1.00
        high_cut = 1.50

        low_norm = clamp01((low_cut - zmin) / (zmax - zmin)) if zmax > zmin else 0.33
        high_norm = clamp01((high_cut - zmin) / (zmax - zmin)) if zmax > zmin else 0.66

        colorscale = [
            [0.00, "rgb(255,180,180)"],
            [low_norm, "rgb(255,180,180)"],
            [low_norm, "rgb(255,255,204)"],
            [high_norm, "rgb(255,255,204)"],
            [high_norm, "rgb(214,232,202)"],
            [1.00, "rgb(214,232,202)"],
        ]
    else:
        text_vals = heatmap_df.map(lambda x: f"{x}" if pd.notnull(x) else "")
        zmin = 0.0
        zmax = 1.0
        colorscale = "RdYlGn"

    fig = go.Figure(
        data=go.Heatmap(
            z=heatmap_df.values,
            x=x_vals,
            y=y_vals,
            text=text_vals.values,
            texttemplate="%{text}",
            colorscale=colorscale,
            zmin=zmin,
            zmax=zmax,
            showscale=False,
            hovertemplate=f"{x_title}: %{{x}}<br>{y_title}: %{{y}}<br>Value: %{{text}}<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        xaxis=dict(title=x_title, side="top", type="category", automargin=True),
        yaxis=dict(title=y_title, type="category", automargin=True),
        margin=dict(l=90, r=20, t=60, b=50),
        height=360,
    )

    if base_x is not None and base_y is not None:
        try:
            x_vals_raw = list(heatmap_df.columns)
            y_vals_raw = list(heatmap_df.index)

            def find_closest_index(values, target):
                return min(
                    range(len(values)),
                    key=lambda i: abs(float(values[i]) - float(target)),
                )

            x_idx = find_closest_index(x_vals_raw, base_x)
            y_idx = find_closest_index(y_vals_raw, base_y)

            fig.add_shape(
                type="rect",
                x0=x_idx - 0.5,
                x1=x_idx + 0.5,
                y0=y_idx - 0.5,
                y1=y_idx + 0.5,
                line=dict(color="black", width=3),
                fillcolor="rgba(0,0,0,0)",
            )
        except Exception:
            pass

    return fig


def build_quarterly_output_table(deal_df, all_slots_df, slot_df, deal_inputs):
    import numpy as np

    deal = deal_df.copy()
    slots = all_slots_df.copy()
    slot_inputs = slot_df.copy()

    deal["date"] = pd.to_datetime(deal["date"])
    slots["date"] = pd.to_datetime(slots["date"])
    slot_inputs["drilling_spud_month"] = pd.to_datetime(slot_inputs["drilling_spud_month"])

    deal["quarter_label"] = "Q" + deal["date"].dt.quarter.astype(str) + " " + deal["date"].dt.strftime("%y")
    deal["year_label"] = deal["date"].dt.year.astype(str)

    quarter_order = [
        "Q1 26", "Q2 26", "Q3 26", "Q4 26",
        "Q1 27", "Q2 27", "Q3 27", "Q4 27",
    ]
    year_order = [str(y) for y in range(2026, 2034)]

    def quarter_days_from_label(q_label):
        q_num = int(q_label[1])
        year = 2000 + int(q_label[-2:])
        quarter_start_month = {1: 1, 2: 4, 3: 7, 4: 10}[q_num]
        start = pd.Timestamp(year=year, month=quarter_start_month, day=1)
        end = start + pd.offsets.QuarterEnd(0)
        return (end - start).days + 1

    def year_days_from_label(y_label):
        year = int(y_label)
        start = pd.Timestamp(year=year, month=1, day=1)
        end = pd.Timestamp(year=year, month=12, day=31)
        return (end - start).days + 1

    q_days = pd.Series({q: quarter_days_from_label(q) for q in quarter_order}, index=quarter_order, dtype=float)
    y_days = pd.Series({y: year_days_from_label(y) for y in year_order}, index=year_order, dtype=float)

    q = deal.groupby("quarter_label").sum(numeric_only=True).reindex(quarter_order)
    y = deal.groupby("year_label").sum(numeric_only=True).reindex(year_order)

    slot_metrics = slot_inputs.copy()
    slot_metrics["spud_quarter"] = "Q" + slot_metrics["drilling_spud_month"].dt.quarter.astype(str) + " " + slot_metrics["drilling_spud_month"].dt.strftime("%y")
    slot_metrics["spud_year"] = slot_metrics["drilling_spud_month"].dt.year.astype(str)

    unit_acres_final = np.where(
        slot_metrics["use_calc_unit_acres"].fillna(False),
        slot_metrics["gross_wells"] * slot_metrics["lateral_length"] / 50.0,
        slot_metrics["unit_acres"],
    )

    working_interest = np.where(
        unit_acres_final != 0,
        (slot_metrics["net_acres"] / unit_acres_final) * slot_metrics["pct_unitized"],
        0.0,
    )

    net_wells_calc = working_interest * slot_metrics["gross_wells"]

    slot_metrics["gross_wells_spud"] = slot_metrics["gross_wells"]
    slot_metrics["net_wells_spud"] = net_wells_calc

    q_spud = slot_metrics.groupby("spud_quarter")[["gross_wells_spud", "net_wells_spud"]].sum().reindex(quarter_order).fillna(0.0)
    y_spud = slot_metrics.groupby("spud_year")[["gross_wells_spud", "net_wells_spud"]].sum().reindex(year_order).fillna(0.0)

    def safe_div(n, d):
        return np.where((d != 0) & pd.notnull(d), n / d, 0.0)

    def build_section(df, days):
        out = pd.DataFrame(index=[], columns=df.index)

        oil_price_flat = float(deal_inputs["oil_price"])
        gas_price_flat = float(deal_inputs["gas_price"])

        realized_oil = safe_div(df["slot_oil_revenue"], df["slot_net_oil_production"])
        realized_gas = safe_div(df["slot_gas_revenue"], df["slot_net_gas_production"])
        realized_ngl_price = safe_div(df["slot_ngl_revenue"], df["slot_net_ngl_production"])
        realized_ngl_pct_wti = safe_div(realized_ngl_price, oil_price_flat)

        oil_mbbl_d = safe_div(df["slot_net_oil_production"], days)
        ngl_mbbl_d = safe_div(df["slot_net_ngl_production"], days)
        gas_mmcf_d = safe_div(df["slot_net_gas_production"], days)

        total_mcfe = (
            df["slot_net_oil_production"] * 6.0
            + df["slot_net_ngl_production"] * 6.0
            + df["slot_net_gas_production"]
        )
        total_mcfe_d = safe_div(total_mcfe, days)

        taxes_pos = -df["slot_tax"]
        loe_pos = -df["slot_loe"]
        promote_pos = -df["slot_promote"]

        total_opex = taxes_pos + loe_pos + promote_pos
        ebitda = df["slot_total_revenue"] - total_opex

        d_and_c = -df["slot_capex"]
        acquisition = -df["slot_asset_purchase"]
        total_capex = d_and_c + acquisition

        free_cash_flow = df["slot_total_cash_flow"]

        out.loc["Assumed Index Pricing - Crude Oil"] = oil_price_flat
        out.loc["Assumed Index Pricing - Natural Gas"] = gas_price_flat
        out.loc["Realized Pricing - Crude Oil"] = realized_oil
        out.loc["Realized Pricing - NGL (% of WTI)"] = realized_ngl_pct_wti
        out.loc["Realized Pricing - Natural Gas"] = realized_gas
        out.loc["Production - Crude Oil"] = oil_mbbl_d
        out.loc["Production - NGL's"] = ngl_mbbl_d
        out.loc["Production - Natural Gas"] = gas_mmcf_d
        out.loc["Production - Total (Mcfe/d)"] = total_mcfe_d
        out.loc["Revenues - Crude Oil"] = df["slot_oil_revenue"] / 1000.0
        out.loc["Revenues - NGL's"] = df["slot_ngl_revenue"] / 1000.0
        out.loc["Revenues - Natural Gas"] = df["slot_gas_revenue"] / 1000.0
        out.loc["Revenues - Total"] = df["slot_total_revenue"] / 1000.0
        out.loc["Operating Expenses - Taxes"] = taxes_pos / 1000.0
        out.loc["Operating Expenses - LOE"] = loe_pos / 1000.0
        out.loc["Operating Expenses - Dale Promote"] = promote_pos / 1000.0
        out.loc["Operating Expenses - Total Opex"] = total_opex / 1000.0
        out.loc["Taxes / Mcfe"] = safe_div(taxes_pos, total_mcfe)
        out.loc["LOE / Mcfe"] = safe_div(loe_pos, total_mcfe)
        out.loc["Promote / Mcfe"] = safe_div(promote_pos, total_mcfe)
        out.loc["EBITDA"] = ebitda / 1000.0
        out.loc["Capital Expenditures - D&C"] = d_and_c / 1000.0
        out.loc["Capital Expenditures - Acquisition"] = acquisition / 1000.0
        out.loc["Capital Expenditures - Total"] = total_capex / 1000.0
        out.loc["Free Cash Flow"] = free_cash_flow / 1000.0
        out.loc["Cumulative FCF"] = (free_cash_flow / 1000.0).cumsum()

        return out

    q_out = build_section(q, q_days)
    y_out = build_section(y, y_days)

    q_out.loc["Gross Wells Spud"] = q_spud["gross_wells_spud"]
    q_out.loc["Net Wells Spud"] = q_spud["net_wells_spud"]
    y_out.loc["Gross Wells Spud"] = y_spud["gross_wells_spud"]
    y_out.loc["Net Wells Spud"] = y_spud["net_wells_spud"]

    row_order = [
        "Assumed Index Pricing - Crude Oil",
        "Assumed Index Pricing - Natural Gas",
        "Realized Pricing - Crude Oil",
        "Realized Pricing - NGL (% of WTI)",
        "Realized Pricing - Natural Gas",
        "Gross Wells Spud",
        "Net Wells Spud",
        "Production - Crude Oil",
        "Production - NGL's",
        "Production - Natural Gas",
        "Production - Total (Mcfe/d)",
        "Revenues - Crude Oil",
        "Revenues - NGL's",
        "Revenues - Natural Gas",
        "Revenues - Total",
        "Operating Expenses - Taxes",
        "Operating Expenses - LOE",
        "Operating Expenses - Dale Promote",
        "Operating Expenses - Total Opex",
        "Taxes / Mcfe",
        "LOE / Mcfe",
        "Promote / Mcfe",
        "EBITDA",
        "Capital Expenditures - D&C",
        "Capital Expenditures - Acquisition",
        "Capital Expenditures - Total",
        "Free Cash Flow",
        "Cumulative FCF",
    ]

    q_out = q_out.reindex(row_order)
    y_out = y_out.reindex(row_order)

    separator = pd.DataFrame(index=q_out.index, columns=[" "], data="")
    final = pd.concat([q_out, separator, y_out], axis=1)
    return final


def build_quarterly_output_display_table(df):
    first_col = "$ in Thousands"
    data_cols = list(df.columns)

    pct_rows = {"Realized Pricing - NGL (% of WTI)"}
    dollar_per_unit_rows = {"Taxes / Mcfe", "LOE / Mcfe", "Promote / Mcfe"}
    price_rows = {
        "Assumed Index Pricing - Crude Oil",
        "Assumed Index Pricing - Natural Gas",
        "Realized Pricing - Crude Oil",
        "Realized Pricing - Natural Gas",
    }
    production_rows = {
        "Production - Crude Oil",
        "Production - NGL's",
        "Production - Natural Gas",
        "Production - Total (Mcfe/d)",
        "Gross Wells Spud",
        "Net Wells Spud",
    }

    def fmt_value(source_row, col):
        val = df.loc[source_row, col]

        if col == " ":
            return ""
        if pd.isnull(val) or val == "":
            return ""

        if source_row in pct_rows:
            return format_accounting_percent(val, decimals=0)
        if source_row in dollar_per_unit_rows:
            return format_accounting_number(val, decimals=2, prefix="$")
        if source_row in price_rows:
            return format_accounting_number(val, decimals=2, prefix="$")
        if source_row in production_rows:
            return format_accounting_production(val)
        return format_accounting_number(val, decimals=1, prefix="$")

    rows = []
    row_styles = []

    def add_section(label):
        row = {first_col: label}
        for c in data_cols:
            row[c] = ""
        rows.append(row)
        row_styles.append("section")

    def add_gap():
        row = {first_col: ""}
        for c in data_cols:
            row[c] = ""
        rows.append(row)
        row_styles.append("gap")

    def add_data(label, source_row, indent=False, style="normal"):
        display_label = f"    {label}" if indent else label
        row = {first_col: display_label}
        for c in data_cols:
            row[c] = fmt_value(source_row, c)
        rows.append(row)
        row_styles.append(style)

    add_section("Assumed Index Pricing")
    add_data("Crude Oil", "Assumed Index Pricing - Crude Oil", indent=True)
    add_data("Natural Gas", "Assumed Index Pricing - Natural Gas", indent=True)

    add_gap()

    add_section("Realized Pricing")
    add_data("Crude Oil", "Realized Pricing - Crude Oil", indent=True)
    add_data("Natural Gas", "Realized Pricing - Natural Gas", indent=True)
    add_data("NGL (% of WTI)", "Realized Pricing - NGL (% of WTI)", indent=True)

    add_gap()

    add_data("Gross Wells Spud", "Gross Wells Spud")
    add_data("Net Wells Spud", "Net Wells Spud")

    add_gap()

    add_section("Production")
    add_data("Crude Oil", "Production - Crude Oil", indent=True)
    add_data("Natural Gas", "Production - Natural Gas", indent=True)
    add_data("NGL's", "Production - NGL's", indent=True)
    add_data("Total (Mcfe/d)", "Production - Total (Mcfe/d)", style="bold")

    add_gap()

    add_section("Revenues")
    add_data("Crude Oil", "Revenues - Crude Oil", indent=True)
    add_data("Natural Gas", "Revenues - Natural Gas", indent=True)
    add_data("NGL's", "Revenues - NGL's", indent=True)
    add_data("Total", "Revenues - Total")

    add_gap()

    add_section("Operating Expenses")
    add_data("Taxes", "Operating Expenses - Taxes", indent=True)
    add_data("LOE", "Operating Expenses - LOE", indent=True)
    add_data("Dale Promote", "Operating Expenses - Dale Promote", indent=True)
    add_data("Total", "Operating Expenses - Total Opex")

    add_gap()

    add_data("Taxes / Mcfe", "Taxes / Mcfe", style="italic")
    add_data("LOE / Mcfe", "LOE / Mcfe", style="italic")
    add_data("Promote / Mcfe", "Promote / Mcfe", style="italic")

    add_gap()

    add_data("EBITDA", "EBITDA", style="bold")

    add_gap()

    add_section("Capital Expenditures")
    add_data("D&C", "Capital Expenditures - D&C", indent=True)
    add_data("Acquisition", "Capital Expenditures - Acquisition", indent=True)
    add_data("Total", "Capital Expenditures - Total")

    add_gap()

    add_data("Free Cash Flow", "Free Cash Flow", style="bold")

    add_gap()

    add_data("Cumulative FCF", "Cumulative FCF", style="footer")

    display_df = pd.DataFrame(rows)
    return display_df, row_styles


def style_quarterly_output_table(display_df, row_styles):
    style_map = pd.Series(row_styles, index=display_df.index)

    first_col = display_df.columns[0]
    data_cols = list(display_df.columns[1:])

    quarter_cols = [c for c in data_cols if str(c).startswith("Q")]
    year_cols = [c for c in data_cols if str(c).isdigit()]
    separator_cols = [c for c in data_cols if str(c).strip() == ""]

    def row_style(row):
        rtype = style_map.loc[row.name]
        styles = [""] * len(row)

        if rtype == "section":
            styles = ["font-weight: 700; text-align: left;"] + [""] * (len(row) - 1)
        elif rtype == "bold":
            styles = ["font-weight: 700;"] * len(row)
        elif rtype == "italic":
            styles = ["font-style: italic;"] * len(row)
        elif rtype == "footer":
            styles = [f"background-color: {QUARTERLY_HEADER_COLOR}; color: white; font-weight: 700;"] * len(row)
        elif rtype == "gap":
            styles = [""] * len(row)

        return styles

    return (
        display_df.style
        .apply(row_style, axis=1)
        .hide(axis="index")
        .set_properties(subset=[first_col], **{
            "text-align": "left",
            "white-space": "pre",
            "background-color": "white",
        })
        .set_properties(subset=quarter_cols, **{
            "text-align": "right",
            "background-color": "white",
        })
        .set_properties(subset=year_cols, **{
            "text-align": "right",
            "background-color": YEAR_FILL,
        })
        .set_properties(subset=separator_cols, **{
            "background-color": "white",
            "width": "14px",
        })
        .set_table_styles([
            {
                "selector": "table",
                "props": [
                    ("border-collapse", "separate"),
                    ("border-spacing", "0"),
                    ("width", "100%"),
                ],
            },
            {
                "selector": "thead th",
                "props": [
                    ("background-color", QUARTERLY_HEADER_COLOR),
                    ("color", "white"),
                    ("font-weight", "700"),
                    ("text-align", "center"),
                    ("border", "none"),
                    ("padding", "6px 10px"),
                ],
            },
            {
                "selector": "tbody td",
                "props": [
                    ("border", "none"),
                    ("padding", "6px 10px"),
                ],
            },
            {
                "selector": "tbody td.col0",
                "props": [
                    ("text-align", "left"),
                    ("white-space", "pre"),
                ],
            },
            {
                "selector": "tbody td:not(.col0)",
                "props": [("text-align", "right")],
            },
            {
                "selector": f"tbody tr:nth-child({len(display_df)}) td",
                "props": [
                    ("background-color", QUARTERLY_HEADER_COLOR),
                    ("color", "white"),
                    ("font-weight", "700"),
                ],
            },
        ], overwrite=False)
    )


def build_tc_assumptions_output_display_table(slot_df):
    df = slot_df.copy()

    if df.empty:
        return pd.DataFrame({"TC Assumptions": []}), []

    df["drilling_spud_month"] = pd.to_datetime(df["drilling_spud_month"], errors="coerce")
    display_cols = [f"Slot {int(s)}" for s in df["slot_id"]]

    rows = []
    row_styles = []

    def add_section(label):
        row = {"TC Assumptions": label}
        for c in display_cols:
            row[c] = ""
        rows.append(row)
        row_styles.append("section")

    def add_gap():
        row = {"TC Assumptions": ""}
        for c in display_cols:
            row[c] = ""
        rows.append(row)
        row_styles.append("gap")

    def add_data(label, values, style="normal"):
        row = {"TC Assumptions": label}
        row.update(values)
        rows.append(row)
        row_styles.append(style)

    slot_map = {}
    for _, r in df.iterrows():
        slot_name = f"Slot {int(r['slot_id'])}"
        slot_map[slot_name] = r

    def fmt_num(x, decimals=1, prefix="", suffix=""):
        return format_accounting_number(x, decimals=decimals, prefix=prefix, suffix=suffix, null_as_blank=False)

    def fmt_pct(x, decimals=0):
        return format_accounting_percent(x, decimals=decimals, null_as_blank=False)

    def fmt_date(x):
        if pd.isnull(x):
            return "-"
        return pd.to_datetime(x).strftime("%Y-%m-%d")

    add_section("Development")
    add_data("Type Curve", {k: str(v["tc_name"]) for k, v in slot_map.items()})
    add_data("Gross Wells", {k: fmt_num(v["gross_wells"], decimals=2) for k, v in slot_map.items()})
    add_data("Net Acres", {k: fmt_num(v["net_acres"], decimals=1) for k, v in slot_map.items()})
    add_data("Unit Acres", {k: fmt_num(v["unit_acres"], decimals=0) for k, v in slot_map.items()})
    add_data("Calc Unit Acres", {k: "Yes" if bool(v["use_calc_unit_acres"]) else "No" for k, v in slot_map.items()})
    add_data("% Unitized", {k: fmt_pct(v["pct_unitized"], decimals=0) for k, v in slot_map.items()})
    add_data("Spud Month", {k: fmt_date(v["drilling_spud_month"]) for k, v in slot_map.items()})
    add_data("Flowback Delay", {k: fmt_num(v["flowback_delay"], decimals=0) for k, v in slot_map.items()})
    add_data("NRI", {k: fmt_pct(v["net_revenue_interest"], decimals=0) for k, v in slot_map.items()})
    add_data("Lateral Length (ft)", {k: fmt_num(v["lateral_length"], decimals=0) for k, v in slot_map.items()})

    add_gap()

    add_section("Economics")
    add_data("D&C ($/ft)", {k: fmt_num(v["dc_costs"], decimals=0, prefix="$") for k, v in slot_map.items()})
    add_data("TC Risk", {k: fmt_pct(v["tc_risk"], decimals=0) for k, v in slot_map.items()})
    add_data("$/Acre Bid", {k: fmt_num(v["bid_per_acre"], decimals=0, prefix="$") for k, v in slot_map.items()})
    add_data("Oil Diff", {k: fmt_num(v["oil_diff"], decimals=2, prefix="$") for k, v in slot_map.items()})
    add_data("Gas Diff", {k: fmt_num(v["gas_diff"], decimals=2, prefix="$") for k, v in slot_map.items()})

    add_gap()

    add_section("Operating Costs")
    add_data("Oil Opex", {k: fmt_num(v["oil_opex_bbl"], decimals=2, prefix="$") for k, v in slot_map.items()})
    add_data("Gas Opex", {k: fmt_num(v["gas_opex_mcf"], decimals=2, prefix="$") for k, v in slot_map.items()})
    add_data("NGL Opex", {k: fmt_num(v["ngl_opex"], decimals=2, prefix="$") for k, v in slot_map.items()})
    add_data("Fixed LOE", {k: fmt_num(v["fixed_loe"], decimals=0, prefix="$") for k, v in slot_map.items()})
    add_data("NGL Yield", {k: fmt_num(v["ngl_yield"], decimals=2) for k, v in slot_map.items()}, style="footer")

    display_df = pd.DataFrame(rows)
    return display_df, row_styles


def style_tc_assumptions_output_table(display_df, row_styles):
    style_map = pd.Series(row_styles, index=display_df.index)

    first_col = display_df.columns[0]
    other_cols = list(display_df.columns[1:])

    def row_style(row):
        rtype = style_map.loc[row.name]
        styles = [""] * len(row)

        if rtype == "section":
            styles = ["font-weight: 700; text-align: left;"] + [""] * (len(row) - 1)
        elif rtype == "footer":
            styles = [f"background-color: {QUARTERLY_HEADER_COLOR}; color: white; font-weight: 700;"] * len(row)
        elif rtype == "gap":
            styles = [""] * len(row)

        return styles

    return (
        display_df.style
        .apply(row_style, axis=1)
        .hide(axis="index")
        .set_properties(subset=[first_col], **{
            "text-align": "left",
            "white-space": "pre",
            "background-color": "white",
        })
        .set_properties(subset=other_cols, **{
            "text-align": "right",
            "background-color": "white",
        })
        .set_table_styles([
            {
                "selector": "table",
                "props": [
                    ("border-collapse", "separate"),
                    ("border-spacing", "0"),
                    ("width", "100%"),
                ],
            },
            {
                "selector": "thead th",
                "props": [
                    ("background-color", QUARTERLY_HEADER_COLOR),
                    ("color", "white"),
                    ("font-weight", "700"),
                    ("text-align", "center"),
                    ("border", "none"),
                    ("padding", "6px 10px"),
                ],
            },
            {
                "selector": "tbody td",
                "props": [
                    ("border", "none"),
                    ("padding", "6px 10px"),
                ],
            },
            {
                "selector": "tbody td.col0",
                "props": [
                    ("text-align", "left"),
                    ("white-space", "pre"),
                ],
            },
        ], overwrite=False)
    )


def render_deal_highlight_box(title, value):
    st.markdown(
        f"""
        <div style="
            background-color: {QUARTERLY_HEADER_COLOR};
            color: white;
            padding: 14px 10px;
            border-radius: 6px;
            text-align: center;
            font-weight: 700;
        ">
            <div style="font-size: 13px; margin-bottom: 6px;">{title}</div>
            <div style="font-size: 24px;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_production_profile_chart(deal_df, chart_view="Stacked BOE/d"):
    df = deal_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] <= pd.Timestamp("2040-12-31")].copy()

    # Convert monthly net volumes to BOE/d
    df["days_in_month"] = df["date"].dt.days_in_month
    df["net_oil_boe_d"] = df["slot_net_oil_production"] / df["days_in_month"]
    df["net_ngl_boe_d"] = df["slot_net_ngl_production"] / df["days_in_month"]
    df["net_gas_boe_d"] = (df["slot_net_gas_production"] / 6.0) / df["days_in_month"]

    # Optional total line if you ever want it later
    df["total_boe_d"] = (
        df["net_oil_boe_d"] + df["net_ngl_boe_d"] + df["net_gas_boe_d"]
    )

    fig = go.Figure()

    oil_color = "#1f4e79"
    ngl_color = "#4e80b1"
    gas_color = "#b7cde3"

    if chart_view == "Stacked BOE/d":
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["net_oil_boe_d"],
                mode="lines",
                name="Oil",
                stackgroup="one",
                line=dict(color=oil_color, width=1.5),
                hovertemplate="Date: %{x|%Y-%m-%d}<br>Net Oil: %{y:,.1f} BOE/d<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["net_ngl_boe_d"],
                mode="lines",
                name="NGL",
                stackgroup="one",
                line=dict(color=ngl_color, width=1.5),
                hovertemplate="Date: %{x|%Y-%m-%d}<br>Net NGL: %{y:,.1f} BOE/d<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["net_gas_boe_d"],
                mode="lines",
                name="Gas",
                stackgroup="one",
                line=dict(color=gas_color, width=1.5),
                hovertemplate="Date: %{x|%Y-%m-%d}<br>Net Gas: %{y:,.1f} BOE/d<extra></extra>",
            )
        )

        chart_title = "Net Production Profile (BOE/d)"
    else:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["net_oil_boe_d"],
                mode="lines",
                name="Oil",
                line=dict(color=oil_color, width=3),
                hovertemplate="Date: %{x|%Y-%m-%d}<br>Net Oil: %{y:,.1f} BOE/d<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["net_ngl_boe_d"],
                mode="lines",
                name="NGL",
                line=dict(color=ngl_color, width=3),
                hovertemplate="Date: %{x|%Y-%m-%d}<br>Net NGL: %{y:,.1f} BOE/d<extra></extra>",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["net_gas_boe_d"],
                mode="lines",
                name="Gas",
                line=dict(color=gas_color, width=3),
                hovertemplate="Date: %{x|%Y-%m-%d}<br>Net Gas: %{y:,.1f} BOE/d<extra></extra>",
            )
        )

        chart_title = "Net Production Stream Split (BOE/d)"

    fig.update_layout(
        title=dict(
            text=chart_title,
            font=dict(color="black"),
        ),
        xaxis=dict(
            title=dict(text="Date", font=dict(color="black")),
            tickformat="%Y",
            dtick="M12",
            tickfont=dict(color="black"),
        ),
        yaxis=dict(
            title=dict(text="Net Production (BOE/d)", font=dict(color="black")),
            tickfont=dict(color="black"),
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.16,
            xanchor="center",
            x=0.5,
            font=dict(color="black"),
            traceorder="normal",
            entrywidth=140,
            entrywidthmode="pixels",
        )
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")

    return fig

def build_cumulative_fcf_chart(deal_df, slot_df):
    df = deal_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] <= pd.Timestamp("2040-12-31")].copy()

    monthly_fcf = df.groupby("date", as_index=False)["slot_total_cash_flow"].sum()
    monthly_fcf["cum_fcf"] = monthly_fcf["slot_total_cash_flow"].cumsum() / 1000.0

    payback_years = None
    payback_date = None

    for i in range(1, len(monthly_fcf)):
        prev_val = monthly_fcf.loc[i - 1, "cum_fcf"]
        curr_val = monthly_fcf.loc[i, "cum_fcf"]

        if prev_val < 0 <= curr_val:
            prev_date = monthly_fcf.loc[i - 1, "date"]
            curr_date = monthly_fcf.loc[i, "date"]

            frac = 0 if curr_val == prev_val else (0 - prev_val) / (curr_val - prev_val)
            payback_date = prev_date + (curr_date - prev_date) * frac
            start_date = monthly_fcf.loc[0, "date"]
            payback_years = (payback_date - start_date).days / 365.25
            break

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=monthly_fcf["date"],
            y=monthly_fcf["cum_fcf"],
            mode="lines",
            name="Cumulative FCF",
            fill="tozeroy",
            hovertemplate="Date: %{x|%Y-%m-%d}<br>Cumulative FCF: %{y:,.1f}<extra></extra>",
        )
    )

    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")

    slot_chart = slot_df.copy()
    slot_chart["drilling_spud_month"] = pd.to_datetime(
        slot_chart["drilling_spud_month"], errors="coerce"
    )
    slot_chart = slot_chart[
        slot_chart["drilling_spud_month"] <= pd.Timestamp("2040-12-31")
    ].copy()

    if not slot_chart.empty:
        spud_summary = (
            slot_chart.groupby("drilling_spud_month", as_index=False)["gross_wells"]
            .sum()
            .sort_values("drilling_spud_month")
        )
    
        for _, row in spud_summary.iterrows():
            spud_date = row["drilling_spud_month"]
            gross_wells = row["gross_wells"]
    
            x0 = spud_date
            x1 = spud_date + pd.offsets.MonthEnd(1)
    
            # 🔹 Soft shaded band (no outline)
            fig.add_vrect(
                x0=x0,
                x1=x1,
                fillcolor="rgba(78, 128, 177, 0.18)",  # softer fill
                line_width=0,  # removes harsh border
                layer="below",
            )
    
            # 🔹 Move Gross Wells LOWER so it never conflicts with payback
            fig.add_annotation(
                x=spud_date + pd.Timedelta(days=14),
                y=0.88,
                yref="paper",
                text=f"{gross_wells:.1f} Gross Wells",
                showarrow=False,
                textangle=-90,
                font=dict(size=10, color="black"),
                bgcolor="rgba(255,255,255,0)",
                bordercolor="rgba(0,0,0,0)",
                borderwidth=0,
                xanchor="center",
                yanchor="middle",
            )
            
    if payback_date is not None and payback_years is not None:
        fig.add_vline(
            x=payback_date,
            line_width=1,
            line_dash="dot",
            line_color="gray",
        )

        fig.add_annotation(
            x=payback_date,
            y=1.08,
            yref="paper",
            text=f"<b>Payback = {payback_years:.1f} years</b>",
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=28,
            font=dict(size=16, color="black"),  # slightly bigger
            bgcolor="rgba(255,255,255,0)",     # no box
            bordercolor="rgba(0,0,0,0)",
            borderwidth=0,
        )

    fig.update_layout(
        title=dict(
            text="<b>Cumulative Free Cash Flow</b>",
            x=0.5,
            xanchor="center",
            font=dict(size=20, color="black"),
        ),
        xaxis=dict(
            title=dict(text="Date", font=dict(size=14, color="black")),
            tickformat="%Y",
            dtick="M12",
            tickfont=dict(size=12, color="black"),
        ),
        yaxis=dict(
            title=dict(text="$ in Thousands", font=dict(size=14, color="black")),
            tickfont=dict(size=12, color="black"),
        ),
        height=525,
        margin=dict(l=50, r=40, t=95, b=45),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")

    return fig

@st.cache_data(show_spinner=False)
def build_scenario_scatter_chart(slot_df, deal_inputs, base_bid, base_dc):
    bid_values = build_sensitivity_range(base_bid, 500.0, 3)

    dc_cases = [
        ("Low", base_dc - 50.0),
        ("Base", base_dc),
        ("High", base_dc + 50.0),
    ]
    
    tc_risk_values = [0.80, 1.00, 1.20]

    base_oil = float(deal_inputs["oil_price"])
    base_gas = float(deal_inputs["gas_price"])

    pricing_cases = [
        ("Downside", max(0.0, base_oil - 5.0), max(0.0, base_gas - 0.25)),
        ("Base", base_oil, base_gas),
        ("Upside", base_oil + 5.0, base_gas + 0.25),
    ]

    rows = []

    for pricing_name, oil_price, gas_price in pricing_cases:
        for dc_label, dc_value in dc_cases:
            for tc_risk in tc_risk_values:
                for bid in bid_values:
                    sens_inputs = deal_inputs.copy()
                    sens_inputs["oil_price"] = float(oil_price)
                    sens_inputs["gas_price"] = float(gas_price)
                    sens_inputs["use_bid_override"] = True
                    sens_inputs["bid_override"] = float(bid)
                    sens_inputs["use_dc_override"] = True
                    sens_inputs["dc_override"] = float(dc_value)

                    sens_slot_df = slot_df.copy()
                    sens_slot_df["tc_risk"] = float(tc_risk)

                    try:
                        _, _, _, _, irr, moic = run_deal_model(sens_slot_df, sens_inputs)
                    except Exception:
                        irr, moic = None, None

                    rows.append(
                        {
                            "pricing_case": pricing_name,
                            "oil_price": oil_price,
                            "gas_price": gas_price,
                            "dc_case": dc_label,
                            "dc_value": dc_value,
                            "tc_risk": tc_risk,
                            "bid": bid,
                            "irr": irr,
                            "moic": moic,
                        }
                    )

    chart_df = pd.DataFrame(rows)
    chart_df = chart_df[pd.notnull(chart_df["irr"])].copy()

    color_map = {
        "Low": "#9ECAE1",
        "Base": "#4E80B1",
        "High": "#1F4E79",
    }

    size_map = {
        0.80: 8,
        1.00: 14,
        1.20: 22,
    }

    dc_label_map = {
        "Low": f"Low (${base_dc - 100.0:,.0f}/ft)",
        "Base": f"Base (${base_dc:,.0f}/ft)",
        "High": f"High (${base_dc + 100.0:,.0f}/ft)",
    }
    
    fig = make_subplots(
        rows=1,
        cols=3,
        shared_yaxes=True,
        horizontal_spacing=0.06,
        subplot_titles=[
            f"Downside (${pricing_cases[0][1]:.0f} / ${pricing_cases[0][2]:.2f})",
            f"Base (${pricing_cases[1][1]:.0f} / ${pricing_cases[1][2]:.2f})",
            f"Upside (${pricing_cases[2][1]:.0f} / ${pricing_cases[2][2]:.2f})",
        ],
    )
    panel_col_map = {"Downside": 1, "Base": 2, "Upside": 3}
    legend_seen = set()
    tc_jitter = {
        0.90: 0,
        1.00: 0,
        1.10: 0,
    }
    
    for pricing_name in ["Downside", "Base", "Upside"]:
        panel_df = chart_df[chart_df["pricing_case"] == pricing_name].copy()
        col_num = panel_col_map[pricing_name]
    
        for dc_case in ["Low", "Base", "High"]:
            dc_df = panel_df[panel_df["dc_case"] == dc_case].copy()
            if dc_df.empty:
                continue
    
            marker_sizes = [size_map.get(float(x), 14) for x in dc_df["tc_risk"]]
            show_legend = dc_case not in legend_seen
    
            fig.add_trace(
                go.Scatter(
                    x=[
                        b + tc_jitter.get(round(float(r), 2), 0)
                        for b, r in zip(dc_df["bid"], dc_df["tc_risk"])
                    ],                    
                    y=dc_df["irr"],
                    mode="markers",
                    name=dc_label_map[dc_case],
                    legendgroup="dc",
                    showlegend=show_legend,
                    marker=dict(
                        color=color_map[dc_case],
                        size=marker_sizes,
                        line=dict(color="white", width=0.5),
                        opacity=0.70,
                    ),
                    hovertemplate=(
                        "Bid: $%{x:,.0f}"
                        "<br>IRR: %{y:.1%}"
                        "<br>D&C: " + dc_label_map[dc_case] +
                        "<br>TC Risk: %{customdata[0]:.0%}"
                        "<br>Oil: $%{customdata[1]:.0f}"
                        "<br>Gas: $%{customdata[2]:.2f}"
                        "<extra></extra>"
                    ),
                    customdata=dc_df[["tc_risk", "oil_price", "gas_price"]].values,
                ),
                row=1,
                col=col_num,
            )

            legend_seen.add(dc_case)

    base_tc_risk = round(float(slot_df["tc_risk"].mean()), 2)
    base_bid_rounded = round(float(base_bid), 2)
    
    base_points = chart_df[
        (chart_df["pricing_case"] == "Base")
        & (chart_df["dc_case"] == "Base")
        & (chart_df["tc_risk"].round(2) == base_tc_risk)
        & (chart_df["bid"].round(2) == base_bid_rounded)
    ].copy()
    
    if base_points.empty:
        base_points = chart_df[
            (chart_df["pricing_case"] == "Base")
            & (chart_df["dc_case"] == "Base")
            & (chart_df["tc_risk"].round(2) == 1.00)
            & (chart_df["bid"].round(2) == base_bid_rounded)
        ].copy()


    
    tc_legend_items = [
        ("TC Risk 90%", 0.90),
        ("TC Risk 100%", 1.00),
        ("TC Risk 110%", 1.10),
    ]
    
    for label, risk in tc_legend_items:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                name=label,
                legendgroup="tc",
                showlegend=True,
                marker=dict(
                    color="rgba(120,120,120,0.85)",
                    size=size_map[risk],
                    line=dict(color="white", width=0.5),
                ),
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )

    if not base_points.empty:
        fig.add_trace(
            go.Scatter(
                x=base_points["bid"],
                y=base_points["irr"],
                mode="markers",
                name="Current Base Point",
                marker=dict(
                    color="#1F4E79",
                    size=18,
                    line=dict(color="black", width=2),
                    opacity=1.0,
                ),
                hovertemplate="Current Base Point<br>Bid: $%{x:,.0f}<br>IRR: %{y:.1%}<extra></extra>",
            ),
            row=1,
            col=2,
    )

    for c in [1, 2, 3]:
        fig.update_xaxes(
            title_text="$/Acre Bid",
            tickprefix="$",
            tickformat=",.0f",
            showgrid=False,
            row=1,
            col=c,
        )

    fig.update_yaxes(
        title_text="IRR",
        tickformat=".0%",
        showgrid=True,
        gridcolor="rgba(0,0,0,0.08)",
        row=1,
        col=1,
    )

    fig.update_layout(
        title=(
            "Scenario Matrix: IRR vs. $/Acre Bid"
            "<br><sup>Color = D&C | Marker Size = TC Risk</sup>"
        ),
        height=700,
        margin=dict(l=50, r=30, t=95, b=150),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.20,
            xanchor="center",
            x=0.5,
            font=dict(color="black"),
            traceorder="normal",
            entrywidth=160,
            entrywidthmode="pixels",
            tracegroupgap=20, 
        )
    )
    
    fig.update_xaxes(
        tickfont=dict(color="black"),
        title_font=dict(color="black"),
    )
    
    fig.update_yaxes(
        tickfont=dict(color="black"),
        title_font=dict(color="black"),
    )
    
    fig.update_annotations(font=dict(color="black"))
    
    return fig
# -----------------------------
# Session state init
# -----------------------------
if "slot_df" not in st.session_state:
    st.session_state["slot_df"] = build_slot_template(2)

if "deal_df" not in st.session_state:
    st.session_state["deal_df"] = None

if "all_slots_df" not in st.session_state:
    st.session_state["all_slots_df"] = None

if "irr" not in st.session_state:
    st.session_state["irr"] = None

if "moic" not in st.session_state:
    st.session_state["moic"] = None

if "model_has_run" not in st.session_state:
    st.session_state["model_has_run"] = False


# -----------------------------
# Sidebar deal inputs
# -----------------------------
st.sidebar.header("Deal-Level Inputs")

st.sidebar.subheader("Timing")
effective_date = st.sidebar.date_input("Effective Date", value=next_month_start())

st.sidebar.subheader("Pricing")
oil_price = st.sidebar.number_input("Oil Price ($/bbl)", value=60.0, step=1.0)
gas_price = st.sidebar.number_input("Gas Price ($/mcf)", value=3.75, step=0.05)

st.sidebar.subheader("Overrides")

use_acquisition_override = st.sidebar.checkbox("Use Acquisition Cost Override", value=False)
acquisition_cost_override = st.sidebar.number_input(
    "Acquisition Cost Override",
    min_value=0.0,
    value=0.0,
    step=1000.0,
    format="%.1f",
    disabled=not use_acquisition_override,
)

use_dc_override = st.sidebar.checkbox("Use D&C Override for All Slots", value=False)
dc_override = st.sidebar.number_input(
    "D&C Override ($/ft)",
    value=750.0,
    step=25.0,
    disabled=not use_dc_override,
)

use_bid_override = st.sidebar.checkbox("Use $/Acre Override for All Slots", value=False)
bid_override = st.sidebar.number_input(
    "$/Acre Override",
    value=8000.0,
    step=250.0,
    disabled=not use_bid_override,
)

st.sidebar.subheader("Taxes")
oil_sev_tax = st.sidebar.number_input("Oil Severance Tax ($/bbl)", value=0.10, step=0.01, format="%.3f")
gas_sev_tax = st.sidebar.number_input("Gas Severance Tax ($/mcf)", value=0.025, step=0.005, format="%.3f")
ad_val_tax = st.sidebar.number_input("Ad Valorem Tax (% of Net Revenue)", value=0.025, step=0.005, format="%.3f")

st.sidebar.subheader("Ethane / NGL")
ethane_rec = st.sidebar.checkbox("Recover Ethane", value=False)

with st.sidebar.expander("Content Percentages", expanded=False):
    content_ethane = st.number_input("Ethane Content %", value=0.50, step=0.01, format="%.3f")
    content_propane = st.number_input("Propane Content %", value=0.25, step=0.01, format="%.3f")
    content_isobutane = st.number_input("Isobutane Content %", value=0.065, step=0.005, format="%.3f")
    content_butane = st.number_input("Butane Content %", value=0.065, step=0.005, format="%.3f")
    content_pentanes = st.number_input("Pentanes Content %", value=0.12, step=0.01, format="%.3f")

with st.sidebar.expander("Recover Ethane Percentages", expanded=False):
    rec_ethane = st.number_input("Recover Ethane %", value=0.90, step=0.01, format="%.3f")
    rec_propane = st.number_input("Recover Propane %", value=0.98, step=0.01, format="%.3f")
    rec_isobutane = st.number_input("Recover Isobutane %", value=0.99, step=0.01, format="%.3f")
    rec_butane = st.number_input("Recover Butane %", value=0.99, step=0.01, format="%.3f")
    rec_pentanes = st.number_input("Recover Pentanes %", value=0.995, step=0.001, format="%.3f")

with st.sidebar.expander("Reject Ethane Percentages", expanded=False):
    rej_ethane = st.number_input("Reject Ethane %", value=0.20, step=0.01, format="%.3f")
    rej_propane = st.number_input("Reject Propane %", value=0.90, step=0.01, format="%.3f")
    rej_isobutane = st.number_input("Reject Isobutane %", value=0.98, step=0.01, format="%.3f")
    rej_butane = st.number_input("Reject Butane %", value=0.98, step=0.01, format="%.3f")
    rej_pentanes = st.number_input("Reject Pentanes %", value=0.995, step=0.001, format="%.3f")

with st.sidebar.expander("NGL Shrink Factors", expanded=False):
    shrink_ethane = st.number_input("Ethane Shrink", value=0.06634, step=0.001, format="%.5f")
    shrink_propane = st.number_input("Propane Shrink", value=0.091563, step=0.001, format="%.5f")
    shrink_isobutane = st.number_input("Isobutane Shrink", value=0.09963, step=0.001, format="%.5f")
    shrink_butane = st.number_input("Butane Shrink", value=0.103744, step=0.001, format="%.5f")
    shrink_pentanes = st.number_input("Pentanes Shrink", value=0.10968, step=0.001, format="%.5f")

with st.sidebar.expander("NGL Component Prices", expanded=False):
    price_ethane = st.number_input("Ethane Price", value=0.27, step=0.01, format="%.5f")
    price_propane = st.number_input("Propane Price", value=0.64625, step=0.01, format="%.5f")
    price_isobutane = st.number_input("Isobutane Price", value=0.84, step=0.01, format="%.5f")
    price_butane = st.number_input("Butane Price", value=0.7825, step=0.01, format="%.5f")
    price_pentanes = st.number_input("Pentanes Price", value=1.22125, step=0.01, format="%.5f")

st.sidebar.subheader("Dale Promote")
promote_enabled = st.sidebar.checkbox("Dale Promote On", value=False)

promote_rate = st.sidebar.number_input(
    "Promote",
    value=0.0625,
    step=0.01,
    format="%.4f",
    disabled=not promote_enabled,
)

promote_multiple = st.sidebar.number_input(
    "Promote Multiple",
    value=1.00,
    step=0.05,
    format="%.2f",
    disabled=not promote_enabled,
)

promote_irr_threshold = st.sidebar.number_input(
    "Promote IRR Threshold",
    value=0.00,
    step=0.01,
    format="%.4f",
    disabled=not promote_enabled,
)

deal_inputs = {
    "use_acquisition_override": use_acquisition_override,
    "acquisition_cost_override": acquisition_cost_override,
    "effective_date": effective_date,
    "oil_price": oil_price,
    "gas_price": gas_price,
    "use_dc_override": use_dc_override,
    "dc_override": dc_override,
    "use_bid_override": use_bid_override,
    "bid_override": bid_override,
    "oil_sev_tax": oil_sev_tax,
    "gas_sev_tax": gas_sev_tax,
    "ad_val_tax": ad_val_tax,
    "ethane_rec": ethane_rec,
    "content_ethane": content_ethane,
    "content_propane": content_propane,
    "content_isobutane": content_isobutane,
    "content_butane": content_butane,
    "content_pentanes": content_pentanes,
    "rec_ethane": rec_ethane,
    "rec_propane": rec_propane,
    "rec_isobutane": rec_isobutane,
    "rec_butane": rec_butane,
    "rec_pentanes": rec_pentanes,
    "rej_ethane": rej_ethane,
    "rej_propane": rej_propane,
    "rej_isobutane": rej_isobutane,
    "rej_butane": rej_butane,
    "rej_pentanes": rej_pentanes,
    "shrink_ethane": shrink_ethane,
    "shrink_propane": shrink_propane,
    "shrink_isobutane": shrink_isobutane,
    "shrink_butane": shrink_butane,
    "shrink_pentanes": shrink_pentanes,
    "price_ethane": price_ethane,
    "price_propane": price_propane,
    "price_isobutane": price_isobutane,
    "price_butane": price_butane,
    "price_pentanes": price_pentanes,
    "promote_enabled": promote_enabled,
    "promote_rate": promote_rate if promote_enabled else 0.0,
    "promote_multiple": promote_multiple if promote_enabled else 0.0,
    "promote_irr_threshold": promote_irr_threshold if promote_enabled else 0.0,
}


# -----------------------------
# Slot controls
# -----------------------------
st.subheader("Type Curve Assumptions")

file_mtime = os.path.getmtime("type_curve_library.xlsx")
tc_names = ["Choose TC"] + load_tc_names(file_mtime)

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    num_slots = st.number_input(
        "Number of Slots",
        min_value=1,
        step=1,
        value=len(st.session_state["slot_df"]),
    )

with col2:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    load_slots_clicked = st.button("Load Slots", use_container_width=True, type="primary")

with col3:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    refresh_tc_clicked = st.button(
        "Refresh Type Curves",
        use_container_width=True,
        type="secondary",
        key="refresh_tc_btn",
    )

if refresh_tc_clicked:
    load_tc_names.clear()
    st.rerun()

if load_slots_clicked:
    st.session_state["slot_df"] = resize_slot_df(st.session_state["slot_df"], num_slots)
    st.session_state["model_has_run"] = False

slot_df_display = apply_calc_unit_acres(st.session_state["slot_df"].copy())

slot_df = st.data_editor(
    slot_df_display,
    num_rows="fixed",
    use_container_width=True,
    key="slot_editor",
    column_config={
        "slot_id": st.column_config.NumberColumn("Slot", format="%d", disabled=True),
        "tc_name": st.column_config.SelectboxColumn("Type Curve", options=tc_names, required=True),
        "gross_wells": st.column_config.NumberColumn("Gross Wells", format="%.2f"),
        "net_acres": st.column_config.NumberColumn("Net Acres", format="%,.1f"),
        "unit_acres": st.column_config.NumberColumn("Unit Acres", format="%,.0f"),
        "use_calc_unit_acres": st.column_config.CheckboxColumn("Calc Unit Acres"),
        "pct_unitized": st.column_config.NumberColumn("% Unitized", format="%.2f"),
        "drilling_spud_month": st.column_config.DateColumn("Spud Month", format="YYYY-MM-DD"),
        "flowback_delay": st.column_config.NumberColumn("Flowback Delay", format="%d"),
        "net_revenue_interest": st.column_config.NumberColumn("NRI", format="%.2f"),
        "lateral_length": st.column_config.NumberColumn("Lateral Length (ft)", format="%,d"),
        "dc_costs": st.column_config.NumberColumn("D&C ($/ft)", format="$%,.0f"),
        "tc_risk": st.column_config.NumberColumn("TC Risk", format="%.2f"),
        "bid_per_acre": st.column_config.NumberColumn("$/Acre Bid", format="$%,d"),
        "oil_diff": st.column_config.NumberColumn("Oil Diff", format="$%.2f"),
        "gas_diff": st.column_config.NumberColumn("Gas Diff", format="$%.2f"),
        "ngl_diff": None,
        "oil_opex_bbl": st.column_config.NumberColumn("Oil Opex", format="$%.2f"),
        "gas_opex_mcf": st.column_config.NumberColumn("Gas Opex", format="$%.2f"),
        "ngl_opex": st.column_config.NumberColumn("NGL Opex", format="$%.2f"),
        "fixed_loe": st.column_config.NumberColumn("Fixed LOE", format="$%,.0f"),
        "ngl_yield": st.column_config.NumberColumn("NGL Yield", format="%.2f"),
    },
).copy()

slot_df = apply_calc_unit_acres(slot_df)
st.session_state["slot_df"] = slot_df

run_model_clicked = st.button("Run Model", type="primary")

if run_model_clicked:
    st.session_state["slot_df"] = slot_df

    if (slot_df["tc_name"] == "Choose TC").any():
        st.warning("Please select a Type Curve for all slots before running the model.")
        st.session_state["model_has_run"] = False
    else:
        all_slots_df, deal_df, slot_audit_df, deal_audit_df, irr, moic = run_deal_model(
            slot_df,
            deal_inputs,
        )

        st.session_state["all_slots_df"] = all_slots_df
        st.session_state["deal_df"] = deal_df
        st.session_state["slot_audit_df"] = slot_audit_df
        st.session_state["deal_audit_df"] = deal_audit_df
        st.session_state["irr"] = irr
        st.session_state["moic"] = moic
        st.session_state["model_has_run"] = True


# -----------------------------
# Results
# -----------------------------
DEAL_DISPLAY_COLS = [
    "date",
    "slot_net_oil_production",
    "slot_net_gas_production",
    "slot_net_ngl_production",
    "slot_oil_revenue",
    "slot_gas_revenue",
    "slot_ngl_revenue",
    "slot_total_revenue",
    "slot_loe",
    "slot_tax",
    "slot_operating_profit",
    "slot_capex",
    "slot_asset_purchase",
    "slot_promote",
    "slot_total_cash_flow",
    "cum_total_cf",
]

SLOT_DISPLAY_COLS = [
    "slot_id",
    "tc_name",
    "date",
    "slot_net_oil_production",
    "slot_net_gas_production",
    "slot_net_ngl_production",
    "slot_oil_revenue",
    "slot_gas_revenue",
    "slot_ngl_revenue",
    "slot_total_revenue",
    "slot_loe",
    "slot_tax",
    "slot_operating_profit",
    "slot_capex",
    "slot_asset_purchase",
    "slot_promote",
    "slot_total_cash_flow",
    "cum_total_cf",
]

if (
    st.session_state["model_has_run"]
    and st.session_state["deal_df"] is not None
    and st.session_state["all_slots_df"] is not None
):
    all_slots_df = st.session_state["all_slots_df"]
    deal_df = st.session_state["deal_df"]
    irr = st.session_state["irr"]
    moic = st.session_state["moic"]
    deal_audit_df = st.session_state["deal_audit_df"]
    slot_audit_df = st.session_state["slot_audit_df"]

    deal_display_df = deal_audit_df[[col for col in DEAL_DISPLAY_COLS if col in deal_audit_df.columns]].copy()
    slot_display_df = slot_audit_df[[col for col in SLOT_DISPLAY_COLS if col in slot_audit_df.columns]].copy()

    deal_audit_display_df = format_display_df(deal_display_df)
    slot_audit_display_df = format_display_df(slot_display_df)
    audit_excel_data = to_excel_bytes(deal_audit_df, slot_audit_df)

    with st.expander("Monthly Data", expanded=False):
        st.subheader("Total Deal Monthly Data")
        st.dataframe(deal_audit_display_df, use_container_width=True)

        st.subheader("Type Curve Monthly Data")
        st.dataframe(slot_audit_display_df, use_container_width=True)

        st.download_button(
            "Download in Excel",
            audit_excel_data,
            file_name="deal_audit.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="monthly_data_download_excel",
        )

    st.subheader("Deal Summary")

    total_net_acres = slot_df["net_acres"].sum()

    if deal_inputs["use_bid_override"]:
        total_acquisition = total_net_acres * deal_inputs["bid_override"]
    else:
        total_acquisition = (slot_df["net_acres"] * slot_df["bid_per_acre"]).sum()

    blended_bid = total_acquisition / total_net_acres if total_net_acres > 0 else 0.0

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Net Acres", format_accounting_number(total_net_acres, decimals=1))
    with col2:
        total_acquisition_cost = -deal_df["slot_asset_purchase"].sum()
        st.metric("Acquisition Cost", format_thousands_short(total_acquisition_cost, decimals=1))
    with col3:
        st.metric("$/Acre Bid", format_accounting_number(blended_bid, decimals=0, prefix="$"))
    with col4:
        st.metric("IRR", format_accounting_percent(irr, decimals=1, zero_as_dash=False) if irr is not None else "N/A")
    with col5:
        st.metric("MOIC", format_accounting_number(moic, decimals=2, suffix="x", zero_as_dash=False) if moic is not None else "N/A")

    st.subheader("Sensitivity Tables")

    base_dc = deal_inputs["dc_override"] if deal_inputs["use_dc_override"] else float(slot_df["dc_costs"].mean())
    base_bid = deal_inputs["bid_override"] if deal_inputs["use_bid_override"] else float(slot_df["bid_per_acre"].mean())

    scenario_scatter_chart = build_scenario_scatter_chart(
        slot_df=slot_df,
        deal_inputs=deal_inputs,
        base_bid=base_bid,
        base_dc=base_dc,
    )
    
    irr_sens_df, moic_sens_df = run_bid_dc_sensitivity(
        slot_df=slot_df,
        deal_inputs=deal_inputs,
        base_dc=base_dc,
        base_bid=base_bid,
    )

    irr_heatmap = build_heatmap(
        irr_sens_df,
        "IRR Sensitivity",
        metric="irr",
        x_title="D&C Costs ($/ft)",
        y_title="$/Acre Bid",
        base_x=base_dc,
        base_y=base_bid,
    )

    moic_heatmap = build_heatmap(
        moic_sens_df,
        "MOIC Sensitivity",
        metric="moic",
        x_title="D&C Costs ($/ft)",
        y_title="$/Acre Bid",
        base_x=base_dc,
        base_y=base_bid,
    )

    bid_values = build_sensitivity_range(base_bid, 500.0, 3)
    tc_risk_values = [0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30]
    oil_values = [50, 55, 60, 65, 70]
    gas_values = [3.25, 3.50, 3.75, 4.00, 4.25]

    irr_oil_bid_df, moic_oil_bid_df = run_oil_bid_sensitivity(
        slot_df=slot_df,
        deal_inputs=deal_inputs,
        oil_values=oil_values,
        bid_values=bid_values,
    )

    irr_gas_bid_df, moic_gas_bid_df = run_gas_bid_sensitivity(
        slot_df=slot_df,
        deal_inputs=deal_inputs,
        gas_values=gas_values,
        bid_values=bid_values,
    )

    irr_oil_bid_heatmap = build_heatmap(
        irr_oil_bid_df,
        "IRR Sensitivity",
        metric="irr",
        x_title="Oil Price ($/bbl)",
        y_title="$/Acre Bid",
        base_x=deal_inputs["oil_price"],
        base_y=base_bid,
    )

    moic_oil_bid_heatmap = build_heatmap(
        moic_oil_bid_df,
        "MOIC Sensitivity",
        metric="moic",
        x_title="Oil Price ($/bbl)",
        y_title="$/Acre Bid",
        base_x=deal_inputs["oil_price"],
        base_y=base_bid,
    )

    irr_gas_bid_heatmap = build_heatmap(
        irr_gas_bid_df,
        "IRR Sensitivity",
        metric="irr",
        x_title="Gas Price ($/mcf)",
        y_title="$/Acre Bid",
        base_x=deal_inputs["gas_price"],
        base_y=base_bid,
    )

    moic_gas_bid_heatmap = build_heatmap(
        moic_gas_bid_df,
        "MOIC Sensitivity",
        metric="moic",
        x_title="Gas Price ($/mcf)",
        y_title="$/Acre Bid",
        base_x=deal_inputs["gas_price"],
        base_y=base_bid,
    )

    with st.expander(r"D&C Costs (\$/ft) vs. \$/Acre Bid Sensitivity", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### IRR Sensitivity")
            st.plotly_chart(irr_heatmap, use_container_width=True)
        with col2:
            st.markdown("### MOIC Sensitivity")
            st.plotly_chart(moic_heatmap, use_container_width=True)
    
    with st.expander(r"Oil Price vs. \$/Acre Bid Sensitivity", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### IRR Sensitivity")
            st.plotly_chart(irr_oil_bid_heatmap, use_container_width=True)
        with col2:
            st.markdown("### MOIC Sensitivity")
            st.plotly_chart(moic_oil_bid_heatmap, use_container_width=True)

    with st.expander("Gas Price vs. $/Acre Bid Sensitivity", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### IRR Sensitivity")
            st.plotly_chart(irr_gas_bid_heatmap, use_container_width=True)
        with col2:
            st.markdown("### MOIC Sensitivity")
            st.plotly_chart(moic_gas_bid_heatmap, use_container_width=True)

    irr_tcrisk_bid_df, moic_tcrisk_bid_df = run_tcrisk_bid_sensitivity(
        slot_df=slot_df,
        deal_inputs=deal_inputs,
        tc_risk_values=tc_risk_values,
        bid_values=bid_values,
    )

    base_tc_risk = float(slot_df["tc_risk"].iloc[0])

    irr_tcrisk_bid_heatmap = build_heatmap(
        irr_tcrisk_bid_df,
        "IRR Sensitivity",
        metric="irr",
        x_title="TC Risk",
        y_title="$/Acre Bid",
        x_format="percent",
        y_format="dollar",
        base_x=base_tc_risk,
        base_y=base_bid,
    )

    moic_tcrisk_bid_heatmap = build_heatmap(
        moic_tcrisk_bid_df,
        "MOIC Sensitivity",
        metric="moic",
        x_title="TC Risk",
        y_title="$/Acre Bid",
        x_format="percent",
        y_format="dollar",
        base_x=base_tc_risk,
        base_y=base_bid,
    )

    with st.expander("TC Risk vs. $/Acre Bid Sensitivity", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### IRR Sensitivity")
            st.plotly_chart(irr_tcrisk_bid_heatmap, use_container_width=True)
        with col2:
            st.markdown("### MOIC Sensitivity")
            st.plotly_chart(moic_tcrisk_bid_heatmap, use_container_width=True)

    quarterly_output_df = build_quarterly_output_table(
        deal_df=deal_df,
        all_slots_df=all_slots_df,
        slot_df=slot_df,
        deal_inputs=deal_inputs,
    )

    quarterly_output_display_df, quarterly_row_styles = build_quarterly_output_display_table(quarterly_output_df)
    quarterly_output_styler = style_quarterly_output_table(
        quarterly_output_display_df,
        quarterly_row_styles,
    )

    with st.expander("Quarterly Output", expanded=False):
        st.markdown(quarterly_output_styler.to_html(), unsafe_allow_html=True)

        st.markdown("### Deal Highlights")
        h1, h2, h3, h4 = st.columns(4)

        with h1:
            render_deal_highlight_box(
                "IRR",
                format_accounting_percent(irr, decimals=1, zero_as_dash=False) if irr is not None else "N/A",
            )
        with h2:
            render_deal_highlight_box(
                "MOIC",
                format_accounting_number(moic, decimals=2, suffix="x", zero_as_dash=False) if moic is not None else "N/A",
            )
        with h3:
            render_deal_highlight_box(
                "Net Acres",
                format_accounting_number(total_net_acres, decimals=1),
            )
        with h4:
            render_deal_highlight_box(
                "$/Acre Bid",
                format_accounting_number(blended_bid, decimals=0, prefix="$"),
            )

    tc_output_display_df, tc_output_row_styles = build_tc_assumptions_output_display_table(slot_df)
    tc_output_styler = style_tc_assumptions_output_table(
        tc_output_display_df,
        tc_output_row_styles,
    )

    with st.expander("TC Assumptions Output", expanded=False):
        st.markdown(tc_output_styler.to_html(), unsafe_allow_html=True)

    cum_fcf_chart = build_cumulative_fcf_chart(deal_df, slot_df)
    
    with st.expander("Charts", expanded=False):
        chart_tab1, chart_tab2, chart_tab3 = st.tabs(
            ["Cumulative FCF", "Production", "Scenario Matrix"]
        )
    
        with chart_tab1:
            st.plotly_chart(cum_fcf_chart, use_container_width=True)
    
        with chart_tab2:
            prod_chart_view = st.radio(
                "Production Chart View",
                ["Stacked BOE/d", "Stream Split"],
                horizontal=True,
                key="prod_chart_view",
            )
            prod_chart = build_production_profile_chart(deal_df, chart_view=prod_chart_view)
            st.plotly_chart(prod_chart, use_container_width=True)
    
        with chart_tab3:
            st.plotly_chart(scenario_scatter_chart, use_container_width=True)

else:
    st.info("Set your deal assumptions and slot inputs, then click Run Model.")
