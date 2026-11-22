"""Reproducible, explicitly synthetic annual observations; no client data."""
import csv
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creditlab.engine import Statement


def generate():
    rows = []
    for i, year in enumerate(range(2022, 2026)):
        for name, sector, values in [
            ("华衡精密（虚构）", "通用设备制造", dict(revenue=500+70*i, cogs=375+55*i, ebit=55+4*i, net_profit=35+2*i, depreciation=15+2*i, cash=60-8*i, restricted_cash=5+i, receivables=85+40*i, inventory=65+15*i, payables=60+8*i, short_debt=80+22*i, long_debt=95+8*i, cfo=55-14*i, interest=9+2*i, maintenance_capex=18+2*i, principal_due=50+18*i)),
            ("澄远商贸（虚构）", "批发与贸易", dict(revenue=800+80*i, cogs=704+70*i, ebit=40+5*i, net_profit=25+3*i, depreciation=6+i, cash=50+10*i, restricted_cash=4, receivables=75+6*i, inventory=90+7*i, payables=105+9*i, short_debt=65+5*i, long_debt=30, cfo=45+6*i, interest=5+i, maintenance_capex=8+i, principal_due=25+3*i)),
            ("锦川材料（虚构）", "基础化工材料", dict(revenue=650-25*i, cogs=455-5*i, ebit=105-26*i, net_profit=65-23*i, depreciation=32+2*i, cash=70-12*i, restricted_cash=8+2*i, receivables=80+15*i, inventory=110+18*i, payables=70+5*i, short_debt=90+20*i, long_debt=210+12*i, cfo=95-32*i, interest=18+2*i, maintenance_capex=35+2*i, principal_due=60+15*i)),
        ]:
            values["current_assets"] = values["cash"] + values["receivables"] + values["inventory"] + 25
            values["total_assets"] = values["current_assets"] + (420 if sector == "基础化工材料" else 220)
            values["current_liabilities"] = values["payables"] + values["short_debt"] + 35
            values["total_liabilities"] = values["current_liabilities"] + values["long_debt"] + 25
            values["equity"] = values["total_assets"] - values["total_liabilities"]
            record = Statement(company=name, industry=sector, year=year, source="项目规则生成的合成数据，无真实企业对应；见scripts/generate_demo.py", **values)
            record.validate()
            rows.append(asdict(record))
    target = ROOT / "data" / "demo_financials.csv"
    target.parent.mkdir(exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} synthetic company-year observations.")


if __name__ == "__main__":
    generate()
