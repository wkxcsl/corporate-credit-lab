from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_dashboard_company_year_and_scenario():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "企业财务与授信压力测试"
    initial = app.metric[3].value
    app.slider[2].set_value(60).run()
    assert not app.exception
    assert app.metric[3].value != initial
    app.selectbox[0].select("澄远商贸（虚构）").run()
    app.selectbox[1].select(2022).run()
    assert not app.exception
    assert "2022" in app.subheader[0].value
    app.radio[0].set_value("上传标准 CSV").run()
    assert not app.exception
    assert any("请上传" in x.value for x in app.info)
