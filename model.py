import os
from functools import lru_cache
from datetime import date

import numpy as np
import pandas as pd

try:
    import pyxirr
except Exception:
    pyxirr = None


# -----------------------------
# Library + utility helpers
# -----------------------------
def clean_tc_name(name):
    return str(name).strip().lower().replace(" ", "_")


@lru_cache(maxsize=8)
def _load_type_curve_library_cached(file_path, file_mtime):
    tc_monthly = pd.read_excel(file_path, sheet_name="tc_monthly")
    tc_metadata = pd.read_excel(file_path, sheet_name="tc_metadata")

    tc_monthly["tc_name"] = tc_monthly["tc_name"].map(clean_tc_name)
    tc_metadata["tc_name"] = tc_metadata["tc_name"].map(clean_tc_name)

    library = {}
    for tc_name, monthly_df in tc_monthly.groupby("tc_name"):
        meta_row = tc_metadata.loc[tc_metadata["tc_name"] == tc_name]
        if meta_row.empty:
            continue

        library[tc_name] = {
            "base_lateral": float(meta_row["base_lateral"].iloc[0]),
            "monthly": monthly_df[["month", "oil", "gas"]].copy().sort_values("month"),
        }

    return library


def load_type_curve_library(file_path="type_curve_library.xlsx"):
    file_mtime = os.path.getmtime(file_path)
    return _load_type_curve_library_cached(file_path, file_mtime)


def default_effective_date():
    today = date.today()
    if today.month == 12:
        return pd.Timestamp(today.year + 1, 1, 1)
    return pd.Timestamp(today.year, today.month + 1, 1)


# -----------------------------
# NGL factors
# -----------------------------
def build_slot_ngl_factors(
    slot,
    global_assumptions,
    content_percentages,
    recover_ethane_percentages,
    reject_ethane_percentages,
    ngl_prices,
    ngl_shrink_factors,
):
    ngl_yield = float(slot["ngl_yield"])

    if int(global_assumptions["ethane_rec"]) == 1:
        recoveries = recover_ethane_percentages
        recovery_case = "recover"
    else:
        recoveries = reject_ethane_percentages
        recovery_case = "reject"

    rows = []

    for component in content_percentages:
        content_pct = float(content_percentages[component])
        implied_ngl_content = content_pct * ngl_yield
        recovery_pct = float(recoveries[component])
        sales_volume_factor = implied_ngl_content * recovery_pct
        shrink_factor = float(ngl_shrink_factors[component])
        shrink_contribution = sales_volume_factor * shrink_factor
        component_price = float(ngl_prices[component])

        rows.append(
            {
                "component": component,
                "content_pct": content_pct,
                "implied_ngl_content": implied_ngl_content,
                "recovery_pct": recovery_pct,
                "sales_volume_factor": sales_volume_factor,
                "shrink_factor": shrink_factor,
                "shrink_contribution": shrink_contribution,
                "component_price": component_price,
            }
        )

    ngl_detail_df = pd.DataFrame(rows)

    shrink = float(ngl_detail_df["shrink_contribution"].sum())

    aggregate_ngl_price = float(
        (
            ngl_detail_df["recovery_pct"]
            * ngl_detail_df["content_pct"]
            * ngl_detail_df["component_price"]
        ).sum()
    )

    ngl_pct_of_wti = aggregate_ngl_price * 42.0 / 60.0

    return {
        "recovery_case": recovery_case,
        "recoveries": recoveries,
        "detail_df": ngl_detail_df,
        "shrink": shrink,
        "aggregate_ngl_price": aggregate_ngl_price,
        "ngl_pct_of_wti": ngl_pct_of_wti,
    }


# -----------------------------
# Slot metrics
# -----------------------------
def calc_slot_metrics(slot, deal_settings, total_net_acres):
    slot = slot.copy()

    if bool(deal_settings["use_bid_override"]):
        bid_price_final = float(deal_settings["bid_override"])
    else:
        bid_price_final = float(slot["bid_per_acre"])

    if bool(slot["use_calc_unit_acres"]):
        unit_acres_final = (
            float(slot["gross_wells"]) * float(slot["lateral_length"]) / 50.0
        )
    else:
        unit_acres_final = float(slot["unit_acres"])

    if unit_acres_final == 0:
        working_interest = 0.0
    else:
        working_interest = (
            float(slot["net_acres"]) / unit_acres_final
        ) * float(slot["pct_unitized"])

    net_wells = working_interest * float(slot["gross_wells"])

    use_acquisition_override = bool(
        deal_settings.get("use_acquisition_override", False)
    )
    acquisition_cost_override = float(
        deal_settings.get("acquisition_cost_override", 0.0)
    )

    if use_acquisition_override:
        if total_net_acres == 0:
            acquisition_cost = 0.0
        else:
            acquisition_cost = (
                float(slot["net_acres"]) / total_net_acres
            ) * acquisition_cost_override
    else:
        acquisition_cost = float(slot["net_acres"]) * bid_price_final

    slot["bid_price_final"] = bid_price_final
    slot["unit_acres_final"] = unit_acres_final
    slot["working_interest"] = working_interest
    slot["net_wells_calc"] = net_wells
    slot["acquisition_cost"] = acquisition_cost

    return slot


# -----------------------------
# Single well economics
# -----------------------------
def run_single_slot_economics(slot, type_curve_library, global_assumptions, slot_ngl):
    tc_name = clean_tc_name(slot["tc_name"])
    lateral_length = float(slot["lateral_length"])
    spud_date = pd.to_datetime(slot["drilling_spud_month"])
    flowback_delay = int(slot["flowback_delay"])
    ngl_yield = float(slot["ngl_yield"])
    nri = float(slot["net_revenue_interest"])
    tc_risk = float(slot["tc_risk"])

    oil_price = float(global_assumptions["oil_price"])
    gas_price = float(global_assumptions["gas_price"])
    oil_sev_tax = float(global_assumptions["oil_sev_tax"])
    gas_sev_tax = float(global_assumptions["gas_sev_tax"])
    ad_val_tax = float(global_assumptions["ad_val_tax"])

    oil_diff = float(slot["oil_diff"])
    gas_diff = float(slot["gas_diff"])

    oil_opex_bbl = float(slot["oil_opex_bbl"])
    gas_opex_mcf = float(slot["gas_opex_mcf"])
    ngl_opex = float(slot["ngl_opex"])
    fixed_loe = float(slot["fixed_loe"])
    dc_costs = float(slot["dc_costs"])

    tc_info = type_curve_library[tc_name]
    base_lateral = float(tc_info["base_lateral"])
    tc_df = tc_info["monthly"].copy()

    ll_scale = lateral_length / base_lateral

    tc_df["base_oil_scaled"] = tc_df["oil"] * tc_risk * ll_scale
    tc_df["base_gas_scaled"] = tc_df["gas"] * tc_risk * ll_scale

    tc_df["gross_oil_production"] = tc_df["base_oil_scaled"]
    tc_df["gross_gas_production"] = tc_df["base_gas_scaled"] * (
        1.0 - float(slot_ngl["shrink"])
    )
    tc_df["gross_ngl_production"] = tc_df["base_gas_scaled"] * ngl_yield / 42.0

    tc_df["monthly_production_boe"] = (
        tc_df["gross_oil_production"]
        + tc_df["gross_ngl_production"]
        + (tc_df["gross_gas_production"] / 6.0)
    )

    tc_df["oil_royalty_volumes"] = tc_df["gross_oil_production"] * (1.0 - nri)
    tc_df["gas_royalty_volumes"] = tc_df["gross_gas_production"] * (1.0 - nri)
    tc_df["ngl_royalty_volumes"] = tc_df["gross_ngl_production"] * (1.0 - nri)

    tc_df["equity_oil_production"] = (
        tc_df["gross_oil_production"] - tc_df["oil_royalty_volumes"]
    )
    tc_df["equity_gas_production"] = (
        tc_df["gross_gas_production"] - tc_df["gas_royalty_volumes"]
    )
    tc_df["equity_ngl_production"] = (
        tc_df["gross_ngl_production"] - tc_df["ngl_royalty_volumes"]
    )

    tc_df["local_oil_price"] = oil_price + oil_diff
    tc_df["local_gas_price"] = gas_price + gas_diff
    tc_df["local_ngl_price"] = oil_price * float(slot_ngl["ngl_pct_of_wti"])

    tc_df["oil_revenue"] = tc_df["local_oil_price"] * tc_df["equity_oil_production"]
    tc_df["gas_revenue"] = tc_df["local_gas_price"] * tc_df["equity_gas_production"]
    tc_df["ngl_revenue"] = tc_df["local_ngl_price"] * tc_df["equity_ngl_production"]
    tc_df["total_revenue"] = (
        tc_df["oil_revenue"] + tc_df["gas_revenue"] + tc_df["ngl_revenue"]
    )

    variable_loe = -(
        tc_df["gross_oil_production"] * oil_opex_bbl
        + tc_df["gross_gas_production"] * gas_opex_mcf
        + tc_df["gross_ngl_production"] * ngl_opex
    )
    fixed_loe_monthly = -fixed_loe

    tc_df["variable_loe"] = variable_loe
    tc_df["fixed_loe_monthly"] = fixed_loe_monthly
    tc_df["total_loe"] = tc_df["variable_loe"] + tc_df["fixed_loe_monthly"]

    tc_df["ad_valorem_tax"] = -(ad_val_tax * tc_df["total_revenue"])
    tc_df["oil_severance_tax"] = -(oil_sev_tax * tc_df["equity_oil_production"])
    tc_df["gas_severance_tax"] = -(
        gas_sev_tax
        * (tc_df["equity_gas_production"] / (1.0 - float(slot_ngl["shrink"])))
    )

    tc_df["tax"] = (
        tc_df["ad_valorem_tax"]
        + tc_df["oil_severance_tax"]
        + tc_df["gas_severance_tax"]
    )

    tc_df["net_revenue"] = tc_df["total_revenue"]
    tc_df["opex"] = tc_df["variable_loe"]

    tc_df["period"] = tc_df["month"]

    period_0 = pd.DataFrame(
        {
            "period": [0],
            "base_oil_scaled": [0.0],
            "base_gas_scaled": [0.0],
            "gross_oil_production": [0.0],
            "gross_gas_production": [0.0],
            "gross_ngl_production": [0.0],
            "monthly_production_boe": [0.0],
            "oil_royalty_volumes": [0.0],
            "gas_royalty_volumes": [0.0],
            "ngl_royalty_volumes": [0.0],
            "equity_oil_production": [0.0],
            "equity_gas_production": [0.0],
            "equity_ngl_production": [0.0],
            "local_oil_price": [oil_price + oil_diff],
            "local_gas_price": [gas_price + gas_diff],
            "local_ngl_price": [oil_price * float(slot_ngl["ngl_pct_of_wti"])],
            "oil_revenue": [0.0],
            "gas_revenue": [0.0],
            "ngl_revenue": [0.0],
            "total_revenue": [0.0],
            "net_revenue": [0.0],
            "opex": [0.0],
            "variable_loe": [0.0],
            "fixed_loe_monthly": [0.0],
            "total_loe": [0.0],
            "tax": [0.0],
        }
    )
    df = pd.concat(
        [
            period_0,
            tc_df[
                [
                    "period",
                    "base_oil_scaled",
                    "base_gas_scaled",
                    "gross_oil_production",
                    "gross_gas_production",
                    "gross_ngl_production",
                    "monthly_production_boe",
                    "oil_royalty_volumes",
                    "gas_royalty_volumes",
                    "ngl_royalty_volumes",
                    "equity_oil_production",
                    "equity_gas_production",
                    "equity_ngl_production",
                    "local_oil_price",
                    "local_gas_price",
                    "local_ngl_price",
                    "net_revenue",
                    "opex",
                    "variable_loe",
                    "fixed_loe_monthly",
                    "total_loe",
                    "tax",
                ]
            ],
        ],
        ignore_index=True,
    )

    df = df.sort_values("period").reset_index(drop=True)

    dates = []
    for _, row in df.iterrows():
        if int(row["period"]) == 0:
            dates.append(spud_date)
        elif int(row["period"]) == 1:
            dates.append(spud_date + pd.DateOffset(months=flowback_delay))
        else:
            dates.append(dates[-1] + pd.DateOffset(months=1))

    df["date"] = dates

    df["capex"] = 0.0
    df.loc[df["period"] == 0, "capex"] = -(dc_costs * lateral_length)

    df["operating_cf"] = df["net_revenue"] + df["total_loe"] + df["tax"]

    df["operating_cf_shut_in"] = np.where(
        (df["period"] > 0) & (df["operating_cf"] < 0),
        0.0,
        df["operating_cf"],
    )

    df["cash_flow"] = df["operating_cf_shut_in"] + df["capex"]

    return df


# -----------------------------
# Slot financials
# -----------------------------
def build_slot_financials(
    slot, deal_settings, type_curve_library, global_assumptions, total_net_acres
):
    slot = calc_slot_metrics(slot, deal_settings, total_net_acres)

    slot_ngl = build_slot_ngl_factors(
        slot=slot,
        global_assumptions=global_assumptions,
        content_percentages=global_assumptions["content_percentages"],
        recover_ethane_percentages=global_assumptions["recover_ethane_percentages"],
        reject_ethane_percentages=global_assumptions["reject_ethane_percentages"],
        ngl_prices=global_assumptions["ngl_prices"],
        ngl_shrink_factors=global_assumptions["ngl_shrink_factors"],
    )

    one_well_df = run_single_slot_economics(
        slot=slot,
        type_curve_library=type_curve_library,
        global_assumptions=global_assumptions,
        slot_ngl=slot_ngl,
    ).copy()

    df = one_well_df.copy()

    gross_wells = float(slot["gross_wells"])
    net_wells = float(slot["net_wells_calc"])

    df["slot_id"] = slot["slot_id"]
    df["tc_name"] = slot["tc_name"]

    df["slot_gross_oil_production"] = df["gross_oil_production"] * gross_wells
    df["slot_gross_gas_production"] = df["gross_gas_production"] * gross_wells
    df["slot_gross_ngl_production"] = df["gross_ngl_production"] * gross_wells
    df["slot_gross_boe"] = df["monthly_production_boe"] * gross_wells

    df["slot_net_oil_production"] = df["equity_oil_production"] * net_wells
    df["slot_net_gas_production"] = df["equity_gas_production"] * net_wells
    df["slot_net_ngl_production"] = df["equity_ngl_production"] * net_wells
    df["slot_net_boe"] = (
        df["equity_oil_production"]
        + df["equity_ngl_production"]
        + (df["equity_gas_production"] / 6.0)
    ) * net_wells

    df["slot_oil_revenue"] = df["oil_revenue"] * net_wells
    df["slot_gas_revenue"] = df["gas_revenue"] * net_wells
    df["slot_ngl_revenue"] = df["ngl_revenue"] * net_wells
    df["slot_total_revenue"] = df["slot_oil_revenue"] + df["slot_gas_revenue"] + df["slot_ngl_revenue"]

    df["slot_loe"] = df["total_loe"] * net_wells
    df["slot_tax"] = df["tax"] * net_wells
    df["slot_capex"] = df["capex"] * net_wells

    df["slot_operating_profit"] = (
        df["slot_total_revenue"] + df["slot_loe"] + df["slot_tax"]
    )

    df["slot_pud_cash_flow"] = df["slot_operating_profit"] + df["slot_capex"]

    df["slot_asset_purchase"] = 0.0
    df["slot_promote"] = 0.0

    df["slot_total_cash_flow"] = (
        df["slot_pud_cash_flow"] + df["slot_asset_purchase"] + df["slot_promote"]
    )

    df["working_interest"] = float(slot["working_interest"])
    df["net_wells"] = float(slot["net_wells_calc"])
    df["gross_wells"] = float(slot["gross_wells"])
    df["acquisition_cost"] = float(slot["acquisition_cost"])
    df["bid_price_final"] = float(slot["bid_price_final"])
    df["ngl_recovery_case"] = slot_ngl["recovery_case"]
    df["slot_shrink"] = float(slot_ngl["shrink"])
    df["slot_ngl_pct_of_wti"] = float(slot_ngl["ngl_pct_of_wti"])

    return df


# -----------------------------
# Financial calendar alignment
# -----------------------------
def align_to_financial_calendar(slot_df, effective_date, months=360):
    effective_date = pd.to_datetime(effective_date)

    calendar = pd.DataFrame(
        {"date": pd.date_range(start=effective_date, periods=months, freq="MS")}
    )

    df = calendar.merge(slot_df, on="date", how="left")

    numeric_cols = [
        col for col in df.select_dtypes(include=[np.number]).columns if col != "slot_id"
    ]
    df[numeric_cols] = df[numeric_cols].fillna(0)

    object_cols = df.select_dtypes(include=["object"]).columns
    for col in object_cols:
        if col == "tc_name":
            df[col] = df[col].fillna(
                slot_df["tc_name"].iloc[0] if "tc_name" in slot_df.columns else ""
            )
        elif col == "ngl_recovery_case":
            df[col] = df[col].fillna(
                slot_df["ngl_recovery_case"].iloc[0]
                if "ngl_recovery_case" in slot_df.columns
                else ""
            )

    if "slot_id" in slot_df.columns:
        df["slot_id"] = slot_df["slot_id"].iloc[0]

    return df


# -----------------------------
# Deal build / rollup
# -----------------------------
def build_all_slot_financials(
    slot_inputs, deal_settings, type_curve_library, global_assumptions
):
    slot_results = []
    total_net_acres = pd.to_numeric(
        slot_inputs["net_acres"], errors="coerce"
    ).fillna(0).sum()

    effective_date = pd.to_datetime(deal_settings["effective_date"])

    for _, slot_row in slot_inputs.iterrows():
        slot_df = build_slot_financials(
            slot=slot_row,
            deal_settings=deal_settings,
            type_curve_library=type_curve_library,
            global_assumptions=global_assumptions,
            total_net_acres=total_net_acres,
        )

        slot_df = align_to_financial_calendar(
            slot_df,
            deal_settings["effective_date"],
            months=360,
        )

        slot_calc = calc_slot_metrics(slot_row, deal_settings, total_net_acres)

        slot_df["slot_asset_purchase"] = 0.0
        mask = (
            (slot_df["date"].dt.year == effective_date.year)
            & (slot_df["date"].dt.month == effective_date.month)
        )
        slot_df.loc[mask, "slot_asset_purchase"] = -float(
            slot_calc["acquisition_cost"]
        )

        if "slot_promote" not in slot_df.columns:
            slot_df["slot_promote"] = 0.0

        slot_df["slot_total_cash_flow"] = (
            slot_df["slot_pud_cash_flow"]
            + slot_df["slot_asset_purchase"]
            + slot_df["slot_promote"]
        )

        slot_results.append(slot_df)

    return pd.concat(slot_results, ignore_index=True)


def roll_up_deal(all_slots_df):
    sum_cols = [
        "slot_gross_oil_production",
        "slot_gross_gas_production",
        "slot_gross_ngl_production",
        "slot_gross_boe",
        "slot_net_oil_production",
        "slot_net_gas_production",
        "slot_net_ngl_production",
        "slot_net_boe",
        "slot_oil_revenue",
        "slot_gas_revenue",
        "slot_ngl_revenue",
        "slot_total_revenue",
        "slot_loe",
        "slot_tax",
        "slot_operating_profit",
        "slot_capex",
        "slot_pud_cash_flow",
        "slot_asset_purchase",
        "slot_promote",
        "slot_total_cash_flow",
    ]

    deal_df = (
        all_slots_df.groupby("date", as_index=False)[sum_cols]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
    )
    return deal_df


# -----------------------------
# Promote + returns
# -----------------------------
def add_promote_test_columns(df, deal_settings):
    df = df.copy()

    if not bool(deal_settings["promote_enabled"]):
        df["cum_positive_pud_cf"] = df["slot_pud_cash_flow"].clip(lower=0).cumsum()
        df["cum_negative_pud_cf"] = (
            df["slot_pud_cash_flow"].where(df["slot_pud_cash_flow"] < 0, 0).cumsum()
        )
        df["cum_negative_asset_purchase"] = (
            df["slot_asset_purchase"].where(df["slot_asset_purchase"] < 0, 0).cumsum()
        )
        df["running_moic_for_promote"] = 0.0
        df["running_irr_for_promote"] = 0.0
        df["running_moic_for_promote_lag"] = 0.0
        df["running_irr_for_promote_lag"] = 0.0
        df["promote_triggered"] = False
        df["slot_promote"] = 0.0
        df["slot_total_cash_flow"] = (
            df["slot_pud_cash_flow"] + df["slot_asset_purchase"] + df["slot_promote"]
        )
        return df

    df["cum_positive_pud_cf"] = df["slot_pud_cash_flow"].clip(lower=0).cumsum()

    df["cum_negative_pud_cf"] = (
        df["slot_pud_cash_flow"].where(df["slot_pud_cash_flow"] < 0, 0).cumsum()
    )

    df["cum_negative_asset_purchase"] = (
        df["slot_asset_purchase"].where(df["slot_asset_purchase"] < 0, 0).cumsum()
    )

    invested_base = -(df["cum_negative_pud_cf"] + df["cum_negative_asset_purchase"])
    df["running_moic_for_promote"] = np.where(
        invested_base > 0,
        df["cum_positive_pud_cf"] / invested_base,
        0.0,
    )

    running_irrs = []
    for i in range(len(df)):
        temp_cf = df.loc[:i, "slot_pud_cash_flow"] + df.loc[:i, "slot_asset_purchase"]
        temp_dates = df.loc[:i, "date"]
        try:
            if pyxirr is None:
                running_irrs.append(0.0)
            else:
                running_irrs.append(float(pyxirr.xirr(temp_dates, temp_cf)))
        except Exception:
            running_irrs.append(0.0)

    df["running_irr_for_promote"] = running_irrs
    df["running_moic_for_promote_lag"] = (
        df["running_moic_for_promote"].shift(1).fillna(0.0)
    )
    df["running_irr_for_promote_lag"] = (
        df["running_irr_for_promote"].shift(1).fillna(0.0)
    )

    df["promote_triggered"] = (
        (df["running_moic_for_promote_lag"] >= float(deal_settings["promote_multiple"]))
        & (
            df["running_irr_for_promote_lag"]
            >= float(deal_settings["promote_irr_threshold"])
        )
    )

    df["slot_promote"] = np.where(
        df["promote_triggered"],
        -(df["slot_pud_cash_flow"] * float(deal_settings["promote_rate"])),
        0.0,
    )

    df["slot_total_cash_flow"] = (
        df["slot_pud_cash_flow"] + df["slot_asset_purchase"] + df["slot_promote"]
    )

    return df


def calc_financial_irr(df):
    if pyxirr is None:
        return None
    try:
        return float(pyxirr.xirr(df["date"], df["slot_total_cash_flow"]))
    except Exception:
        return None


def calc_financial_moic(df):
    invested = -df.loc[df["slot_total_cash_flow"] < 0, "slot_total_cash_flow"].sum()
    returned = df.loc[df["slot_total_cash_flow"] > 0, "slot_total_cash_flow"].sum()

    if invested == 0:
        return None

    return float(returned / invested)


# -----------------------------
# Input prep
# -----------------------------
def prepare_deal_settings(deal_inputs):
    effective_date = pd.to_datetime(
        deal_inputs.get("effective_date", default_effective_date())
    )

    return {
        "effective_date": effective_date,
        "use_bid_override": bool(deal_inputs.get("use_bid_override", False)),
        "bid_override": float(deal_inputs.get("bid_override", 0.0)),
        "use_acquisition_override": bool(
            deal_inputs.get("use_acquisition_override", False)
        ),
        "acquisition_cost_override": float(
            deal_inputs.get("acquisition_cost_override", 0.0)
        ),
        "promote_enabled": bool(deal_inputs.get("promote_enabled", False)),
        "promote_rate": (
            float(deal_inputs.get("promote_rate", 0.0))
            if deal_inputs.get("promote_enabled", False)
            else 0.0
        ),
        "promote_multiple": (
            float(deal_inputs.get("promote_multiple", 0.0))
            if deal_inputs.get("promote_enabled", False)
            else 0.0
        ),
        "promote_irr_threshold": (
            float(deal_inputs.get("promote_irr_threshold", 0.0))
            if deal_inputs.get("promote_enabled", False)
            else 0.0
        ),
    }


def prepare_global_assumptions(deal_inputs):
    return {
        "oil_price": float(deal_inputs["oil_price"]),
        "gas_price": float(deal_inputs["gas_price"]),
        "oil_sev_tax": float(deal_inputs["oil_sev_tax"]),
        "gas_sev_tax": float(deal_inputs["gas_sev_tax"]),
        "ad_val_tax": float(deal_inputs["ad_val_tax"]),
        "ethane_rec": 1 if bool(deal_inputs["ethane_rec"]) else 0,
        "content_percentages": {
            "ethane": float(deal_inputs["content_ethane"]),
            "propane": float(deal_inputs["content_propane"]),
            "isobutane": float(deal_inputs["content_isobutane"]),
            "butane": float(deal_inputs["content_butane"]),
            "pentanes": float(deal_inputs["content_pentanes"]),
        },
        "recover_ethane_percentages": {
            "ethane": float(deal_inputs["rec_ethane"]),
            "propane": float(deal_inputs["rec_propane"]),
            "isobutane": float(deal_inputs["rec_isobutane"]),
            "butane": float(deal_inputs["rec_butane"]),
            "pentanes": float(deal_inputs["rec_pentanes"]),
        },
        "reject_ethane_percentages": {
            "ethane": float(deal_inputs["rej_ethane"]),
            "propane": float(deal_inputs["rej_propane"]),
            "isobutane": float(deal_inputs["rej_isobutane"]),
            "butane": float(deal_inputs["rej_butane"]),
            "pentanes": float(deal_inputs["rej_pentanes"]),
        },
        "ngl_prices": {
            "ethane": float(deal_inputs["price_ethane"]),
            "propane": float(deal_inputs["price_propane"]),
            "isobutane": float(deal_inputs["price_isobutane"]),
            "butane": float(deal_inputs["price_butane"]),
            "pentanes": float(deal_inputs["price_pentanes"]),
        },
        "ngl_shrink_factors": {
            "ethane": float(deal_inputs["shrink_ethane"]),
            "propane": float(deal_inputs["shrink_propane"]),
            "isobutane": float(deal_inputs["shrink_isobutane"]),
            "butane": float(deal_inputs["shrink_butane"]),
            "pentanes": float(deal_inputs["shrink_pentanes"]),
        },
    }


def prepare_slot_inputs(slot_df, deal_inputs):
    df = slot_df.copy()

    required_defaults = {
        "slot_id": 0,
        "use_calc_unit_acres": False,
        "flowback_delay": 4,
        "tc_risk": 1.0,
        "oil_diff": 0.0,
        "gas_diff": 0.0,
        "ngl_diff": 0.0,
        "oil_opex_bbl": 0.0,
        "gas_opex_mcf": 0.0,
        "ngl_opex": 0.0,
        "fixed_loe": 0.0,
        "ngl_yield": 0.0,
    }

    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].fillna(default)

    if "drilling_spud_month" in df.columns:
        df["drilling_spud_month"] = pd.to_datetime(df["drilling_spud_month"])
    else:
        df["drilling_spud_month"] = pd.Timestamp(default_effective_date())

    if bool(deal_inputs.get("use_dc_override", False)):
        df["dc_costs"] = float(deal_inputs.get("dc_override", 0.0))
    else:
        df["dc_costs"] = df["dc_costs"].astype(float)

    if bool(deal_inputs.get("use_bid_override", False)):
        df["bid_per_acre"] = float(deal_inputs.get("bid_override", 0.0))
    else:
        df["bid_per_acre"] = df["bid_per_acre"].astype(float)

    numeric_cols = [
        "slot_id",
        "lateral_length",
        "gross_wells",
        "net_acres",
        "unit_acres",
        "pct_unitized",
        "flowback_delay",
        "net_revenue_interest",
        "dc_costs",
        "tc_risk",
        "bid_per_acre",
        "oil_diff",
        "gas_diff",
        "ngl_diff",
        "oil_opex_bbl",
        "gas_opex_mcf",
        "ngl_opex",
        "fixed_loe",
        "ngl_yield",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["use_calc_unit_acres"] = df["use_calc_unit_acres"].astype(bool)
    df["tc_name"] = df["tc_name"].astype(str)

    return df


def build_slot_audit_view(all_slots_df):
    df = all_slots_df.copy().sort_values(["slot_id", "date"]).reset_index(drop=True)

    df["month_label"] = df["date"].dt.strftime("%Y-%m")
    df["cum_slot_total_cf"] = df.groupby("slot_id")["slot_total_cash_flow"].cumsum()

    audit_cols = [
        "slot_id",
        "tc_name",
        "date",
        "month_label",
        "period",
        "gross_wells",
        "net_wells",
        "working_interest",
        "bid_price_final",
        "acquisition_cost",
        "slot_shrink",
        "slot_ngl_pct_of_wti",
        "slot_gross_oil_production",
        "slot_gross_gas_production",
        "slot_gross_ngl_production",
        "slot_gross_boe",
        "slot_net_oil_production",
        "slot_net_gas_production",
        "slot_net_ngl_production",
        "slot_net_boe",
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
        "cum_slot_total_cf",
    ]

    existing_cols = [c for c in audit_cols if c in df.columns]
    return df[existing_cols]


def build_deal_audit_view(deal_df):
    df = deal_df.copy().sort_values("date").reset_index(drop=True)

    df["month_num"] = np.arange(1, len(df) + 1)
    df["month_label"] = df["date"].dt.strftime("%Y-%m")
    df["cum_total_cf"] = df["slot_total_cash_flow"].cumsum()

    audit_cols = [
        "date",
        "month_label",
        "month_num",
        "slot_gross_oil_production",
        "slot_gross_gas_production",
        "slot_gross_ngl_production",
        "slot_gross_boe",
        "slot_net_oil_production",
        "slot_net_gas_production",
        "slot_net_ngl_production",
        "slot_net_boe",
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

    existing_cols = [c for c in audit_cols if c in df.columns]
    return df[existing_cols]


# -----------------------------
# Main entrypoint
# -----------------------------
def run_deal_model(slot_df, deal_inputs, type_curve_file="type_curve_library.xlsx"):
    type_curve_library = load_type_curve_library(type_curve_file)
    slot_inputs = prepare_slot_inputs(slot_df, deal_inputs)
    deal_settings = prepare_deal_settings(deal_inputs)
    global_assumptions = prepare_global_assumptions(deal_inputs)

    all_slots_df = build_all_slot_financials(
        slot_inputs=slot_inputs,
        deal_settings=deal_settings,
        type_curve_library=type_curve_library,
        global_assumptions=global_assumptions,
    )

    deal_df = roll_up_deal(all_slots_df)
    deal_df = add_promote_test_columns(deal_df, deal_settings)

    slot_audit_df = build_slot_audit_view(all_slots_df)
    deal_audit_df = build_deal_audit_view(deal_df)

    irr = calc_financial_irr(deal_df)
    moic = calc_financial_moic(deal_df)

    return all_slots_df, deal_df, slot_audit_df, deal_audit_df, irr, moic
