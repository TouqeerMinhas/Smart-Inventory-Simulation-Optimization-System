# Smart Inventory Simulation & Optimization System

A runnable Python + Streamlit academic inventory simulation project with a modular simulation engine, dashboard, editable product setup, analytics, scenario comparison, policy grid search, and downloadable reports. All products and results included here are synthetic examples.

## Interface update

Muted Champagne + Dusty Rose: champagne background (#F8F5F1), pearl cards (#FFFCF8), dusty rose actions (#A55E57), charcoal text (#302B29), warm gold accents (#C9A47E), and an editorial dark sidebar. Chart colors and backgrounds are explicit, so they remain readable regardless of Streamlit's chart theme. Manrope / Inter use local sans-serif fallbacks when web fonts are unavailable.

When updating an existing installation, copy the new project files over the old ones, including **`reporting.py`**, `app.py`, `style.css`, and `.streamlit/config.toml`, then fully stop and restart Streamlit **from this project folder**. Keep `.venv` as it is. Launching from the project folder ensures Streamlit loads the included theme configuration.

## Day-wise report update

Reports now start with **Simulation day**, with exactly one row per simulated day from run 1. Demand, sales, stock and order counts are whole numbers. Fill rates show percentages, and monetary values show two decimal places in PKR. Each day's revenue and ordering cost belong to that day, not an average over simulation runs. Average closing stock to date is a cumulative average, displayed and exported as the nearest whole unit (.5 rounds up). Internal calculations retain full precision.

The default ZIP contains `daily_simulation_report.csv`, `simulation_summary.csv`, `configuration.json`, and `READ_ME.txt`. The summary matches the same daily path. Optional advanced per-run totals and confidence intervals are available through an unchecked-by-default checkbox. The dashboard and optimization still use independent simulation runs for statistical averages. These averages can differ from the single run in the daily report.

Mean demand is **units per day**. For example, 2 units/day over 30 days gives an expected total of 60 units, with actual totals varying randomly. The old run-level `demand` field was a total over all days; it was not daily demand. The model and its random demand process have not been artificially capped or rounded to change results.

## Run locally (Windows / VS Code)

Install Python 3.10 or newer. Extract the ZIP, open the `smart_inventory` folder in VS Code, and run:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Open the local address printed in the terminal (usually http://localhost:8501).

On macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

## Workflow

1. Open Inventory setup. Load a sample product, upload a CSV matching `data/sample_products.csv`, or edit the product parameters. Save the product.
2. Apply simulation days, replication count, and seed in the sidebar. Defaults: 90 days, 100 replications, seed 42.
3. Inspect aggregate metrics in Dashboard, one daily trajectory in Simulation, and confidence intervals in Analytics.
4. Compare increased demand and supplier delays in Scenarios.
5. Search reorder point/order quantity combinations in Optimization. The service target is a mean unit fill rate, not a probability guarantee. At most 100 candidate combinations are permitted.
6. In Reports, inspect day-wise demand, stock and financials. Download the daily CSV or report ZIP. Enable the advanced checkbox only when per-run totals and confidence intervals are needed.

## Algorithm

Each replication gets an independent NumPy child random stream. Each day:

1. Receive all replenishment orders due at the start of the day.
2. Draw independent Poisson demand with the configured mean.
3. Sell the minimum of available stock and demand; unmet units become lost sales.
4. Charge holding cost on closing stock and a penalty on lost units.
5. Compute inventory position: closing stock + all outstanding orders.
6. If position is at or below `s`, place one order of quantity `Q`, arriving on day `current_day + lead_time` and charge the fixed order fee.

Lead time is at least one day. Several outstanding orders are supported. At most one order is placed per day, so extremely small Q may be unable to sustain demand. There is no warm-up period or terminal salvage value.

## Metrics and economics

- Fill rate: units sold / total demand per replication; 1.0 if demand is zero. The dashboard shows the arithmetic mean of replication fill rates.
- Stockout days: days on which some demand went unfulfilled.
- Policy cost: holding + order fees + lost-sale penalties.
- Modeled profit: revenue − cost of goods sold − policy cost. COGS is charged on units sold; this metric is not cash flow. Initial and ending inventory values and outstanding purchase commitments are not charged as cash expenditures.
- Mean 95% confidence intervals use `mean ± 1.96 * sample_std / sqrt(replications)`. These are approximate normal intervals for expected metrics, not prediction intervals. They can extend outside feasible bounds for bounded metrics. More replications improve precision; normal approximations may be poor for small samples or skewed outputs.
- Grid search uses identical demand streams for each candidate. It selects the lowest mean policy cost among candidates reaching the mean fill-rate target. If none qualify, the UI says so. This is a finite candidate search, not a globally optimal solution or a certified service guarantee; check the selected policy with additional seeds.

## Project structure

```text
smart_inventory/
  app.py                    Streamlit navigation, controls, charts, exports
  simulation/engine.py      Config validation, simulation, CIs, optimization
  data/sample_products.csv  Synthetic example catalog
  tests/                    Engine invariants and Streamlit interaction checks
  requirements.txt
  README.md
```

## Test

```powershell
.venv\Scripts\python -m pytest -q
```

Tests cover reproducibility, demand/stock conservation, lead-time arrival convention, pipeline-aware reordering, lost sales, cost arithmetic, input rejection, optimization agreement, and all seven UI pages.

## Scope of this first version

Single-product analysis, constant Poisson demand, deterministic lead time, lost sales, unlimited supplier capacity, no expiry, session-based settings. No login, database, actual supplier integration, or live stock synchronization is included. Download reports to retain runs. Presentation slides and a formal project report can be developed from the validated implementation.
