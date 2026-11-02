from dataclasses import asdict, replace
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from simulation import Config, run, intervals, optimize
from reporting import daily_report, daily_display, run_summary, readable_averages, report_bundle, whole_stock, MONEY, LABELS

st.set_page_config(page_title='Smart Inventory | Simulation Lab', page_icon='📦', layout='wide')
st.markdown(f"<style>{(Path(__file__).parent / 'style.css').read_text()}</style>", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def simulate(config):
    return run(config)


def show_daily(daily):
    formats = {LABELS[key]: st.column_config.NumberColumn(format='PKR %.2f') for key in MONEY}
    formats[LABELS['average_stock']] = st.column_config.NumberColumn(format='%d')
    for key in ('simulation_day', 'demand', 'sales', 'lost_sales', 'opening_stock', 'arrivals',
                'closing_stock', 'ordered', 'orders_placed', 'on_order', 'inventory_position'):
        formats[LABELS[key]] = st.column_config.NumberColumn(format='%d')
    st.dataframe(daily_display(daily), column_config=formats, hide_index=True, use_container_width=True)


PALETTE = ['#A55E57', '#C9A47E', '#76534F', '#D7AAA0', '#726B67']


def chart(fig):
    fig.update_layout(
        template='plotly_white', paper_bgcolor='#FFFCF8', plot_bgcolor='#FFFCF8',
        font=dict(family='Inter, sans-serif', color='#302B29', size=12),
        colorway=PALETTE, height=365,
        title=dict(font=dict(family='Manrope, sans-serif', size=16, color='#302B29'), x=.02),
        margin=dict(t=58, b=40, l=25, r=25), legend_title_text='',
        legend=dict(orientation='h', y=1.02, x=1, xanchor='right', yanchor='bottom', font=dict(size=11)),
        hoverlabel=dict(bgcolor='#302B29', font_color='#FFFCF8', bordercolor='#76534F'),
    )
    for i, trace in enumerate(fig.data):
        color = PALETTE[i % len(PALETTE)]
        if trace.type == 'scatter':
            trace.update(line=dict(color=color, width=2.5))
        elif trace.type in ('bar', 'histogram'):
            trace.update(marker=dict(color=color))
    fig.update_xaxes(gridcolor='#F1E5DF', zerolinecolor='#E7DDD6', linecolor='#E7DDD6', automargin=True)
    fig.update_yaxes(gridcolor='#E7DDD6', zerolinecolor='#E7DDD6', automargin=True)
    st.plotly_chart(fig, use_container_width=True, theme=None, config={'displaylogo': False})


st.sidebar.title('Inventory Lab')
st.sidebar.caption('Smart Inventory Simulation & Optimization System')
page = st.sidebar.radio('Workspace', ['Dashboard', 'Inventory setup', 'Simulation', 'Analytics', 'Scenarios', 'Optimization', 'Reports'])
st.sidebar.divider()
with st.sidebar.form('run_settings_form'):
    days = st.number_input('Simulation days', min_value=1, max_value=730, value=90)
    reps = st.number_input('Simulation runs for averages', min_value=2, max_value=500, value=100,
                           help='Each run simulates the selected number of days. Reports show daily results from run 1; averages compare separate runs.')
    seed = st.number_input('Random seed', min_value=0, max_value=2147483647, value=42)
    apply = st.form_submit_button('Apply run settings', use_container_width=True)
if 'run_settings' not in st.session_state:
    st.session_state.run_settings = dict(days=90, replications=100, seed=42)
if apply:
    st.session_state.run_settings = dict(days=int(days), replications=int(reps), seed=int(seed))
if 'product' not in st.session_state:
    st.session_state.product = {k:v for k,v in asdict(Config()).items() if k not in ('days', 'replications', 'seed')}
    st.session_state.product_name = 'Wireless Mouse'
config = Config(**st.session_state.product, **st.session_state.run_settings)
config.validate()
st.markdown('''<div class="lab-project-header" role="banner">
<div class="lab-eyebrow">INVENTORY LAB</div>
<h2>Smart Inventory Simulation &amp; Optimization System</h2>
<p>Model demand. Compare policies. Plan replenishment.</p>
</div>''', unsafe_allow_html=True)
st.title(page)
st.caption(f'{st.session_state.product_name} · {config.days} days · {config.replications} replications · Seed {config.seed}')
st.caption(f'Configured demand: {config.daily_demand:g} units/day on average. '
           f'Expected total over {config.days} days: {config.daily_demand * config.days:,.2f} units per run. '
           'Actual daily demand varies randomly around this average.')

if page == 'Inventory setup':
    st.subheader('Define your product and replenishment policy')
    st.write('One product is simulated at a time. Each CSV row can be loaded as a separate product.')
    uploaded = st.file_uploader('Import product catalog (CSV)', type='csv')
    try:
        catalog = pd.read_csv(uploaded) if uploaded else pd.read_csv(Path(__file__).parent / 'data/sample_products.csv')
        required = ['product'] + list(st.session_state.product)
        missing = set(required) - set(catalog.columns)
        if missing:
            raise ValueError('Missing columns: ' + ', '.join(sorted(missing)))
        if catalog.empty or catalog[required].isna().any().any():
            raise ValueError('The catalog must contain complete product rows.')
        selected = st.selectbox('Catalog product', range(len(catalog)), format_func=lambda i: str(catalog.iloc[i]['product']))
        if st.button('Load selected product'):
            candidate = catalog.iloc[selected].to_dict()
            values = {}
            integer_keys = {'initial_stock','reorder_point','order_quantity','lead_time'}
            for key in st.session_state.product:
                raw = float(candidate[key])
                if key in integer_keys and not raw.is_integer():
                    raise ValueError(f'{key} must be a whole number.')
                values[key] = int(raw) if key in integer_keys else raw
            Config(**values, **st.session_state.run_settings).validate()
            st.session_state.product = values
            st.session_state.product_name = str(candidate['product'])
            st.rerun()
    except (ValueError, TypeError, pd.errors.ParserError) as exc:
        st.error(f'Could not load catalog: {exc}')
    with st.form('product_settings'):
        name = st.text_input('Product name', st.session_state.product_name)
        columns = st.columns(3)
        labels = {'initial_stock':'Initial stock (units)', 'daily_demand':'Mean demand (units/day)',
                  'reorder_point':'Reorder point s (units)', 'order_quantity':'Order quantity Q (units)',
                  'lead_time':'Lead time (days)', 'selling_price':'Selling price (PKR/unit)',
                  'unit_cost':'Unit cost (PKR/unit)', 'holding_cost':'Holding cost (PKR/unit/day)',
                  'order_cost':'Fixed cost (PKR/order)', 'shortage_cost':'Lost sale penalty (PKR/unit)'}
        values = {}
        for i, (key, value) in enumerate(st.session_state.product.items()):
            with columns[i % 3]:
                values[key] = st.number_input(labels[key], min_value=1 if key in ('lead_time','order_quantity') else 0 if isinstance(value,int) else 0.0, value=value)
        if st.form_submit_button('Save product', type='primary'):
            try:
                Config(**values, **st.session_state.run_settings).validate()
                st.session_state.product = values
                st.session_state.product_name = name.strip() or 'Untitled product'
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    st.download_button('Download sample CSV', (Path(__file__).parent / 'data/sample_products.csv').read_bytes(), 'sample_products.csv', 'text/csv')
else:
    with st.spinner('Simulating inventory policies…'):
        result, path = simulate(config)
    ci = intervals(result)
    daily = daily_report(path, config)
    if page == 'Dashboard':
        st.markdown('''<div class="lab-hero"><div class="lab-tag">Simulation overview</div>
        <h2>A clearer view of your inventory.</h2><p>Track profit, service levels and replenishment performance.
        Compare policies under uncertain demand, then use the results to plan your next move.</p></div>''', unsafe_allow_html=True)
        cols = st.columns(4)
        cols[0].metric('Modeled profit · PKR', f'{result.profit.mean():,.0f}')
        cols[1].metric('Mean unit fill rate', f'{result.fill_rate.mean():.1%}')
        cols[2].metric('Mean lost units', f'{result.lost_sales.mean():,.1f}')
        cols[3].metric('Policy cost · PKR', f'{result.policy_cost.mean():,.0f}')
        chart(px.line(path, x='day', y=['closing_stock','inventory_position'], labels={'value':'Units','day':'Day'}, title='Inventory trajectory · run 01'))
        a,b = st.columns(2)
        with a:
            st.subheader('Policy snapshot')
            st.write(f'Reorder at inventory position ≤ **{config.reorder_point} units**; order **{config.order_quantity} units** with **{config.lead_time}-day** lead time.')
            st.write(f'Expected demand over lead time: **{config.daily_demand * config.lead_time:,.1f} units**.')
        with b:
            st.subheader('Uncertainty across replications')
            st.write(f'Approximate 95% CI for mean profit: **PKR {ci.loc["profit","lower_95"]:,.0f} to {ci.loc["profit","upper_95"]:,.0f}**.')
            st.caption('Confidence intervals describe uncertainty in the estimated mean, not a range for a future run.')
    elif page == 'Simulation':
        st.subheader('Daily inventory ledger')
        st.info(f'One row per simulation day, from run 1 ({config.days} days). Demand and stock are whole units. '
                'Daily revenue and costs belong to that day; the dashboard shows averages across separate runs.')
        chart(px.bar(path, x='day', y=['sales','lost_sales'], title='Daily fulfilled and lost demand', labels={'value':'Units'}))
        show_daily(daily)
    elif page == 'Analytics':
        a,b = st.columns(2)
        with a:
            chart(px.histogram(result, x='profit', nbins=25, title='Profit distribution across replications'))
        with b:
            costs = result[['holding_cost','ordering_cost','shortage_cost']].mean().rename_axis('cost').reset_index(name='PKR')
            chart(px.bar(costs, x='cost', y='PKR', title='Mean inventory policy costs'))
        st.subheader('Means and approximate 95% confidence intervals')
        ci_view = ci.astype(object)
        for metric in ci.index:
            ci_view.loc[metric] = ci.loc[metric].map(lambda v: f'{v:.2%}' if metric == 'fill_rate' else str(whole_stock(v)) if metric == 'average_stock' else f'{v:,.2f}')
        ci_view = ci_view.rename(index={'profit': 'Modeled profit (PKR/run)', 'policy_cost': 'Policy cost (PKR/run)',
                                      'fill_rate': 'Fill rate (%)', 'lost_sales': 'Unfulfilled units/run',
                                      'average_stock': 'Average closing stock (units)', 'orders': 'Orders/run',
                                      'stockout_days': 'Stockout days/run'})
        st.dataframe(ci_view, use_container_width=True)
        st.caption('Average closing stock is rounded to whole units. Other averages, including order counts, can have decimals. '
                   'Fill rate is shown as a percentage. Approximate CIs use mean ± 1.96 × standard error; bounds are untruncated.')
    elif page == 'Scenarios':
        st.subheader('Compare demand and supply conditions')
        demand_factor = st.slider('High demand multiplier', 1.0, 3.0, 1.5, 0.1)
        delay = st.slider('Additional supplier delay (days)', 1, 14, 2)
        rows = []
        for name,candidate in [('Baseline',config),('Higher demand',replace(config,daily_demand=config.daily_demand*demand_factor)),('Supplier delay',replace(config,lead_time=config.lead_time+delay))]:
            r,_ = simulate(candidate)
            rows.append(dict(scenario=name, profit=r.profit.mean(), fill_rate=r.fill_rate.mean(), policy_cost=r.policy_cost.mean(), lost_sales=r.lost_sales.mean()))
        table = pd.DataFrame(rows)
        chart(px.bar(table, x='scenario', y='profit', title='Mean modeled profit by scenario'))
        st.dataframe(readable_averages(table), hide_index=True, use_container_width=True)
        st.caption('Baseline and delay scenarios use identical demand streams; higher demand uses the same seeds with a different Poisson mean.')
    elif page == 'Optimization':
        st.subheader('Find a replenishment policy')
        st.write('Grid search minimizes mean holding + ordering + lost-sale penalty cost among candidates meeting the mean fill-rate target.')
        target = st.slider('Target mean unit fill rate', 0.50, 1.0, 0.95, 0.01)
        a,b = st.columns(2)
        points = a.text_input('Reorder points (comma-separated)', '30,60,90,120')
        quantities = b.text_input('Order quantities (comma-separated)', '60,120,180,240')
        if st.button('Search policies', type='primary'):
            try:
                ps, qs = [int(v.strip()) for v in points.split(',')], [int(v.strip()) for v in quantities.split(',')]
                if min(ps) < 0 or min(qs) < 1 or len(set(ps))*len(set(qs)) > 100:
                    raise ValueError('Use nonnegative reorder points, positive quantities, and no more than 100 combinations.')
                with st.spinner('Evaluating candidate policies…'):
                    ranking = optimize(config, ps, qs, target)
                st.session_state.optimization = (asdict(config), target, ranking)
            except ValueError as exc:
                st.error(str(exc))
        saved = st.session_state.get('optimization')
        if saved and saved[0] == asdict(config) and saved[1] == target:
            ranking = saved[2]
            if ranking.meets_target.any():
                best = ranking.iloc[0]
                st.success(f'Best feasible tested policy: s = {int(best.reorder_point)}, Q = {int(best.order_quantity)} · mean fill rate {best.fill_rate:.1%}')
            else:
                st.warning('No tested policy meets the target. Expand the candidate grid.')
            st.dataframe(readable_averages(ranking), hide_index=True, use_container_width=True)
            st.download_button('Download policy ranking', readable_averages(ranking).to_csv(index=False).encode('utf-8-sig'), 'policy_ranking.csv', 'text/csv')
            st.caption('This is the best policy within the tested grid under the model assumptions. Validate selected policies on new seeds before operational use.')
    elif page == 'Reports':
        st.subheader('Day-wise simulation report')
        st.info(f'This report contains {config.days} daily rows from simulation run 1. '
                'It shows actual units and daily costs, not fractional averages across runs.')
        counts = st.columns(4)
        counts[0].metric('Simulation days', len(daily))
        counts[1].metric('Total demand over all days', f'{daily.demand.sum():,} units')
        counts[2].metric('Mean daily demand (units)', f'{daily.demand.mean():.2f}')
        total_demand = int(daily.demand.sum())
        counts[3].metric('Overall fill rate', f'{daily.sales.sum() / total_demand if total_demand else 1:.2%}')
        st.caption('Daily demand is the number of units requested that day. Total demand adds all simulation days. '
                   'Average closing stock is rounded to the nearest whole unit. '
                   'Money is displayed to two decimal places; fill rate uses percentages.')
        include_advanced = st.checkbox('Include advanced per-run totals and confidence intervals', value=False)
        bundle = report_bundle(daily, config, st.session_state.product_name,
                               result if include_advanced else None, ci if include_advanced else None)
        st.download_button('Download report bundle', bundle, 'inventory_report.zip', 'application/zip', type='primary')
        st.download_button('Download daily report (CSV)', daily_display(daily).to_csv(index=False, float_format='%.2f').encode('utf-8-sig'),
                           'daily_simulation_report.csv', 'text/csv')
        show_daily(daily)
        with st.expander('Run 1 totals and averages'):
            summary = run_summary(daily, config).iloc[0]
            summary_values = [f'{v:.2f}' if isinstance(v, float) else str(v) for v in summary]
            st.dataframe(pd.DataFrame({'Metric': summary.index, 'Value': summary_values}), hide_index=True, use_container_width=True)
        st.caption('The downloaded summary and daily rows describe the same run. Dashboard and optimization metrics '
                   f'are means across {config.replications} separate runs and may differ from this single run.')

with st.expander('Model assumptions and metric definitions'):
    st.markdown('''- Independent Poisson daily demand with a constant mean; unmet demand is lost.
- Fixed supplier lead time; unlimited supplier capacity; no expiry or backorders.
- Each day: receive due orders → satisfy demand → record closing stock and costs → review inventory position.
- Inventory position = on-hand + outstanding orders. At most one fixed-size order is placed per day when position ≤ reorder point.
- Fill rate = units sold ÷ demand; defined as 100% when no demand occurs. Stockout days count days with unmet demand.
- Modeled profit = sales revenue − cost of goods sold − holding cost − ordering fees − shortage penalties. This is not cash flow; purchases/terminal stock valuation are excluded.
- Policy cost excludes COGS. Initial stock and a finite horizon can affect policy rankings; there is no warm-up period.
- Currency labels use PKR. Product and settings remain in the current session; exports preserve a run.''')
