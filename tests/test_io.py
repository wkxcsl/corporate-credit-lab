import csv
from dataclasses import asdict
from io import StringIO
from pathlib import Path

import pytest

from creditlab.engine import baseline
from creditlab.io import load_csv

ROOT = Path(__file__).resolve().parents[1]


def sample():
    return (ROOT / "data/demo_financials.csv").read_text(encoding="utf-8-sig")


def encode(rows, fields=None):
    target = StringIO()
    writer = csv.DictWriter(target, fieldnames=fields or list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return target.getvalue()


def test_demo_and_zero_shocks():
    records = load_csv(sample())
    assert len(records) == 12
    assert len({s.company for s in records}) == 3
    for s in records:
        assert baseline(s)["cfo"] == pytest.approx(s.cfo)


@pytest.mark.parametrize("value", ["", "NaN", "inf", "-1", "未知"])
def test_missing_or_invalid_not_imputed(value):
    row = asdict(load_csv(sample())[0])
    row["cash"] = value
    with pytest.raises(ValueError, match="第 2 行"):
        load_csv(encode([row]))


def test_duplicate_period():
    row = asdict(load_csv(sample())[0])
    with pytest.raises(ValueError, match="重复记录"):
        load_csv(encode([row, row]))


def test_headers_empty_extra_missing_duplicate():
    with pytest.raises(ValueError):
        load_csv("")
    row = asdict(load_csv(sample())[0])
    row.pop("source")
    with pytest.raises(ValueError, match="缺少"):
        load_csv(encode([row]))
    row["unknown"] = 1
    with pytest.raises(ValueError, match="多余"):
        load_csv(encode([row]))
    with pytest.raises(ValueError, match="重复列"):
        load_csv("company,company\nA,A\n")
    header = sample().splitlines()[0]
    with pytest.raises(ValueError, match="无数据"):
        load_csv(header)


def test_utf8_bom_and_size_limit():
    assert len(load_csv("\ufeff" + sample())) == 12
    with pytest.raises(ValueError, match="2 MB"):
        load_csv("a" * 2_000_001)
