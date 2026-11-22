from dataclasses import asdict, replace
from math import inf, nan

import pytest

from creditlab.engine import Scenario, Statement, baseline, divide, flags, ratios, stress
from creditlab.report import make_report


@pytest.fixture
def company():
    return Statement(company="测试制造", industry="制造", year=2025, revenue=1000, cogs=600,
        ebit=200, net_profit=120, depreciation=20, cash=100, restricted_cash=10,
        receivables=200, inventory=120, current_assets=450, total_assets=800,
        payables=60, current_liabilities=200, total_liabilities=450, equity=350,
        short_debt=100, long_debt=200, interest=20, cfo=160,
        maintenance_capex=30, principal_due=80, source="独立手算测试夹具")


def test_hand_calculated_cash_bridge(company):
    # Worked example in docs/test_case.md, not a second implementation.
    result = stress(company, Scenario(.10, 2, 30, 10, 5, 200, .5, .25))
    expected = {"revenue": 900, "gross_margin": .38, "ebit": 142, "interest": 23,
        "tax_delta": -15.25, "nwc_delta": 57.4164383561644,
        "cfo": 59.8335616438356, "cfads": 29.8335616438356,
        "debt_service": 103, "cash_after_service": 16.8335616438356, "funding_gap": 0}
    for key, value in expected.items():
        assert result[key] == pytest.approx(value)
    assert result["dscr_proxy"] == pytest.approx(.289646229551802)


def test_zero_shock_reproduces_inputs(company):
    result = baseline(company)
    assert result["cfo"] == pytest.approx(160)
    assert result["nwc_delta"] == pytest.approx(0)
    assert result["dscr_proxy"] == pytest.approx(1.3)
    assert result["cash_after_service"] == pytest.approx(120)


def test_interest_deducted_once_no_tax(company):
    result = stress(company, Scenario(0, 0, 0, 0, 0, 100, 1, 0))
    assert result["cfo"] == pytest.approx(160)
    assert result["interest"] == pytest.approx(23)
    assert result["cash_after_service"] == pytest.approx(117)


def test_one_day_collection_delay_cost(company):
    result = stress(company, Scenario(0, 0, 1, 0, 0, 0, 0, 0))
    assert baseline(company)["cfo"] - result["cfo"] == pytest.approx(1000 / 365)


def test_average_balance_and_missing_year(company):
    previous = replace(company, year=2024, receivables=100)
    assert ratios(company, previous)["dso"] == pytest.approx(54.75)
    assert ratios(company)["dso"] == pytest.approx(73)
    assert ratios(company)["revenue_growth"] is None
    with pytest.raises(ValueError, match="上一年度"):
        ratios(company, replace(previous, year=2023))
    with pytest.raises(ValueError, match="上一年度"):
        ratios(company, replace(previous, company="另一企业"))


def test_nonpositive_denominators_and_negative_numerators(company):
    assert divide(1, 0) is None
    assert divide(1, -2) is None
    assert divide(-1, 2) == -.5
    assert ratios(replace(company, net_profit=-5))["cfo_profit"] is None
    assert ratios(replace(company, ebit=-30))["net_debt_ebitda"] is None
    result = stress(replace(company, cfo=-30), Scenario(0, 0, 0, 0, 0, 0, 0, 0))
    assert result["dscr_proxy"] < 0
    assert result["funding_gap"] == pytest.approx(70)


def test_no_debt_no_fake_zero_coverage(company):
    s = replace(company, short_debt=0, long_debt=0, interest=0, principal_due=0)
    r, result = ratios(s), baseline(s)
    assert r["cash_short_debt"] is None
    assert result["dscr_proxy"] is None
    assert not any("覆盖不足" in x["signal"] for x in flags(s, r, result))


def test_tax_loss_no_refund(company):
    result = stress(company, Scenario(.5, 20, 0, 0, 0, 0, 0, .25))
    assert result["ebit"] < 0
    assert result["tax_delta"] == pytest.approx(-45)


@pytest.mark.parametrize("change", [
    {"cash": nan}, {"interest": inf}, {"revenue": 0}, {"cogs": 0},
    {"cash": -1}, {"restricted_cash": 101}, {"equity": 1},
    {"current_assets": 10}, {"long_debt": 300}, {"principal_due": 301},
    {"year": 2025.5}, {"company": ""}, {"source": ""},
])
def test_invalid_financials(company, change):
    with pytest.raises(ValueError):
        replace(company, **change).validate()


@pytest.mark.parametrize("change", [{"revenue_drop": .6}, {"margin_drop_pp": -1}, {"dso_extra": nan}, {"rate_up_bps": 1000}, {"repricing_share": 2}])
def test_invalid_scenarios(company, change):
    with pytest.raises(ValueError):
        stress(company, replace(Scenario(), **change))


def test_report_contains_audit_inputs(company):
    report = make_report(company, Scenario(), replace(company, year=2024))
    for key in asdict(company):
        assert key in report
    assert "连续上年输入" in report
    assert "资金缺口不是授信额度" in report
    assert "税款变化" in report
