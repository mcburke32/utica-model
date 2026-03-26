def run_deal_model(deal_inputs):
    oil_price = deal_inputs["oil_price"]
    gas_price = deal_inputs["gas_price"]
    gross_wells = deal_inputs["gross_wells"]
    net_acres = deal_inputs["net_acres"]
    bid_per_acre = deal_inputs["bid_per_acre"]
    lateral_length = deal_inputs["lateral_length"]
    dc_cost_per_ft = deal_inputs["dc_cost_per_ft"]

    revenue_per_well = (oil_price * 1000 + gas_price * 5000) * (lateral_length / 10000)
    total_revenue = revenue_per_well * gross_wells
    acquisition_cost = net_acres * bid_per_acre
    gross_capex = gross_wells * lateral_length * dc_cost_per_ft

    return {
        "revenue_per_well": revenue_per_well,
        "total_revenue": total_revenue,
        "acquisition_cost": acquisition_cost,
        "gross_capex": gross_capex,
    }
