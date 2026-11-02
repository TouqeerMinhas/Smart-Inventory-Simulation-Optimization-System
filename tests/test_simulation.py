from dataclasses import replace
import pandas as pd
import pytest
from simulation import Config, run, intervals, optimize


def test_reproducible_and_conservation():
    config = Config(days=20, replications=10)
    result, path = run(config)
    again, again_path = run(config)
    pd.testing.assert_frame_equal(result, again)
    pd.testing.assert_frame_equal(path, again_path)
    assert (result.sales + result.lost_sales == result.demand).all()
    assert (path.closing_stock >= 0).all()
    assert (path.opening_stock - path.sales == path.closing_stock).all()
    assert config.initial_stock + path.arrivals.sum() - path.sales.sum() == path.closing_stock.iloc[-1]
    assert path.ordered.sum() == path.arrivals.sum() + path.on_order.iloc[-1]
    assert (path.inventory_position == path.closing_stock + path.on_order).all()
    for row in result.itertuples():
        assert row.profit == row.revenue-row.cogs-row.holding_cost-row.ordering_cost-row.shortage_cost


def test_arrival_timing_and_no_duplicate_order_on_pipeline():
    config = Config(initial_stock=0, daily_demand=0, reorder_point=0, order_quantity=10, lead_time=3, days=5, replications=2)
    result, path = run(config)
    assert path.ordered.tolist() == [10, 0, 0, 0, 0]
    assert path.arrivals.tolist() == [0, 0, 0, 10, 0]
    assert path.closing_stock.tolist() == [0, 0, 0, 10, 10]
    assert (result.fill_rate == 1).all()
    assert (result.holding_cost == 40).all()


def test_all_demand_lost_before_delivery():
    result, path = run(Config(initial_stock=0, daily_demand=20, lead_time=10, days=3, replications=3))
    assert (result.sales == 0).all()
    assert (result.lost_sales == result.demand).all()
    assert (path.arrivals == 0).all()


def test_intervals_and_optimizer_match_direct_run():
    config = Config(days=10, replications=5)
    result,_ = run(config)
    ci = intervals(result)
    assert ci.loc['profit','lower_95'] <= result.profit.mean() <= ci.loc['profit','upper_95']
    ranking = optimize(config, [30,60], [60,120], 0.9)
    assert len(ranking) == 4
    for row in ranking.itertuples():
        direct,_ = run(replace(config,reorder_point=row.reorder_point,order_quantity=row.order_quantity))
        assert row.policy_cost == direct.policy_cost.mean()
        assert row.fill_rate == direct.fill_rate.mean()


@pytest.mark.parametrize('change', [dict(lead_time=0),dict(order_quantity=0),dict(daily_demand=-1),dict(seed=-1),dict(replications=1),dict(initial_stock=1.5),dict(unit_cost=float('nan'))])
def test_invalid_inputs(change):
    with pytest.raises(ValueError):
        run(replace(Config(),**change))
