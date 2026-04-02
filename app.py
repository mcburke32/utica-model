import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO

import plotly.graph_objects as go

from model import run_deal_model

st.set_page_config(page_title="Utica Deal Model", layout="wide")
st.title("Utica Deal Model")


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

def format_thousands_short(x, decimals=1, prefix="$", suffix="k", zero_as_dash=True, null_as_blank=True):
    if pd.isnull(x):
        return "" if null_as_blank else "-"

    x = float(x)

    if zero_as_dash and is_effectively_zero(x):
        return "-"

    x_thousands = x / 1000.0
    abs_text = f"{abs(x_thousands):,.{decimals}f}"
    text = f"{prefix}{abs_text}{suffix}"

    return f"({text})" if x < 0 else text

@st.cache_data
def load_tc_names():
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
        rows.append({
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
        })
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
        elif fmt == "percent":
            return f"{v:.0%}"
        elif fmt == "float2":
            return f"{v:.2f}"
        else:
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
        xaxis=dict(
            title=x_title,
            side="top",
            type="category",
            automargin=True,
        ),
        yaxis=dict(
            title=y_title,
            type="category",
            automargin=True,
        ),
        margin=dict(l=90, r=20, t=60, b=50),
        height=360,
    )

    if base_x is not None and base_y is not None:
        try:
            x_vals_raw = list(heatmap_df.columns)
            y_vals_raw = list(heatmap_df.index)

            def find_closest_index(values, target):
                return min(range(len(values)), key=lambda i: abs(float(values[i]) - float(target)))

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

    q_days = pd.Series(
        {q: quarter_days_from_label(q) for q in quarter_order},
        index=quarter_order,
        dtype=float,
    )

    y_days = pd.Series(
        {y: year_days_from_label(y) for y in year_order},
        index=year_order,
        dtype=float,
    )

    q = deal.groupby("quarter_label").sum(numeric_only=True).reindex(quarter_order)
    y = deal.groupby("year_label").sum(numeric_only=True).reindex(year_order)

    slot_metrics = slot_inputs.copy()
    slot_metrics["spud_quarter"] = "Q" + slot_metrics["drilling_spud_month"].dt.quarter.astype(str) + " " + slot_metrics["drilling_spud_month"].dt.strftime("%y")
    slot_metrics["spud_year"] = slot_metrics["drilling_spud_month"].dt.year.astype(str)

    unit_acres_final = np.where(
        slot_metrics["use_calc_unit_acres"].fillna(False),
        slot_metrics["gross_wells"] * slot_metrics["lateral_length"] / 50.0,
        slot_metrics["unit_acres"]
    )

    working_interest = np.where(
        unit_acres_final != 0,
        (slot_metrics["net_acres"] / unit_acres_final) * slot_metrics["pct_unitized"],
        0.0
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


def format_quarterly_output_table(df):
    formatted = df.copy().astype(object)

    pct_rows = {
        "Realized Pricing - NGL (% of WTI)",
    }

    dollar_per_unit_rows = {
        "Taxes / Mcfe",
        "LOE / Mcfe",
        "Promote / Mcfe",
    }

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

    for idx in formatted.index:
        for col in formatted.columns:
            val = formatted.loc[idx, col]

            if col == " ":
                formatted.loc[idx, col] = ""
            elif pd.isnull(val):
                formatted.loc[idx, col] = "-"
            elif idx in pct_rows:
                formatted.loc[idx, col] = format_accounting_percent(
                    val, decimals=0, null_as_blank=False
                )
            elif idx in dollar_per_unit_rows:
                formatted.loc[idx, col] = format_accounting_number(
                    val, decimals=2, prefix="$", null_as_blank=False
                )
            elif idx in price_rows:
                formatted.loc[idx, col] = format_accounting_number(
                    val, decimals=2, prefix="$", null_as_blank=False
                )
            elif idx in production_rows:
                formatted.loc[idx, col] = format_accounting_production(
                    val, null_as_blank=False
                )
            else:
                formatted.loc[idx, col] = format_accounting_number(
                    val, decimals=1, prefix="$", null_as_blank=False
                )

    return formatted


QUARTERLY_HEADER_COLOR = "#4E80B1"  # RGB(78, 128, 177)


def build_quarterly_output_display_table(df):
    first_col = "$ in Thousands"
    data_cols = list(df.columns)

    pct_rows = {
        "Realized Pricing - NGL (% of WTI)",
    }

    dollar_per_unit_rows = {
        "Taxes / Mcfe",
        "LOE / Mcfe",
        "Promote / Mcfe",
    }

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
        elif source_row in dollar_per_unit_rows:
            return format_accounting_number(val, decimals=2, prefix="$")
        elif source_row in price_rows:
            return format_accounting_number(val, decimals=2, prefix="$")
        elif source_row in production_rows:
            return format_accounting_production(val)
        else:
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

    add_data("Gross Wells Spud", "Gross Wells Spud", indent=False)
    add_data("Net Wells Spud", "Net Wells Spud", indent=False)

    add_gap()

    add_section("Production")
    add_data("Crude Oil", "Production - Crude Oil", indent=True)
    add_data("Natural Gas", "Production - Natural Gas", indent=True)
    add_data("NGL's", "Production - NGL's", indent=True)
    add_data("Total (Mcfe/d)", "Production - Total (Mcfe/d)", indent=False, style="bold")

    add_gap()

    add_section("Revenues")
    add_data("Crude Oil", "Revenues - Crude Oil", indent=True)
    add_data("Natural Gas", "Revenues - Natural Gas", indent=True)
    add_data("NGL's", "Revenues - NGL's", indent=True)
    add_data("Total", "Revenues - Total", indent=False)

    add_gap()

    add_section("Operating Expenses")
    add_data("Taxes", "Operating Expenses - Taxes", indent=True)
    add_data("LOE", "Operating Expenses - LOE", indent=True)
    add_data("Dale Promote", "Operating Expenses - Dale Promote", indent=True)
    add_data("Total", "Operating Expenses - Total Opex", indent=False)

    add_gap()

    add_data("Taxes / Mcfe", "Taxes / Mcfe", indent=False, style="italic")
    add_data("LOE / Mcfe", "LOE / Mcfe", indent=False, style="italic")
    add_data("Promote / Mcfe", "Promote / Mcfe", indent=False, style="italic")

    add_gap()

    add_data("EBITDA", "EBITDA", indent=False, style="bold")

    add_gap()

    add_section("Capital Expenditures")
    add_data("D&C", "Capital Expenditures - D&C", indent=True)
    add_data("Acquisition", "Capital Expenditures - Acquisition", indent=True)
    add_data("Total", "Capital Expenditures - Total", indent=False)

    add_gap()

    add_data("Free Cash Flow", "Free Cash Flow", indent=False, style="bold")

    add_gap()

    add_data("Cumulative FCF", "Cumulative FCF", indent=False, style="footer")

    display_df = pd.DataFrame(rows)
    return display_df, row_styles


def style_quarterly_output_table(display_df, row_styles):
    style_map = pd.Series(row_styles, index=display_df.index)

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

    first_col = display_df.columns[0]
    other_cols = list(display_df.columns[1:])

    styler = (
        display_df.style
        .apply(row_style, axis=1)
        .hide(axis="index")
        .set_properties(subset=[first_col], **{
            "text-align": "left",
            "white-space": "pre",
        })
        .set_properties(subset=other_cols, **{
            "text-align": "right",
        })
        .set_table_styles([
            {
                "selector": "table",
                "props": [
                    ("border-collapse", "collapse"),
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
                    ("border", "1px solid #d9d9d9"),
                    ("padding", "6px 10px"),
                ],
            },
            {
                "selector": "tbody td",
                "props": [
                    ("border", "1px solid #e6e6e6"),
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
                "props": [
                    ("text-align", "right"),
                ],
            },
        ], overwrite=False)
    )

    return styler


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
    disabled=not use_acquisition_override
)

use_dc_override = st.sidebar.checkbox("Use D&C Override for All Slots", value=False)
dc_override = st.sidebar.number_input(
    "D&C Override ($/ft)",
    value=750.0,
    step=25.0,
    disabled=not use_dc_override
)

use_bid_override = st.sidebar.checkbox("Use $/Acre Override for All Slots", value=False)
bid_override = st.sidebar.number_input(
    "$/Acre Override",
    value=8000.0,
    step=250.0,
    disabled=not use_bid_override
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
acreage_carry = st.sidebar.number_input("Acreage Carry", value=0.0625, step=0.01, format="%.4f", disabled=not promote_enabled)
through_first_well_carry = st.sidebar.number_input("Through First Well Carry", value=0.0625, step=0.01, format="%.4f", disabled=not promote_enabled)
promote_rate = st.sidebar.number_input("Promote", value=0.0625, step=0.01, format="%.4f", disabled=not promote_enabled)
promote_multiple = st.sidebar.number_input("Promote Multiple", value=1.00, step=0.05, format="%.2f", disabled=not promote_enabled)

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
    "acreage_carry": acreage_carry if promote_enabled else 0.0,
    "through_first_well_carry": through_first_well_carry if promote_enabled else 0.0,
    "promote_rate": promote_rate if promote_enabled else 0.0,
    "promote_multiple": promote_multiple if promote_enabled else 0.0,
    "promote_irr_threshold": acreage_carry if promote_enabled else 0.0,
}


# -----------------------------
# Slot controls
# -----------------------------
st.header("Type Curve Assumptions")

tc_names = ["Choose TC"] + load_tc_names()

col1, col2 = st.columns([2, 1])

with col1:
    num_slots = st.number_input("Number of Slots", min_value=1, step=1, value=1)

with col2:
    st.write("")
    st.write("")
    load_slots_clicked = st.button("Load Slots")

if load_slots_clicked:
    st.session_state["slot_df"] = resize_slot_df(st.session_state["slot_df"], num_slots)
    st.session_state["model_has_run"] = False

st.session_state["slot_df"] = apply_calc_unit_acres(st.session_state["slot_df"])

slot_df_display = st.session_state["slot_df"]

st.markdown(
    f"""
    <style>
    div[data-testid="stDataEditor"] thead th {{
        background-color: {QUARTERLY_HEADER_COLOR} !important;
        color: white !important;
        font-weight: 700 !important;
        border-color: #d9d9d9 !important;
    }}

    div[data-testid="stDataEditor"] thead th * {{
        color: white !important;
        font-weight: 700 !important;
    }}

    div[data-testid="stDataEditor"] tbody td {{
        border-color: #e6e6e6 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

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

run_model_clicked = st.button("Run Model")

slot_df = apply_calc_unit_acres(slot_df)

if not slot_df.equals(st.session_state["slot_df"]):
    st.session_state["slot_df"] = slot_df
    st.rerun()
else:
    st.session_state["slot_df"] = slot_df

if run_model_clicked:
    st.session_state["slot_df"] = slot_df

    if (slot_df["tc_name"] == "Choose TC").any():
        st.warning("Please select a Type Curve for all slots before running the model.")
        st.session_state["model_has_run"] = False
    else:
        all_slots_df, deal_df, slot_audit_df, deal_audit_df, irr, moic = run_deal_model(
            slot_df,
            deal_inputs
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

    deal_display_df = deal_audit_df[
        [col for col in DEAL_DISPLAY_COLS if col in deal_audit_df.columns]
    ].copy()

    slot_display_df = slot_audit_df[
        [col for col in SLOT_DISPLAY_COLS if col in slot_audit_df.columns]
    ].copy()

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

    base_dc = (
        deal_inputs["dc_override"]
        if deal_inputs["use_dc_override"]
        else float(slot_df["dc_costs"].mean())
    )

    base_bid = (
        deal_inputs["bid_override"]
        if deal_inputs["use_bid_override"]
        else float(slot_df["bid_per_acre"].mean())
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

    with st.expander("D&C Costs (\$/ft) vs. \$/Acre Bid Sensitivity", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### IRR Sensitivity")
            st.plotly_chart(irr_heatmap, use_container_width=True)

        with col2:
            st.markdown("### MOIC Sensitivity")
            st.plotly_chart(moic_heatmap, use_container_width=True)

    with st.expander("Oil Price vs. \$/Acre Bid Sensitivity", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### IRR Sensitivity")
            st.plotly_chart(irr_oil_bid_heatmap, use_container_width=True)

        with col2:
            st.markdown("### MOIC Sensitivity")
            st.plotly_chart(moic_oil_bid_heatmap, use_container_width=True)

    with st.expander("Gas Price vs. \$/Acre Bid Sensitivity", expanded=False):
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

    with st.expander("TC Risk vs. \$/Acre Bid Sensitivity", expanded=False):
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
        st.markdown(
            quarterly_output_styler.to_html(),
            unsafe_allow_html=True,
        )

        st.markdown("### Deal Highlights")

        h1, h2, h3, h4 = st.columns(4)

        with h1:
            render_deal_highlight_box(
                "IRR",
                format_accounting_percent(irr, decimals=1, zero_as_dash=False) if irr is not None else "N/A"
            )

        with h2:
            render_deal_highlight_box(
                "MOIC",
                format_accounting_number(moic, decimals=2, suffix="x", zero_as_dash=False) if moic is not None else "N/A"
            )

        with h3:
            render_deal_highlight_box(
                "Net Acres",
                format_accounting_number(total_net_acres, decimals=1)
            )

        with h4:
            render_deal_highlight_box(
                "$/Acre Bid",
                format_accounting_number(blended_bid, decimals=0, prefix="$")
            )
else:
    st.info("Set your deal assumptions and slot inputs, then click Run Model.")
