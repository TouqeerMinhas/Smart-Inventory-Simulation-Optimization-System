from io import BytesIO
import zipfile

import pandas as pd
import pytest

from simulation import Config, run
from reporting import daily_report, daily_display, run_summary, report_bundle, whole_stock, MONEY


@pytest.mark.parametrize('changes', [
    {},
    dict(initial_stock=0, daily_demand=20, lead_time=10),
    dict(daily_demand=0, initial_stock=0, reorder_point=0),
    dict(selling_price=1499.75, unit_cost=459.25, holding_cost=2.35),
])
def test_daily_finances_reconcile_to_same_simulation_run(changes):
    config = Config(days=12, replications=4, **changes)
    results, path = run(config)
    daily = daily_report(path, config)
    original = results.iloc[0]
    assert daily.simulation_day.tolist() == list(range(1, config.days + 1))
    for key in ['demand', 'sales', 'lost_sales', 'orders_placed', 'closing_stock']:
        assert pd.api.types.is_integer_dtype(daily[key])
    assert (daily.demand == daily.sales + daily.lost_sales).all()
    assert set(daily.ordering_cost).issubset({0, config.order_cost})
    for key in MONEY + ['demand', 'sales', 'lost_sales']:
        assert daily[key].sum() == pytest.approx(original[key])
    assert daily.average_stock.iloc[-1] == pytest.approx(original.average_stock)
    assert daily.orders_placed.sum() == original.orders
    assert daily.fill_rate.between(0, 1).all()
    if config.daily_demand == 0:
        assert (daily.fill_rate == 1).all()
    summary = run_summary(daily, config).iloc[0]
    assert summary['Simulation days'] == config.days
    assert summary['Actual total demand over simulation (units)'] == original.demand
    assert summary['Total modeled profit (PKR)'] == pytest.approx(round(original.profit, 2))


def test_report_rows_are_days_and_percentages_are_readable():
    config = Config(days=7, replications=5)
    result, path = run(config)
    daily = daily_report(path, config)
    payload = report_bundle(daily, config, 'Keyboard')
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        assert 'replications.csv' not in archive.namelist()
        assert not any(n.startswith('advanced/') for n in archive.namelist())
        exported = pd.read_csv(BytesIO(archive.read('daily_simulation_report.csv')))
        assert len(exported) == config.days
        assert exported.columns[0] == 'Simulation day'
        assert exported['Daily fill rate'].str.endswith('%').all()
        assert pd.api.types.is_integer_dtype(exported['Daily demand (units)'])
        assert exported['Daily revenue (PKR)'].sum() == pytest.approx(result.revenue.iloc[0])
        assert exported['Daily ordering cost (PKR)'].isin([0, config.order_cost]).all()
        assert exported['Average closing stock to date (units)'].iloc[-1] == whole_stock(result.average_stock.iloc[0])
        assert pd.api.types.is_integer_dtype(exported['Average closing stock to date (units)'])
        assert archive.read('daily_simulation_report.csv').startswith(b'\xef\xbb\xbf')
    advanced_payload = report_bundle(daily, config, 'Keyboard', result)
    with zipfile.ZipFile(BytesIO(advanced_payload)) as archive:
        advanced = pd.read_csv(BytesIO(archive.read('advanced/per_run_totals.csv')))
        assert len(advanced) == config.replications
        assert 'Total demand over all simulation days (units)' in advanced


def test_stock_rounding_changes_presentation_only():
    assert whole_stock(27.5) == 28
    assert whole_stock(26.5) == 27
    assert whole_stock(26.49) == 26
    config = Config(days=12, replications=4)
    result, path = run(config)
    daily = daily_report(path, config)
    shown = daily_display(daily)
    assert shown['Average closing stock to date (units)'].tolist() == [whole_stock(v) for v in daily.average_stock]
    assert daily.average_stock.iloc[-1] == pytest.approx(result.average_stock.iloc[0])
    assert daily.holding_cost.sum() == pytest.approx(result.holding_cost.iloc[0])

