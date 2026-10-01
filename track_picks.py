# -*- coding: utf-8 -*-
"""选股命中率跟踪: 把每日推荐写入 picks_history.json, 之后用腾讯日K评估
推荐日收盘价买入 → +1/+3/+5 交易日实际涨跌, 并统计区间内是否先触目标/先触止损
(以收盘价计; 触价用当日最高/最低判断)"""
import datetime as dt
import json
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
FILE = "picks_history.json"
HORIZONS = (1, 3, 5)


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

    # 1) 写入今日推荐
    for p in scan["picks"]:
        key = (gen, p["secid"])
        if key not in have:
            recs.append({
                "date": gen, "secid": p["secid"], "code": p.get("code", ""),
                "name": p["name"], "sector": p.get("sector", ""),
                "entry": p.get("entry") or p.get("price"),
                "stop": p.get("stop"), "target": p.get("target"),
                "r1": None, "r3": None, "r5": None, "outcome": None,
            })

    # 2) 需要取K线的: 今日新推荐 + 20天内仍有未完成评价的记录
    need = set()
    for r in recs:
        d = r["date"]
        try:
            age = (today - dt.date.fromisoformat(d)).days
        except Exception:
            age = 999
        if r["secid"] not in need and age <= 20 and (r["r5"] is None or r["outcome"] is None):
            need.add(r["secid"])
    bars_map = {}
    for secid in need:
        try:
            bars_map[secid] = tx_kline(secid, 60)
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

    # 4) 统计
    total = len(recs)
    matured = [r for r in recs if r["r5"] is not None]
    pend = total - len(matured)
    def rate(pred):
        v = [r for r in matured if pred(r)]
        return len(v), (len(v) / len(matured) if matured else None)
    hit5, hit5r = rate(lambda r: r["r5"] > 0)
    hit3, hit3r = rate(lambda r: (r["r3"] or 0) > 0)
    avg5 = sum(r["r5"] for r in matured) / len(matured) if matured else None
    tg = sum(1 for r in matured if r["outcome"] == "target")
    st = sum(1 for r in matured if r["outcome"] == "stop")
    stats = {
        "total": total, "matured": len(matured), "pending": pend,
        "hit5": hit5, "hit5Rate": hit5r, "hit3": hit3, "hit3Rate": hit3r,
        "avg5": avg5, "target": tg, "stop": st,
    }
    hist.update({"records": recs, "stats": stats,
                 "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M")})
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, separators=(",", ":"))

    print(f"推荐记录 {total} 条 | 已满5日 {len(matured)} | 待评估 {pend}")
    if matured:
        print(f"  +5日命中 {hit5}/{len(matured)} ({hit5r*100:.0f}%) 平均 {avg5*100:+.2f}% | "
              f"触目标 {tg} 触止损 {st}")
    print("saved picks_history.json")


if __name__ == "__main__":
    main()
