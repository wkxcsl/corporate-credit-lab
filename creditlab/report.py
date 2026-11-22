"""Deterministic Markdown memo with inputs and assumptions for auditability."""

from dataclasses import asdict

from .engine import Scenario, Statement, baseline, flags, ratios, stress


def fmt(value, percent=False):
    if value is None:
        return "N/A（分母非正或缺少上年数据）"
    return f"{value:.1%}" if percent else f"{value:,.2f}"


def safe_text(text):
    return str(text).replace("\n", " ").replace("\r", " ").replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")


def make_report(s: Statement, scenario: Scenario, previous=None) -> str:
    r, result, base = ratios(s, previous), stress(s, scenario), baseline(s, scenario.tax_rate)
    lines = [
        f"# {safe_text(s.company)}｜企业财务与情景分析备忘录",
        "", "> 教学分析工具；不构成银行评级、授信审批、额度建议或投资建议。与任何银行无隶属或背书关系。",
        "", f"- 基准年度：{s.year}；行业：{safe_text(s.industry)}；金额单位：人民币百万元。",
        f"- 数据来源：{safe_text(s.source)}。来源为用户声明，本工具不自动核验。",
        f"- 周转指标口径：{r['balance_basis']}；年度按365天。",
        "", "## 一、财务观察", "", "| 指标 | 结果 |", "|---|---:|",
    ]
    for key, label, percent in [
        ("revenue_growth", "收入同比", True), ("gross_margin", "毛利率", True),
        ("net_margin", "净利率", True), ("debt_asset_ratio", "资产负债率", True),
        ("current_ratio", "流动比率", False), ("cash_short_debt", "非受限现金/短期有息债务", False),
        ("interest_coverage", "EBIT/现金利息支出", False), ("cfo_profit", "经营现金流/净利润", False),
        ("net_debt_ebitda", "净债务/EBITDA近似", False), ("dso", "应收周转天数", False),
        ("dio", "存货周转天数", False), ("dpo", "应付周转天数", False), ("ccc", "现金转换周期", False),
    ]:
        lines.append(f"| {label} | {fmt(r[key], percent)} |")
    lines += ["", "## 二、情景与现金桥接", "", "| 参数 | 数值 |", "|---|---:|"]
    labels = {"revenue_drop": "收入下降比例（小数）", "margin_drop_pp": "毛利率下降（百分点）", "dso_extra": "应收额外天数", "dio_extra": "存货额外天数", "dpo_extra": "应付额外天数", "rate_up_bps": "利率上升（基点）", "repricing_share": "债务重定价比例（小数）", "tax_rate": "现金税率近似（小数）"}
    lines += [f"| {labels[k]} | {v:g} |" for k, v in asdict(scenario).items()]
    lines += ["", "| 现金指标 | 零冲击基准 | 压力情景 |", "|---|---:|---:|"]
    for key, label in [("cfo", "经营现金流"), ("cfads", "扣维持性资本开支后现金流"), ("debt_service", "利息及到期本金"), ("dscr_proxy", "现金偿债覆盖倍数（近似）"), ("cash_after_service", "偿债后可用现金"), ("funding_gap", "未融资缺口")]:
        lines.append(f"| {label} | {fmt(base[key])} | {fmt(result[key])} |")
    lines += ["", f"现金桥接：基准CFO {s.cfo:,.2f} + 毛利变化 {result['gross_profit_delta']:,.2f} − 税款变化 {result['tax_delta']:,.2f} − 营运资金增加 {result['nwc_delta']:,.2f} = 情景CFO {result['cfo']:,.2f}。", "", "## 三、尽调线索", ""]
    signals = flags(s, r, result)
    lines += [f"- **{item['signal']}**：{item['question']}" for item in signals] or ["- 未触发所列演示阈值，不代表低风险或建议授信。"]
    lines += [
        "", "## 四、模型边界", "",
        "- 未来一年静态测算，保持期间费用、折旧、维持性资本开支及本金到期额不变；不模拟完整三张报表。",
        "- 营运资金采用期末余额校准，和历史平均余额周转指标口径不同；零冲击精确回到基准。",
        "- CFO必须为未扣筹资性现金利息的经营现金流；利息只在偿债支出中扣除一次。若原数据把利息列入经营活动，须先重分类。",
        "- 税款变化用max(EBIT−现金利息,0)×税率近似；不预测退税、递延税或亏损结转。",
        "- 不考虑新增融资、自动续贷、股东注资、分红、扩张性资本开支、担保履约及汇率；资金缺口不是授信额度。",
        "- 非受限现金不等于全部可用于还款；模型未扣最低经营现金储备，可能低估资金需求。",
        "- 年末余额及年度现金流会掩盖季节性和年内到期错配；需按月现金预算补充。",
        "", "## 五、原始输入快照", "", "| 字段 | 值 |", "|---|---|",
    ]
    lines += [f"| {key} | {safe_text(value)} |" for key, value in asdict(s).items()]
    if previous:
        lines += ["", "### 连续上年输入（同比与平均余额的计算依据）", "", "| 字段 | 值 |", "|---|---|"]
        lines += [f"| {key} | {safe_text(value)} |" for key, value in asdict(previous).items()]
    return "\n".join(lines) + "\n"
