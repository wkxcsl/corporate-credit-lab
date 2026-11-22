"""Pure-Python finance engine. Amounts: CNY million; annual periods only."""

from dataclasses import asdict, dataclass
from math import isfinite


@dataclass(frozen=True)
class Statement:
    company: str
    industry: str
    year: int
    revenue: float
    cogs: float
    ebit: float
    net_profit: float
    depreciation: float
    cash: float
    restricted_cash: float
    receivables: float
    inventory: float
    current_assets: float
    total_assets: float
    payables: float
    current_liabilities: float
    total_liabilities: float
    equity: float
    short_debt: float
    long_debt: float
    interest: float
    cfo: float
    maintenance_capex: float
    principal_due: float
    source: str

    def validate(self):
        if not all(isinstance(x, str) and x.strip() for x in (self.company, self.industry, self.source)):
            raise ValueError("企业名称、行业和数据来源不能为空")
        if isinstance(self.year, bool) or not isinstance(self.year, int) or not 1900 <= self.year <= 2100:
            raise ValueError("年份必须是 1900–2100 的整数")
        signed = {"ebit", "net_profit", "cfo", "equity"}
        for key, value in asdict(self).items():
            if key in {"company", "industry", "source", "year"}:
                continue
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value):
                raise ValueError(f"{key}: 必须是有限数值，不能留空、NaN 或无穷大")
            if key not in signed and value < 0:
                raise ValueError(f"{key}: 不得为负数")
        if self.revenue <= 0 or self.cogs <= 0 or self.total_assets <= 0:
            raise ValueError("收入、营业成本、总资产必须大于零；本工具适用于持续经营的非金融企业")
        checks = [
            (self.restricted_cash, self.cash, "受限资金不能超过货币资金"),
            (self.cash + self.receivables + self.inventory, self.current_assets, "货币资金、应收账款及存货之和不能超过流动资产"),
            (self.current_assets, self.total_assets, "流动资产不能超过总资产"),
            (self.short_debt + self.payables, self.current_liabilities, "短期有息债务及应付账款之和不能超过流动负债"),
            (self.current_liabilities, self.total_liabilities, "流动负债不能超过总负债"),
            (self.short_debt + self.long_debt, self.total_liabilities, "有息债务不能超过总负债"),
            (self.long_debt, self.total_liabilities - self.current_liabilities, "长期有息债务不能超过非流动负债"),
            (self.principal_due, self.short_debt + self.long_debt, "未来12个月到期本金不能超过存量有息债务"),
        ]
        for left, right, message in checks:
            if left > right + 1e-6:
                raise ValueError(message)
        if abs(self.total_assets - self.total_liabilities - self.equity) > max(0.01, self.total_assets * 0.001):
            raise ValueError("资产不等于负债加权益（允许 0.1% 或 0.01 百万元的舍入误差）")


def divide(numerator, denominator):
    """Nonpositive denominator means not meaningful, never a fake zero."""
    return numerator / denominator if denominator > 0 else None


def ratios(s: Statement, previous: Statement | None = None) -> dict:
    s.validate()
    if previous is not None:
        previous.validate()
        if previous.company != s.company or previous.year != s.year - 1:
            raise ValueError("期初数据必须来自同一企业的上一年度")
    def balance(name):
        return (getattr(s, name) + getattr(previous, name)) / 2 if previous else getattr(s, name)
    dso = balance("receivables") / s.revenue * 365
    dio = balance("inventory") / s.cogs * 365
    dpo = balance("payables") / s.cogs * 365
    return {
        "revenue_growth": divide(s.revenue - previous.revenue, previous.revenue) if previous else None,
        "gross_margin": (s.revenue - s.cogs) / s.revenue,
        "net_margin": s.net_profit / s.revenue,
        "debt_asset_ratio": s.total_liabilities / s.total_assets,
        "current_ratio": divide(s.current_assets, s.current_liabilities),
        "cash_short_debt": divide(s.cash - s.restricted_cash, s.short_debt),
        "interest_coverage": divide(s.ebit, s.interest),
        "cfo_profit": divide(s.cfo, s.net_profit),
        "net_debt_ebitda": divide(s.short_debt + s.long_debt - s.cash + s.restricted_cash, s.ebit + s.depreciation),
        "dso": dso, "dio": dio, "dpo": dpo, "ccc": dso + dio - dpo,
        "dscr_proxy": divide(s.cfo - s.maintenance_capex, s.interest + s.principal_due),
        "balance_basis": "期初期末平均余额" if previous else "期末余额近似（缺少连续上年数据）",
    }


@dataclass(frozen=True)
class Scenario:
    revenue_drop: float = 0.10
    margin_drop_pp: float = 2.0
    dso_extra: float = 15.0
    dio_extra: float = 0.0
    dpo_extra: float = 0.0
    rate_up_bps: float = 100.0
    repricing_share: float = 0.5
    tax_rate: float = 0.25

    def validate(self):
        bounds = {
            "revenue_drop": (0, 0.5), "margin_drop_pp": (0, 20),
            "dso_extra": (0, 90), "dio_extra": (0, 90), "dpo_extra": (0, 90),
            "rate_up_bps": (0, 500), "repricing_share": (0, 1), "tax_rate": (0, 0.5),
        }
        for name, (lo, hi) in bounds.items():
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not isfinite(value) or not lo <= value <= hi:
                raise ValueError(f"{name}: 必须介于 {lo} 和 {hi} 之间")


def stress(s: Statement, scenario: Scenario) -> dict:
    """One-year static bridge; CFO excludes financing interest cash payments.

    Closing working-capital ratios anchor the projection to make a zero-shock
    scenario exactly reproduce the input. No automatic refinancing is assumed.
    """
    s.validate()
    scenario.validate()
    revenue = s.revenue * (1 - scenario.revenue_drop)
    margin = (s.revenue - s.cogs) / s.revenue - scenario.margin_drop_pp / 100
    cogs = revenue * (1 - margin)
    gross_profit_delta = (revenue - cogs) - (s.revenue - s.cogs)
    ebit = s.ebit + gross_profit_delta  # period operating expenses held fixed
    interest = s.interest + (s.short_debt + s.long_debt) * scenario.repricing_share * scenario.rate_up_bps / 10000
    tax_delta = (max(ebit - interest, 0) - max(s.ebit - s.interest, 0)) * scenario.tax_rate
    ar = revenue * (s.receivables / s.revenue + scenario.dso_extra / 365)
    inventory = cogs * (s.inventory / s.cogs + scenario.dio_extra / 365)
    payables = cogs * (s.payables / s.cogs + scenario.dpo_extra / 365)
    nwc_delta = ar + inventory - payables - (s.receivables + s.inventory - s.payables)
    cfo = s.cfo + gross_profit_delta - tax_delta - nwc_delta
    cfads = cfo - s.maintenance_capex
    service = interest + s.principal_due
    cash_after_service = s.cash - s.restricted_cash + cfads - service
    return {
        "revenue": revenue, "gross_margin": margin, "ebit": ebit,
        "interest": interest, "gross_profit_delta": gross_profit_delta,
        "tax_delta": tax_delta, "receivables": ar, "inventory": inventory,
        "payables": payables, "nwc_delta": nwc_delta, "cfo": cfo,
        "cfads": cfads, "debt_service": service,
        "dscr_proxy": divide(cfads, service), "cash_after_service": cash_after_service,
        "funding_gap": max(0.0, -cash_after_service),
    }


def baseline(s: Statement, tax_rate=0.25) -> dict:
    return stress(s, Scenario(0, 0, 0, 0, 0, 0, 0, tax_rate))


def flags(s: Statement, r: dict, result: dict) -> list[dict]:
    """Educational discussion prompts, not a credit rating or lending decision."""
    rules = [
        (s.equity <= 0, "净资产非正", "核对持续经营、股东支持及或有负债。"),
        (r["debt_asset_ratio"] > 0.70, "资产负债率超过演示阈值70%", "结合行业及同业口径判断杠杆是否偏高。"),
        (s.cfo < 0, "经营现金流为负", "核对回款、存货占用、关联交易和一次性支付。"),
        (s.net_profit > 0 and s.cfo < s.net_profit * 0.8, "现金利润比低于演示阈值0.8", "核对利润向现金的转化及现金流分类。"),
        (r["interest_coverage"] is not None and r["interest_coverage"] < 2, "利息保障倍数低于演示阈值2", "核对财务费用、资本化利息及有息债务。"),
        (result["dscr_proxy"] is not None and result["dscr_proxy"] < 1, "情景现金偿债覆盖不足1倍", "核对本金到期分布、续贷条件及偿债资金来源。"),
        (result["funding_gap"] > 0, "情景出现资金缺口", "核对未受限现金、承诺授信、资产变现与股东支持；不假设自动续贷。"),
    ]
    return [{"signal": name, "question": question} for condition, name, question in rules if condition]
