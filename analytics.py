# -*- coding: utf-8 -*-
"""组合体检: 持仓相关性矩阵 + 月度收益热力图 -> analytics.json"""
import json
import math

LAST_MONTHS = 15     # 月度热力图保留最近15个月
CORR_BARS = 120      # 相关性用最近120个交易日


def pearson(x, y):
    n = len(x)
    if n < 2:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    den = math.sqrt(sxx * syy)
    return sxy / den if den > 0 else 0.0


def main():
    scan = json.load(open("scan.json", encoding="utf-8"))
    syms = [k for k in scan["kline"] if k.get("tag") != "市场指数"]
    if len(syms) < 2:
        syms = scan["kline"]

    # ---------- 相关性: 按共同交易日对齐最近120根 ----------
    by_date = []
    for s in syms:
        d = {}
        for dt, cl in zip(s["dates"], s["close"]):
            d[dt] = cl
        by_date.append(d)
    common = sorted(set.intersection(*[set(d.keys()) for d in by_date]))
    common = common[-CORR_BARS:]
    names = [s["name"] for s in syms]
    closes = [[d[dt] for dt in common] for d in by_date]
    rets = []
    for cl in closes:
        rets.append([cl[i] / cl[i - 1] - 1 for i in range(1, len(cl))])
    mat = [[round(pearson(rets[i], rets[j]), 3) for j in range(len(rets))]
           for i in range(len(rets))]

    # ---------- 月度收益: 每月最后一个交易日收盘 vs 上一月 ----------
    months_set = sorted({dt[:7] for s in syms for dt in s["dates"]})
    m_rows = []
    for s in syms:
        last_by_month = {}
        for dt, cl in zip(s["dates"], s["close"]):
            last_by_month[dt[:7]] = cl
        m_rows.append({"name": s["name"], "vals": {
            m: last_by_month.get(m) for m in months_set}})
    # 逐月环比(用上一存在月份的月末收盘)
    out_rows = []
    for r in m_rows:
        arr = []
        prev_m, prev_c = None, None
        for m in months_set:
            c = r["vals"].get(m)
            if c is None:
                arr.append(None)
            else:
                arr.append(round(c / prev_c - 1, 4) if (prev_c and m != months_set[0]) else None)
                prev_m, prev_c = m, c
        out_rows.append({"name": r["name"], "rets": arr})
    months = months_set[-LAST_MONTHS:]

    data = {
        "updated": scan["meta"].get("generated", ""),
        "corr": {"names": names, "mat": mat, "bars": CORR_BARS},
        "monthly": {"months": months, "rows": [
            {"name": r["name"], "rets": r["rets"][-LAST_MONTHS:]} for r in out_rows]},
    }
    with open("analytics.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("saved analytics.json  corr:", len(names), "syms; months:", len(months))
    # 展示两位相关性最高的股票对(提示同涨同跌)
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            pairs.append((mat[i][j], names[i], names[j]))
    pairs.sort(reverse=True)
    for v, a, b in pairs[:3]:
        print(f"  高相关 {a} ~ {b}: {v:.2f}")


if __name__ == "__main__":
    main()
