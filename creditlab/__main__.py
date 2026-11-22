import argparse
from pathlib import Path

from .engine import Scenario
from .io import load_csv
from .report import make_report


def main():
    parser = argparse.ArgumentParser(description="企业财务分析备忘录（纯Python，无第三方依赖）")
    parser.add_argument("--input", default="data/demo_financials.csv")
    parser.add_argument("--company", default="华衡精密（虚构）")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--revenue-drop", type=float, default=0.1)
    parser.add_argument("--dso-extra", type=float, default=15)
    parser.add_argument("--output", default="reports/credit_memo.md")
    args = parser.parse_args()
    try:
        records = load_csv(Path(args.input).read_text(encoding="utf-8-sig"))
        s = next((x for x in records if x.company == args.company and x.year == args.year), None)
        if s is None:
            raise ValueError("未找到指定企业与年度")
        previous = next((x for x in records if x.company == s.company and x.year == s.year - 1), None)
        report = make_report(s, Scenario(revenue_drop=args.revenue_drop, dso_extra=args.dso_extra), previous)
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report, encoding="utf-8")
        print(f"Report saved: {target}")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
