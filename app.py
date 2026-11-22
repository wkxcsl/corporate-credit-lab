"""Streamlit presentation layer; finance logic lives in creditlab/engine.py."""
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from creditlab.engine import Scenario, baseline, flags, ratios, stress
from creditlab.io import load_csv
from creditlab.report import fmt, make_report

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="企业财务与授信压力测试 | CreditLab", page_icon="📊", layout="wide")
st.markdown("""<style>
.stApp {background: #f5f7fb;}
[data-testid="stMetric"] {background:white; padding:18px; border-radius:12px; border:1px solid #e3e9f0;}
.block-container {padding-top:2rem; max-width:1440px;}
h1,h2,h3 {color:#102b46;}
</style>""", unsafe_allow_html=True)
st.caption("CREDITLAB / CORPORATE FINANCE / v0.1.0")
st.title("企业财务与授信压力测试")
st.markdown("从财务表现走向**现金偿债能力** · 可追溯输入 · 可解释情景 · 可复现报告")

with st.sidebar:
    st.header("分析设置")
    mode = st.radio("数据来源", ["合成演示数据", "上传标准 CSV"])
    upload = st.file_uploader("标准年度财务数据", type=["csv"], disabled=mode != "上传标准 CSV")
    demo_bytes = (ROOT / "data/demo_financials.csv").read_bytes()
    st.download_button("下载数据模板（含合成案例）", demo_bytes, "demo_financials.csv", "text/csv")
    st.caption("单位：人民币百万元；仅年度、非金融企业。同一数据集请统一合并口径。")

try:
    if mode == "上传标准 CSV":
        if upload is None:
            st.info("请上传 CSV。字段和口径见仓库 docs/data_dictionary.md。")
            st.stop()
        if upload.size > 2_000_000:
            raise ValueError("CSV 超过 2 MB")
        records = load_csv(upload.getvalue().decode("utf-8-sig"))
    else:
        records = load_csv(demo_bytes.decode("utf-8-sig"))
except (ValueError, UnicodeError) as exc:
    st.error(f"数据校验未通过：{exc}")
    st.stop()

with st.sidebar:
    companies = sorted({x.company for x in records})
    company = st.selectbox("选择企业", companies, index=companies.index("华衡精密（虚构）") if "华衡精密（虚构）" in companies else 0)
    years = sorted({x.year for x in records if x.company == company}, reverse=True)
    year = st.selectbox("基准年度", years)
    st.divider()
    st.subheader("未来一年压力情景")
    revenue_drop = st.slider("营业收入下降（%）", 0, 50, 10, 5)
    margin_drop = st.slider("毛利率下降（百分点）", 0.0, 20.0, 2.0, 0.5)
    dso_extra = st.slider("回款额外延长（天）", 0, 90, 15, 5)
    with st.expander("更多假设"):
        dio_extra = st.slider("存货额外占用（天）", 0, 90, 0, 5)
        dpo_extra = st.slider("应付额外延长（天）", 0, 90, 0, 5)
        rate_up = st.slider("利率上升（基点）", 0, 500, 100, 25)
        repricing = st.slider("债务重定价比例（%）", 0, 100, 50, 10)
        tax_rate = st.slider("现金税率近似（%）", 0, 50, 25, 1)
    st.caption("情景为用户假设，不是预测。1基点=0.01个百分点；不假设自动续贷。")

s = next(x for x in records if x.company == company and x.year == year)
previous = next((x for x in records if x.company == company and x.year == year - 1), None)
scenario = Scenario(revenue_drop / 100, margin_drop, dso_extra, dio_extra, dpo_extra, rate_up, repricing / 100, tax_rate / 100)
r, base, result = ratios(s, previous), baseline(s, scenario.tax_rate), stress(s, scenario)
st.info("教学与作品集项目 · 演示企业完全虚构 · 不属于任何银行官方系统 · 不输出信用评级或授信决策")
st.subheader(f"{company} · {year}")
st.caption(f"{s.industry} | 历史周转指标：{r['balance_basis']} | 金额：人民币百万元")
cols = st.columns(4)
cols[0].metric("营业收入", fmt(s.revenue), fmt(r["revenue_growth"], True) if r["revenue_growth"] is not None else "无连续上年")
cols[1].metric("资产负债率", fmt(r["debt_asset_ratio"], True))
cols[2].metric("基准现金偿债覆盖", fmt(base["dscr_proxy"]))
cols[3].metric("情景现金偿债覆盖", fmt(result["dscr_proxy"]), f"{result['dscr_proxy'] - base['dscr_proxy']:+.2f}倍" if result["dscr_proxy"] is not None and base["dscr_proxy"] is not None else None)

tab1, tab2, tab3, tab4 = st.tabs(["财务画像", "压力测试与现金桥接", "尽调线索与报告", "数据与模型口径"])
with tab1:
    history = sorted([x for x in records if x.company == company and x.year <= year], key=lambda x: x.year)
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("#### 利润能否转化为现金？")
        fig = go.Figure()
        for label, key, color in [("净利润", "net_profit", "#287db5"), ("经营现金流", "cfo", "#16a394")]:
            fig.add_bar(x=[str(x.year) for x in history], y=[getattr(x, key) for x in history], name=label, marker_color=color)
        fig.update_layout(height=320, barmode="group", yaxis_title="人民币百万元", legend_orientation="h", margin=dict(l=20,r=20,t=20,b=20), plot_bgcolor="white")
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.markdown("#### 关键财务指标")
        display = [("毛利率", fmt(r["gross_margin"], True)), ("净利率", fmt(r["net_margin"], True)), ("流动比率", fmt(r["current_ratio"])), ("非受限现金/短期有息债务", fmt(r["cash_short_debt"])), ("EBIT/现金利息支出", fmt(r["interest_coverage"])), ("经营现金流/净利润", fmt(r["cfo_profit"])), ("净债务/EBITDA近似", fmt(r["net_debt_ebitda"]))]
        st.dataframe(pd.DataFrame(display, columns=["指标", "数值"]), hide_index=True, width="stretch")
    days = st.columns(4)
    for col, key, name in zip(days, ["dso", "dio", "dpo", "ccc"], ["应收周转天数", "存货周转天数", "应付周转天数", "现金转换周期"]):
        col.metric(name, f"{r[key]:.1f}天")
    st.caption("收入代替赊销收入、营业成本代替采购额；周转天数为近似值，不能直接作为账龄。")

with tab2:
    st.markdown("#### 从经营现金流到偿债后现金")
    labels = ["期初可用现金", "基准CFO", "毛利变化", "税款影响", "营运资金影响", "维持性资本开支", "现金利息", "到期本金", "偿债后现金"]
    amounts = [s.cash-s.restricted_cash, s.cfo, result["gross_profit_delta"], -result["tax_delta"], -result["nwc_delta"], -s.maintenance_capex, -result["interest"], -s.principal_due, 0]
    bridge = go.Figure(go.Waterfall(x=labels, y=amounts, measure=["absolute"]+["relative"]*7+["total"], increasing=dict(marker=dict(color="#16a394")), decreasing=dict(marker=dict(color="#d65d5d")), totals=dict(marker=dict(color="#183d5b"))))
    bridge.update_layout(height=380, yaxis_title="人民币百万元", margin=dict(l=20,r=20,t=20,b=20), plot_bgcolor="white")
    st.plotly_chart(bridge, width="stretch")
    a, b, c = st.columns(3)
    a.metric("情景经营现金流", fmt(result["cfo"]))
    b.metric("情景偿债后可用现金", fmt(result["cash_after_service"]))
    c.metric("未融资缺口（非授信额度）", fmt(result["funding_gap"]))
    st.markdown("#### 双因素敏感性：收入下降 × 回款延长")
    drops, delays = [0, 5, 10, 15, 20, 25, 30], [0, 15, 30, 45, 60]
    matrix = [[stress(s, replace(scenario, revenue_drop=d/100, dso_extra=t))["dscr_proxy"] for d in drops] for t in delays]
    if base["debt_service"] > 0:
        heat = go.Figure(go.Heatmap(z=matrix, x=[f"{x}%" for x in drops], y=[f"+{x}天" for x in delays], texttemplate="%{z:.2f}", colorscale=[[0,"#c44c56"],[0.5,"#f7f4ec"],[1,"#159a88"]], zmid=1, colorbar_title="覆盖倍数"))
        heat.update_layout(height=310, xaxis_title="营业收入下降", yaxis_title="回款额外延长", margin=dict(l=20,r=20,t=20,b=20))
        st.plotly_chart(heat, width="stretch")
    else:
        st.info("到期本金及现金利息均为零，覆盖倍数无定义。")
    st.caption("其他参数保持当前侧栏设定；该矩阵是情景试算，不是概率预测。覆盖倍数<1表示该口径现金流不足以覆盖本息。")

with tab3:
    st.markdown("#### 将指标转成可追问的问题")
    signals = flags(s, r, result)
    if signals:
        for item in signals:
            st.warning(f"**{item['signal']}** — {item['question']}")
    else:
        st.info("未触发演示阈值不代表低风险。继续核验财报、征信、行业及担保信息。")
    st.markdown("**建议补充材料**：应收账龄及前五大客户、银行流水、债务到期表、受限资金明细、担保及关联交易、月度现金预算。")
    report = make_report(s, scenario, previous)
    st.download_button("导出完整分析备忘录（Markdown）", report, f"credit_memo_{year}.md", "text/markdown")
    with st.expander("预览分析备忘录"):
        st.markdown(report)

with tab4:
    st.markdown("#### 原始输入")
    st.dataframe(pd.DataFrame([asdict(x) for x in history]), hide_index=True, width="stretch")
    st.write("来源声明：", s.source)
    st.caption("来源字段由数据提供者声明；通过结构检查不表示财务数据真实或经审计。上传内容不由应用写入文件或共享缓存；若部署到云端，数据会传到该云服务。")
    st.markdown((ROOT / "docs/methodology.md").read_text(encoding="utf-8"))

st.divider()
st.caption("CreditLab · Python + Streamlit · 公式与测试开放可查 · 缺失值不补零，分母非正不伪造结果")
