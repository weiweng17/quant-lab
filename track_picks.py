# -*- coding: utf-8 -*-
"""选股命中率跟踪: 把每日推荐写入 picks_history.json, 之后用腾讯日K评估
推荐日收盘价买入 → +1/+3/+5/+10/+20 交易日实际涨跌, 并统计区间内是否先触目标/先触止损
(以收盘价计; 触价用当日最高/最低判断)

另含三项统计:
  · 熔断: 最近成熟样本命中率过低 → 页面亮红牌提醒信号失效
  · 周度: 按 ISO 周聚合命中率, 看信号是在变好还是变坏
  · 分组: 题材股 vs 非题材股命中率, 检验题材权重该不该上调"""
import datetime as dt
import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
FILE = "picks_history.json"
HORIZONS = (1, 3, 5, 10, 20)
FUSE_WINDOW = 20        # 熔断观察窗口: 最近 N 条已满5日样本(10 笔噪声太大)
FUSE_MIN_N = 15         # 窗口内样本少于此数不下熔断结论
FUSE_THRESHOLD = 0.5    # 命中率 <= 50% 视为失效
BENCH = "1.000300"      # 基准: 沪深300 (判断绝对收益里有多少是大盘 beta)


def tx_code(secid):
    mkt, code = secid.split(".")
    return ("sh" if mkt == "1" else "sz") + code


def tx_kline(secid, n=60):
    """腾讯日K(前复权): 返回 [{'d','o','c','h','l'}] 按日期升序"""
    url = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param="
           f"{tx_code(secid)},day,,,{n},qfq")
    last = None
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=10) as r:
                j = json.loads(r.read().decode("utf-8"))
            raw = j["data"][tx_code(secid)]
            rows = raw.get("qfqday") or raw.get("day") or []
            bars = []
            for row in rows:
                bars.append({"d": row[0], "o": float(row[1]), "c": float(row[2]),
                             "h": float(row[3]), "l": float(row[4])})
            return sorted(bars, key=lambda b: b["d"])
        except Exception as e:
            last = e
            time_sleep(1.0)
    raise last


def time_sleep(s):
    import time
    time.sleep(s)


def load_hist():
    try:
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"records": [], "updated": ""}


def main():
    today = dt.date.today()
    now = dt.datetime.now()
    allow_close = now.hour >= 15  # 收盘后当日K线视为完成

    scan = json.load(open("scan.json", encoding="utf-8"))
    gen = (scan["meta"].get("generated") or "")[:10]
    hist = load_hist()
    recs = hist["records"]
    have = {(r["date"], r["secid"]) for r in recs}
    meta = scan.get("meta") or {}

    # 1) 写入今日推荐(附带当天市场环境与权重版本, 便于以后按版本对比成绩)
    for p in scan["picks"]:
        key = (gen, p["secid"])
        if key not in have:
            recs.append({
                "date": gen, "secid": p["secid"], "code": p.get("code", ""),
                "name": p["name"], "sector": p.get("sector", ""),
                "entry": p.get("entry") or p.get("price"),
                "stop": p.get("stop"), "target": p.get("target"),
                "isHot": bool(p.get("isHot")), "hotTags": p.get("hotTags") or [],
                "score": p.get("score"), "techScore": p.get("techScore"),
                "themeScore": p.get("themeScore"),
                "marketScore": meta.get("marketScore"),
                "pickThreshold": meta.get("pickThreshold"),
                "weightsVersion": meta.get("weightsVersion"),
                "r1": None, "r3": None, "r5": None, "r10": None, "r20": None,
                "outcome": None,
            })

    # 2) 需要取K线的: 今日新推荐 + 30天内仍有未完成评价的记录
    need = set()
    for r in recs:
        d = r["date"]
        try:
            age = (today - dt.date.fromisoformat(d)).days
        except Exception:
            age = 999
        if r["secid"] not in need and age <= 90 \
           and (r.get("r20") is None or r["outcome"] is None):
            need.add(r["secid"])
    bars_map = {}
    for secid in need:
        try:
            bars_map[secid] = tx_kline(secid, 120)   # 120 根覆盖 T+20 + 三个月前的老记录
        except Exception as e:
            print(f"  !! 拉取失败 {secid}: {e}")

    # 3) 评估
    def closed_limit(bars):
        lim = -1
        for i, b in enumerate(bars):
            bd = dt.date.fromisoformat(b["d"])
            if bd < today or (bd == today and allow_close):
                lim = i
        return lim

    for r in recs:
        bars = bars_map.get(r["secid"])
        if not bars:
            continue
        dates = [b["d"] for b in bars]
        try:
            i0 = dates.index(r["date"])
        except ValueError:
            continue
        lim = closed_limit(bars)
        entry = bars[i0]["c"] or r["entry"]
        r["entry"] = entry
        for N in HORIZONS:
            j = i0 + N
            if j <= lim:
                key = f"r{N}"
                r[key] = round(bars[j]["c"] / entry - 1, 4)
        # 区间结果: 推荐后至多5个已收盘交易日, 先触目标 or 先触止损
        if i0 + 1 <= lim:
            t_hit = s_hit = None
            for k in range(i0 + 1, min(i0 + 5, lim) + 1):
                b = bars[k]
                if r["target"] and b["h"] >= r["target"] and t_hit is None:
                    t_hit = k
                if r["stop"] and b["l"] <= r["stop"] and s_hit is None:
                    s_hit = k
            if s_hit is not None and (t_hit is None or s_hit < t_hit):
                r["outcome"] = "stop"
            elif t_hit is not None:
                r["outcome"] = "target"
            else:
                r["outcome"] = "hold"

    # 3b) 基准对照: 同一持有期内沪深300 的涨跌, 差额才是真正的选股能力
    bm = None
    try:
        bm = tx_kline(BENCH, 120)
    except Exception as e:
        print(f"  !! 基准取数失败(跳过超额统计): {e}")
    if bm:
        bmap = {b["d"]: i for i, b in enumerate(bm)}
        for r in recs:
            i = bmap.get(r["date"])
            if i is None:
                continue
            for N in (5, 20):
                if r.get(f"r{N}") is not None and i + N < len(bm):
                    br = bm[i + N]["c"] / bm[i]["c"] - 1
                    r[f"b{N}"] = round(br, 4)
                    r[f"e{N}"] = round(r[f"r{N}"] - br, 4)

    # 4) 统计
    total = len(recs)
    matured = [r for r in recs if r["r5"] is not None]
    pend = total - len(matured)

    def hz(n):
        """第 n 日命中率与平均收益(只统计该字段已结算的记录)"""
        v = [r[f"r{n}"] for r in recs if r.get(f"r{n}") is not None]
        if not v:
            return None, None, 0
        return sum(1 for x in v if x > 0) / len(v), sum(v) / len(v), len(v)

    h = {n: hz(n) for n in HORIZONS}
    tg = sum(1 for r in matured if r["outcome"] == "target")
    st = sum(1 for r in matured if r["outcome"] == "stop")

    # 超额: 推荐股收益 - 同期沪深300收益
    def ex(n):
        v = [r for r in recs if r.get(f"e{n}") is not None]
        if not v:
            return None, None, None, 0
        return (sum(r[f"e{n}"] for r in v) / len(v),
                sum(1 for r in v if r[f"e{n}"] > 0) / len(v),
                sum(r[f"b{n}"] for r in v) / len(v),
                len(v))

    x5 = ex(5)
    x20 = ex(20)

    # 熔断: 最近 FUSE_WINDOW 条已成熟样本的 +5 日命中率与平均收益, 分三档
    recent = sorted(matured, key=lambda r: r["date"], reverse=True)[:FUSE_WINDOW]
    rn = len(recent)
    rrate = (sum(1 for r in recent if (r.get("r5") or 0) > 0) / rn) if rn else None
    ravg = (sum(r["r5"] for r in recent) / rn) if rn else None
    base = {"n": rn, "hitRate": rrate, "avg": ravg,
            "threshold": FUSE_THRESHOLD, "window": FUSE_WINDOW, "minN": FUSE_MIN_N}
    if rn < FUSE_MIN_N:
        fuse = dict(base, status="collecting",
                    label=f"样本积累中（{rn}/{FUSE_MIN_N}）")
    elif rrate is not None and rrate <= FUSE_THRESHOLD and (ravg or 0) <= 0:
        fuse = dict(base, status="fused", label="信号已失效 · 建议空仓观察")
    elif rrate is not None and (rrate <= FUSE_THRESHOLD or (ravg or 0) <= 0):
        fuse = dict(base, status="warn", label="边际转弱 · 建议轻仓试错")
    else:
        fuse = dict(base, status="ok", label="信号正常")

    # 周度: 按推荐日所在 ISO 周聚合
    weeks = {}
    for r in matured:
        try:
            d = dt.date.fromisoformat(r["date"])
        except Exception:
            continue
        k = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
        weeks.setdefault(k, []).append(r)
    weekly = []
    for k in sorted(weeks)[-8:]:
        v = weeks[k]
        weekly.append({
            "week": k, "n": len(v),
            "hitRate": sum(1 for r in v if (r.get("r5") or 0) > 0) / len(v),
            "avg5": sum(r["r5"] for r in v) / len(v),
        })

    # 分组: 题材股 vs 非题材股(旧记录无题材标签, 单列)
    def grp(pred):
        v = [r for r in matured if pred(r)]
        if not v:
            return {"n": 0, "hit5Rate": None, "avg5": None, "hit20Rate": None, "avg20": None}
        h5, a5, _ = hz_of(v, 5)
        h20, a20, _ = hz_of(v, 20)
        return {"n": len(v), "hit5Rate": h5, "avg5": a5,
                "hit20Rate": h20, "avg20": a20}
    groups = {
        "hot": grp(lambda r: r.get("isHot") is True),
        "cold": grp(lambda r: r.get("isHot") is False),
        "unlabeled": grp(lambda r: r.get("isHot") is None),
    }

    stats = {
        "total": total, "matured": len(matured), "pending": pend,
        "hit1Rate": h[1][0], "hit3Rate": h[3][0], "hit5Rate": h[5][0],
        "hit10Rate": h[10][0], "hit20Rate": h[20][0],
        "hit5": sum(1 for r in matured if (r.get("r5") or 0) > 0),
        "avg1": h[1][1], "avg3": h[3][1], "avg5": h[5][1],
        "avg10": h[10][1], "avg20": h[20][1],
        "target": tg, "stop": st,
        "bench5": x5[2], "excess5": x5[0], "excess5WinRate": x5[1],
        "bench20": x20[2], "excess20": x20[0], "excess20WinRate": x20[1],
        "excessN": {"5": x5[3], "20": x20[3]},
        "fuse": fuse, "weekly": weekly, "groups": groups,
        "horizonN": {str(n): h[n][2] for n in HORIZONS},
    }
    hist.update({"records": recs, "stats": stats,
                 "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M")})
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, separators=(",", ":"))

    print(f"推荐记录 {total} 条 | 已满5日 {len(matured)} | 待评估 {pend}")
    if matured:
        print(f"  +5日命中 {stats['hit5']}/{len(matured)} ({h[5][0]*100:.0f}%) "
              f"平均 {h[5][1]*100:+.2f}% | 触目标 {tg} 触止损 {st}")
    if h[20][0] is not None:
        print(f"  +20日命中 {h[20][0]*100:.0f}% 平均 {h[20][1]*100:+.2f}% "
              f"(样本 {h[20][2]})")
    print(f"  熔断: {fuse['label']}"
          + (f" (近{fuse['n']}笔 +5日命中 {fuse['hitRate']*100:.0f}% / 均收益 {fuse['avg']*100:+.2f}%)"
             if fuse.get("hitRate") is not None else ""))
    if x5[0] is not None:
        print(f"  +5日超额 {x5[0]*100:+.2f}pp (基准 {x5[2]*100:+.2f}%, 跑赢 {x5[1]*100:.0f}%)")
    if x20[0] is not None:
        print(f"  +20日超额 {x20[0]*100:+.2f}pp (基准 {x20[2]*100:+.2f}%, 跑赢 {x20[1]*100:.0f}%)")
    print("saved picks_history.json")


def hz_of(rows, n):
    """给定记录集合, 返回第 n 日 (命中率, 平均收益, 样本数)"""
    v = [r[f"r{n}"] for r in rows if r.get(f"r{n}") is not None]
    if not v:
        return None, None, 0
    return sum(1 for x in v if x > 0) / len(v), sum(v) / len(v), len(v)


if __name__ == "__main__":
    main()
