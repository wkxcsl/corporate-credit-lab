"""Strict CSV adapter; no silent imputation of missing financial amounts."""

import csv
from dataclasses import fields
from io import StringIO

from .engine import Statement


def load_csv(text: str) -> list[Statement]:
    if len(text) > 2_000_000:
        raise ValueError("CSV 超过 2 MB，请仅导入所需年度与企业")
    reader = csv.DictReader(StringIO(text.lstrip("\ufeff")))
    required = {f.name for f in fields(Statement)}
    headers = reader.fieldnames or []
    if len(headers) != len(set(headers)):
        raise ValueError("CSV 表头包含重复列")
    if set(headers) != required:
        raise ValueError(f"CSV 列不匹配；缺少：{sorted(required - set(headers))}；多余：{sorted(set(headers) - required)}")
    records, seen = [], set()
    for line, row in enumerate(reader, 2):
        if line > 5001:
            raise ValueError("最多支持 5000 行")
        try:
            if None in row or any(v is None or not v.strip() for v in row.values()):
                raise ValueError("存在空值或列数不一致，缺失值不能填零代替")
            values = {k: v.strip() for k, v in row.items()}
            for key in required - {"company", "industry", "source", "year"}:
                values[key] = float(values[key])
            values["year"] = int(values["year"])
            statement = Statement(**values)
            statement.validate()
            identity = (statement.company, statement.year)
            if identity in seen:
                raise ValueError("同一企业同一年度出现重复记录")
            seen.add(identity)
            records.append(statement)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"第 {line} 行：{exc}") from exc
    if not records:
        raise ValueError("CSV 无数据")
    return sorted(records, key=lambda x: (x.company, x.year))
