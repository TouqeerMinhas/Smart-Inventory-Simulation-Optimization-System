"""Day-wise, single-run reports. Simulation averages stay separate."""
from dataclasses import asdict
from io import BytesIO
from math import floor
import json
import zipfile

import pandas as pd


LABELS = {
    'simulation_day': 'Simulation day', 'demand': 'Daily demand (units)',
    'sales': 'Units sold', 'lost_sales': 'Unfulfilled demand (units)',
    'opening_stock': 'Available before sales (units)', 'arrivals': 'Delivery received (units)',
    'closing_stock': 'Closing stock (units)', 'average_stock': 'Average closing stock to date (units)',
    'fill_rate': 'Daily fill rate', 'ordered': 'Units ordered', 'orders_placed': 'Orders placed',
    'on_order': 'Outstanding orders (units)', 'inventory_position': 'Inventory position (units)',
    'revenue': 'Daily revenue (PKR)', 'cogs': 'Cost of units sold (PKR)',
    'holding_cost': 'Daily holding cost (PKR)', 'ordering_cost': 'Daily ordering cost (PKR)',
    'shortage_cost': 'Daily shortage penalty (PKR)', 'policy_cost': 'Daily policy cost (PKR)',
    'profit': 'Daily modeled profit (PKR)',
}
MONEY = ['revenue', 'cogs', 'holding_cost', 'ordering_cost', 'shortage_cost', 'policy_cost', 'profit']


def whole_stock(value):
    """Round nonnegative stock averages to the nearest unit, with .5 rounding up."""
    return int(floor(float(value) + 0.5))


def daily_report(path, config):
    """One row per actual day in run 1, with integer counts and unrounded arithmetic."""
    daily = path.rename(columns={'day': 'simulation_day'}).copy()
    daily['orders_placed'] = (daily.ordered > 0).astype(int)
    daily['average_stock'] = daily.closing_stock.expanding().mean()
    daily['fill_rate'] = daily.sales.div(daily.demand.where(daily.demand > 0)).fillna(1.0)
    daily['revenue'] = daily.sales * config.selling_price
    daily['cogs'] = daily.sales * config.unit_cost
    daily['holding_cost'] = daily.closing_stock * config.holding_cost
    daily['ordering_cost'] = daily.orders_placed * config.order_cost
    daily['shortage_cost'] = daily.lost_sales * config.shortage_cost
    daily['policy_cost'] = daily.holding_cost + daily.ordering_cost + daily.shortage_cost
    daily['profit'] = daily.revenue - daily.cogs - daily.policy_cost
    return daily[list(LABELS)]


def daily_display(daily):
    """Friendly export/display only: calculations above retain full precision."""
    frame = daily.copy()
    frame['fill_rate'] = frame.fill_rate.map(lambda v: f'{v:.2%}')
    frame['average_stock'] = frame.average_stock.map(whole_stock).astype(int)
    frame[MONEY] = frame[MONEY].round(2)
    return frame.rename(columns=LABELS)


def run_summary(daily, config):
    demand = int(daily.demand.sum())
    sales = int(daily.sales.sum())
    values = {
        'Simulation days': len(daily),
        'Initial stock (units)': config.initial_stock,
        'Configured mean demand (units/day)': config.daily_demand,
        'Expected total demand over simulation (units)': config.daily_demand * len(daily),
        'Actual total demand over simulation (units)': demand,
        'Actual average demand (units/day)': round(demand / len(daily), 2),
        'Total units sold': sales,
        'Total unfulfilled demand (units)': int(daily.lost_sales.sum()),
        'Overall fill rate': f'{sales / demand if demand else 1.0:.2%}',
        'Average closing stock across simulation (units)': whole_stock(daily.closing_stock.mean()),
        'Orders placed (count)': int(daily.orders_placed.sum()),
        'Ending stock (units)': int(daily.closing_stock.iloc[-1]),
        'Outstanding orders at end (units)': int(daily.on_order.iloc[-1]),
    }
    for key in MONEY:
        label = 'Total ' + LABELS[key].replace('Daily ', '').replace('Cost of', 'cost of')
        values[label] = round(float(daily[key].sum()), 2)
    return pd.DataFrame([values])


def readable_averages(frame):
    """Label the meaning of fractional means without rounding them to fake counts."""
    view = frame.copy()
    names = {
        'scenario': 'Scenario', 'reorder_point': 'Reorder point (units)',
        'order_quantity': 'Order quantity (units)', 'meets_target': 'Meets target',
        'fill_rate': 'Mean fill rate', 'profit': 'Mean modeled profit (PKR)',
        'policy_cost': 'Mean policy cost (PKR)', 'lost_sales': 'Mean unfulfilled units per run',
        'demand': 'Mean total demand per run (units)',
    }
    for key in view:
        if key == 'fill_rate':
            view[key] = view[key].map(lambda v: f'{v:.2%}')
        elif key in MONEY or key in ('lost_sales', 'demand'):
            view[key] = view[key].map(lambda v: f'{v:,.2f}')
        elif key == 'meets_target':
            view[key] = view[key].map({True: 'Yes', False: 'No'})
    return view.rename(columns=names)


def report_bundle(daily, config, product, results=None, confidence=None):
    buffer = BytesIO()
    metadata = dict(product=product, config=asdict(config), report_basis='Daily results from simulation run 1; not averages across runs',
                    model='Poisson daily unit demand; lost sales; fixed lead time; daily (s,Q) policy',
                    cost_basis='COGS on units sold; closing-stock holding cost; order fee at placement; no terminal stock valuation')
    explanation = f'''DAY-WISE INVENTORY REPORT
Product: {product}
Simulation days: {len(daily)}. Each row is one day of simulation run 1.
Daily counts are whole units. Money is PKR with two decimal places.
Daily fill rate = units sold / daily demand. Zero demand is shown as 100% by convention.
Average closing stock to date = mean of closing stock from day 1 through that row's day.
Stock averages are rounded to the nearest whole unit for display and export (.5 rounds up).
Internal stock averages retain full precision for simulation calculations and costs.
Configured mean demand: {config.daily_demand:g} units/day.
Expected demand over {len(daily)} days: {config.daily_demand * len(daily):g} units.
Actual demand is random and can differ from this expectation.
Daily revenue = units sold * selling price.
Daily holding cost = closing stock * holding cost per unit per day.
Daily ordering cost = orders placed that day * fixed order fee (not a mean fee).
Policy cost = holding + ordering + shortage penalty.
Modeled profit = revenue - cost of units sold - policy cost. This is not cash flow.
The run summary describes this same daily path. Dashboard/optimization means describe {config.replications} separate runs.
Optional advanced files contain explicitly labelled per-run totals and confidence intervals.
'''
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('daily_simulation_report.csv', daily_display(daily).to_csv(index=False, float_format='%.2f').encode('utf-8-sig'))
        archive.writestr('simulation_summary.csv', run_summary(daily, config).to_csv(index=False, float_format='%.2f').encode('utf-8-sig'))
        archive.writestr('configuration.json', json.dumps(metadata, indent=2))
        archive.writestr('READ_ME.txt', explanation)
        if results is not None:
            advanced = results.rename(columns={'replication': 'Simulation run', 'demand': 'Total demand over all simulation days (units)'})
            advanced['average_stock'] = advanced.average_stock.map(whole_stock).astype(int)
            advanced['fill_rate'] = advanced.fill_rate.map(lambda v: f'{v:.2%}')
            archive.writestr('advanced/per_run_totals.csv', advanced.to_csv(index=False, float_format='%.2f').encode('utf-8-sig'))
        if confidence is not None:
            advanced = confidence.copy()
            advanced.loc['fill_rate'] *= 100
            advanced = advanced.astype(object)
            advanced.loc['average_stock'] = advanced.loc['average_stock'].map(whole_stock).map(str)
            advanced = advanced.rename(index={'fill_rate': 'Fill rate (percentage points)'})
            archive.writestr('advanced/confidence_intervals.csv', advanced.to_csv(float_format='%.2f').encode('utf-8-sig'))
    return buffer.getvalue()
