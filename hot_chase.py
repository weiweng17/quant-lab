# -*- coding: utf-8 -*-
"""热点隔日交易检验: 每日抓热点(涨幅榜/放量) -> 次日开盘买 -> 持1~2日卖
核心问题: 这种"追热点短打"在日线级别到底赚不赚钱?

口径: open_t1(信号收盘生成, 次日开盘成交) + 竞价涨停买不进剔除(次日开盘涨幅>=9.5%)
费用: 买万2.5, 卖万2.5+印花税万5
对照: 同池每日随机3只 hold1 (剥离选股能力, 只看市场漂移)

输出: hot_chase.json
"""
import json
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

BUY_FEE = 0.00025
SELL_FEE = 0.00025 + 0.0005
NSLOTS = 3
CTX = ssl.create_default_context()


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "ignore")


def sina_kline(code, n=600):
    sym = ("sh" if code.startswith("6") else "sz") + code
    url = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={sym}&scale=240&ma=no&datalen={n}")
    rows = json.loads(http_get(url))
    return {
        "dates": [r["day"] for r in rows],
        "open": [float(r["open"]) for r in rows],
        "high": [float(r["high"]) for r in rows],
        "low": [float(r["low"]) for r in rows],
        "close": [float(r["close"]) for r in rows],
        "volume": [float(r["volume"]) for r in rows],
    }


def load_universe():
    uni = json.load(open("universe.json", encoding="utf-8"))
    return {u["code"]: u["name"] for u in uni}


def fetch_all(codes):
    out = {}

    def one(c):
        try:
            return c, sina_kline(c, 600)
        except Exception:
            return c, None

    with ThreadPoolExecutor(max_workers=8) as ex:
        for c, k in ex.map(one, codes):
            if k and len(k["close"]) > 60:
                out[c] = k
    return out


def build_calendar(data):
    days = set()
    for k in data.values():
        days |= set(k["dates"])
    return sorted(days)


def align(k, dates):
    idx = {d: i for i, d in enumerate(k["dates"])}
    o = [k["open"][idx[d]] if d in idx else None for d in dates]
    c = [k["close"][idx[d]] if d in idx else None for d in dates]
    v = [k["volume"][idx[d]] if d in idx else None for d in dates]
    return o, c, v


def ma(x, n):
    out = [None] * len(x)
    s, q = 0.0, []
    for i, val in enumerate(x):
        if val is None:
            continue
        q.append(val); s += val
        if len(q) > n:
            s -= q.pop(0)
        if len(q) == n:
            out[i] = s / n
    return out


def signals_hot(dates, al, topn=3, min_chg=0.05, vol_ratio=None):
    """al: {code:(opens, closes, vols)}; 返回 signals[i] = 候选列表(按涨幅降序)"""
    sigs = [[] for _ in dates]
    vols_ma = {c: ma(al[c][2], 5) for c in al}
    for i in range(6, len(dates)):
        cands = []
        for c in al:
            _, cl, vl = al[c]
            if not (cl[i] and cl[i - 1]):
                continue
            chg = cl[i] / cl[i - 1] - 1
            if chg < min_chg:
                continue
            if vol_ratio is not None:
                vm = vols_ma[c][i - 1] if i - 1 >= 0 else None
                if not vm or not vl[i] or vl[i] < vm * vol_ratio:
                    continue
            cands.append((chg, c))
        cands.sort(reverse=True)
        sigs[i] = [c for _, c in cands[:topn]]
    return sigs


def signals_dip(dates, al, topn=3, max_chg=-0.05):
    """跌幅榜抄底(反向): 当日跌幅超5%的股按跌幅排序"""
    sigs = [[] for _ in dates]
    for i in range(6, len(dates)):
        cands = []
        for c in al:
            _, cl, _ = al[c]
            if not (cl[i] and cl[i - 1]):
                continue
            chg = cl[i] / cl[i - 1] - 1
            if chg > max_chg:
                continue
            cands.append((chg, c))
        cands.sort()
        sigs[i] = [c for _, c in cands[:topn]]
    return sigs


def signals_random(dates, al, n=3, seed=7):
    import random
    rnd = random.Random(seed)
    sigs = [[] for _ in dates]
    codes = list(al)
    for i in range(6, len(dates)):
        avail = [c for c in codes if al[c][1][i] and al[c][0][i]]
        rnd.shuffle(avail)
        sigs[i] = avail[:n]
    return sigs


def sim(dates, al, signals, hold=1, nslots=NSLOTS, max_gap=0.095):
    budget = 1.0 / nslots
    slots = [{"cash": budget, "shares": 0.0, "code": None, "bp": 0.0, "sell_i": None,
              "bi": 0} for _ in range(nslots)]
    nav, trades = [], []
    skipped_gap = 0
    for i in range(len(dates)):
        for s in slots:
            if s["shares"] > 0 and s["sell_i"] is not None and s["sell_i"] <= i:
                o = al[s["code"]][0][i]
                if o:
                    trades.append({"ret": o * (1 - SELL_FEE) / s["bp"] - 1,
                                   "bi": s["bi"], "si": i, "code": s["code"]})
                    s["cash"] = s["shares"] * o * (1 - SELL_FEE)
                    s["shares"], s["code"], s["sell_i"] = 0.0, None, None
                else:
                    s["sell_i"] = i + 1
        if i > 0:
            for code in (signals[i - 1] or []):
                free = next((s for s in slots if s["shares"] == 0), None)
                if free is None:
                    break
                if code in [s["code"] for s in slots]:
                    continue
                o = al[code][0][i]
                prev_c = al[code][1][i - 1]
                if not o or not prev_c:
                    continue
                if o / prev_c - 1 >= max_gap:      # 次日竞价接近涨停, 买不进
                    skipped_gap += 1
                    continue
                free.update(shares=free["cash"] * (1 - BUY_FEE) / o, code=code,
                            bp=o, bi=i, sell_i=i + hold, cash=0.0)
        total = sum(s["cash"] for s in slots)
        for s in slots:
            if s["shares"] > 0:
                c = al[s["code"]][1][i]
                total += s["shares"] * (c if c else s["bp"])
        nav.append(total)
    rets = [t["ret"] for t in trades]
    wins = sum(1 for r in rets if r > 0)
    nav = [v for v in nav if v is not None]
    peak, mdd = nav[0], 0.0
    for v in nav:
        peak = max(peak, v); mdd = min(mdd, v / peak - 1)
    yrs = len(nav) / 244
    return {
        "totalRet": round(nav[-1] - 1, 4),
        "annRet": round((nav[-1]) ** (1 / yrs) - 1, 4) if yrs > 0 else None,
        "mdd": round(mdd, 4),
        "trades": len(trades),
        "winRate": round(wins / len(rets), 4) if rets else None,
        "avgRet": round(sum(rets) / len(rets), 4) if rets else None,
        "skippedGap": skipped_gap,
    }


def main():
    uni = load_universe()
    print(f"[1/4] 抓取 {len(uni)} 只股票带量日线...")
    data = fetch_all(list(uni))
    print(f"   成功 {len(data)}/{len(uni)}")
    if len(data) < 30:
        raise SystemExit("数据不足")
    dates = build_calendar(data)
    al = {c: align(data[c], dates) for c in data}
    print(f"   日历 {dates[0]} ~ {dates[-1]} ({len(dates)} 交易日)")

    print("[2/4] 生成信号...")
    sig_hot = signals_hot(dates, al, topn=3, min_chg=0.05)
    sig_hot_vol = signals_hot(dates, al, topn=3, min_chg=0.05, vol_ratio=1.5)
    sig_rand = signals_random(dates, al, 3)
    sig_dip = signals_dip(dates, al, 3, -0.05)

    print("[3/4] 回测变体...")
    cases = [
        ("hot1", "热点Top3 持1日", "当日涨幅Top3(>5%) → 次日开盘买 → 持1日卖", sig_hot, 1),
        ("hot2", "热点Top3 持2日", "同上, 持2日卖", sig_hot, 2),
        ("hot1_vol", "热点+放量 持1日", "涨幅>5% 且 量>5日均量1.5倍", sig_hot_vol, 1),
        ("hot2_vol", "热点+放量 持2日", "同上, 持2日卖", sig_hot_vol, 2),
        ("rand1", "随机3只 持1日(对照)", "每日随机买3只, 剥离选股能力", sig_rand, 1),
        ("dip1", "跌幅榜抄底 持1日(反向)", "当日跌幅<-5% 的股, 次日开盘买, 持1日", sig_dip, 1),
        ("dip2", "跌幅榜抄底 持2日(反向)", "同上, 持2日", sig_dip, 2),
    ]
    rows = []
    for cid, name, desc, sig, hold in cases:
        m = sim(dates, al, sig, hold=hold)
        rows.append({"id": cid, "name": name, "desc": desc, "hold": hold, "metrics": m})
        print(f"   {name}: 累计{m['totalRet']*100:+.1f}% 年化{(m['annRet'] or 0)*100:+.1f}% "
              f"回撤{m['mdd']*100:.1f}% 笔数{m['trades']} 胜率{(m['winRate'] or 0)*100:.1f}% "
              f"单笔{(m['avgRet'] or 0)*100:+.2f}% 买不进{m['skippedGap']}")

    print("[4/4] 输出...")
    best = max(rows, key=lambda r: r["metrics"]["totalRet"])
    hot1 = next(r for r in rows if r["id"] == "hot1")["metrics"]
    rand1 = next(r for r in rows if r["id"] == "rand1")["metrics"]
    verdict = (
        f"热点追涨持1日单笔均值 {hot1['avgRet']*100:+.2f}%、胜率 {hot1['winRate']*100:.1f}%、"
        f"累计 {hot1['totalRet']*100:+.1f}%；同池随机买持1日单笔 {rand1['avgRet']*100:+.2f}%。"
        + ("热点识别没有跑赢随机, 说明'每天追热点'在日线级别不成立。"
           if (hot1["avgRet"] or 0) <= (rand1["avgRet"] or 0) + 0.001
           else f"热点组单笔超额 {(hot1['avgRet']-rand1['avgRet'])*100:+.2f}%, 但需扣除滑点/冲击成本后再判断。")
    )
    out = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "range": [dates[0], dates[-1]], "pool": len(data),
           "variants": rows, "verdict": verdict}
    json.dump(out, open("hot_chase.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("saved hot_chase.json")
    print("VERDICT:", verdict)


if __name__ == "__main__":
    main()
