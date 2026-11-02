from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_all_workspace_pages():
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
    assert not app.exception
    for page in ['Inventory setup','Simulation','Analytics','Scenarios','Optimization','Reports','Dashboard']:
        app.sidebar.radio[0].set_value(page).run(timeout=30)
        assert not app.exception, str(app.exception)
    assert len(app.metric) == 4


def test_optimization_and_saved_product():
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
    app.sidebar.radio[0].set_value('Optimization').run()
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert app.dataframe
    app.sidebar.radio[0].set_value('Inventory setup').run()
    app.selectbox[0].set_value(1).run()
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state['product_name'] == 'USB Keyboard'


def test_report_defaults_to_days_not_run_totals():
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py')).run(timeout=30)
    app.sidebar.radio[0].set_value('Reports').run(timeout=30)
    assert not app.exception
    daily = app.dataframe[0].value
    assert daily.columns[0] == 'Simulation day'
    assert len(daily) == 90
    assert daily['Daily fill rate'].str.endswith('%').all()
    assert not app.checkbox[0].value
    app.checkbox[0].set_value(True).run(timeout=30)
    assert not app.exception
