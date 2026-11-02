"""Discrete-time, lost-sales (s,Q) inventory Monte Carlo simulation."""
from dataclasses import dataclass, asdict, replace
from math import isfinite
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Config:
    initial_stock: int = 120
    daily_demand: float = 15.0
    reorder_point: int = 60
    order_quantity: int = 120
    lead_time: int = 3
    selling_price: float = 1000.0
    unit_cost: float = 600.0
    holding_cost: float = 2.0
    order_cost: float = 500.0
    shortage_cost: float = 100.0
    days: int = 90
    replications: int = 100
    seed: int = 42

    def validate(self):
        integers = ('initial_stock', 'reorder_point', 'order_quantity', 'lead_time', 'days', 'replications', 'seed')
        for key, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
                raise ValueError(f'{key} must be a finite nonnegative number.')
            if key in integers and not isinstance(value, int):
                raise ValueError(f'{key} must be an integer.')
        for key in ('order_quantity', 'lead_time', 'days', 'replications'):
            if getattr(self, key) < 1:
                raise ValueError(f'{key} must be at least 1.')
        if self.replications < 2:
            raise ValueError('Use at least 2 replications for confidence intervals.')


def run(config: Config):
    """Receive due orders, fulfill demand, charge costs, then review inventory position.

    Orders placed at end of day d arrive before demand on d + lead_time.
    At most one fixed-Q order is placed per day when inventory position <= s.
    Demand streams depend only on seed, horizon and replication, allowing paired
    policy comparisons. Lost demand never carries forward.
    """
    config.validate()
    seeds = np.random.SeedSequence(config.seed).spawn(config.replications)
    summaries, first_path = [], []
    for replication, seed in enumerate(seeds):
        demands = np.random.default_rng(seed).poisson(config.daily_demand, config.days)
        stock, pipeline = config.initial_stock, []
        sales_total = lost_total = order_count = stock_sum = stockout_days = 0
        for day, demand in enumerate(demands, start=1):
            arrivals = sum(q for due, q in pipeline if due == day)
            pipeline = [(due, q) for due, q in pipeline if due > day]
            stock += arrivals
            opening = stock
            sales = min(stock, int(demand))
            lost = int(demand) - sales
            stock -= sales
            sales_total += sales
            lost_total += lost
            stockout_days += int(lost > 0)
            stock_sum += stock
            position = stock + sum(q for _, q in pipeline)
            ordered = 0
            if position <= config.reorder_point:
                ordered = config.order_quantity
                pipeline.append((day + config.lead_time, ordered))
                order_count += 1
            if replication == 0:
                first_path.append(dict(day=day, opening_stock=opening, demand=int(demand), sales=sales,
                                       lost_sales=lost, closing_stock=stock, arrivals=arrivals,
                                       ordered=ordered, on_order=sum(q for _, q in pipeline),
                                       inventory_position=stock + sum(q for _, q in pipeline)))
        demand_total = sales_total + lost_total
        holding = stock_sum * config.holding_cost
        ordering = order_count * config.order_cost
        shortage = lost_total * config.shortage_cost
        cogs = sales_total * config.unit_cost
        revenue = sales_total * config.selling_price
        summaries.append(dict(replication=replication + 1, demand=demand_total, sales=sales_total,
                              lost_sales=lost_total, fill_rate=sales_total / demand_total if demand_total else 1.0,
                              stockout_days=stockout_days, average_stock=stock_sum / config.days,
                              orders=order_count, ending_stock=stock, on_order=sum(q for _, q in pipeline),
                              revenue=revenue, cogs=cogs, holding_cost=holding, ordering_cost=ordering,
                              shortage_cost=shortage, policy_cost=holding + ordering + shortage,
                              profit=revenue - cogs - holding - ordering - shortage))
    return pd.DataFrame(summaries), pd.DataFrame(first_path)


def intervals(results: pd.DataFrame):
    """Approximate 95% normal CIs for means across independent replications."""
    columns = ['profit', 'policy_cost', 'fill_rate', 'lost_sales', 'average_stock', 'orders', 'stockout_days']
    means = results[columns].mean()
    half = 1.96 * results[columns].std(ddof=1) / np.sqrt(len(results))
    return pd.DataFrame({'mean': means, 'lower_95': means - half, 'upper_95': means + half})


def optimize(config: Config, points, quantities, target=0.95):
    """Grid search with common random numbers; target uses mean unit fill rate."""
    rows = []
    for point in sorted(set(points)):
        for quantity in sorted(set(quantities)):
            result, _ = run(replace(config, reorder_point=int(point), order_quantity=int(quantity)))
            rows.append(dict(reorder_point=point, order_quantity=quantity,
                             policy_cost=result.policy_cost.mean(), fill_rate=result.fill_rate.mean(),
                             profit=result.profit.mean()))
    table = pd.DataFrame(rows)
    if table.empty:
        raise ValueError('Supply at least one reorder point and quantity.')
    table['meets_target'] = table.fill_rate >= target
    return table.sort_values(['meets_target', 'policy_cost'], ascending=[False, True]).reset_index(drop=True)
