# -*- coding: utf-8 -*-
"""回测引擎：经典技术指标策略对比 -> results.json"""
import json
import math

INIT_CASH = 100_000.0
BUY_FEE = 0.00025    # 买入佣金 万2.5
SELL_FEE = 0.00025 + 0.0005  # 卖出佣金 + 印花税(0.05%)

# ---------- 指标 ----------

def sma(x, n):
    out = [None] * len(x)
    s = 0.0
    for i, v in enumerate(x):
        s += v
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out

def ema(x, n):
    out = [None] * len(x)
    k = 2.0 / (n + 1)
    prev = None
    for i, v in enumerate(x):
        prev = v if prev is None else v * k + prev * (1 - k)
        out[i] = prev
    return out

def rsi(closes, n=14):
    out = [None] * len(closes)
    gains, losses = 0.0, 0.0
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g, d = max(ch, 0.0), max(-ch, 0.0)
        if i <= n:
            gains += g; losses += d
            if i == n:
                ag, al = gains / n, losses / n
                out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
        else:
            ag = (ag * (n - 1) + g) / n
            al = (al * (n - 1) + d) / n
            out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out

def macd(closes, fast=12, slow=26, sig=9):
    ef, es = ema(closes, fast), ema(closes, slow)
    dif = [a - b for a, b in zip(ef, es)]
    dea = ema(dif, sig)
    return dif, dea

def boll(closes, n=20, k=2.0):
    mid = sma(closes, n)
    up, lo = [None] * len(closes), [None] * len(closes)
    for i in range(n - 1, len(closes)):
        m = mid[i]
        var = sum((closes[j] - m) ** 2 for j in range(i - n + 1, i + 1)) / n
        sd = math.sqrt(var)
        up[i], lo[i] = m + k * sd, m - k * sd
    return up, mid, lo

# ---------- 回测核心 ----------

def run_long_short(closes, signals):
    """signals[i] in {None, 1(持有), 0(空仓)}，收盘价成交，全仓进出。"""
    n = len(closes)
    cash, shares = INIT_CASH, 0.0
    equity = [0.0] * n
    trades = []          # {bi, si, bp, sp, ret}
    open_trade = None
    last_sig = 0
    for i in range(n):
        sig = signals[i]
        # 指标类策略 sig[0] 恒为 None, 该条件只对买入持有(首日建仓)放行 i=0
        if sig is not None and sig != last_sig:
            if sig == 1 and cash > 0:
                shares = cash * (1 - BUY_FEE) / closes[i]
                cash = 0.0
                open_trade = {"bi": i, "bp": closes[i]}
            elif sig == 0 and shares > 0:
                cash = shares * closes[i] * (1 - SELL_FEE)
                shares = 0.0
                trades.append({
                    "bi": open_trade["bi"], "si": i,
                    "bp": open_trade["bp"], "sp": closes[i],
                    "ret": closes[i] / open_trade["bp"] * (1 - SELL_FEE) - (1 + BUY_FEE),
                })
                open_trade = None
            last_sig = sig
        equity[i] = cash + shares * closes[i]
    # 平掉期末持仓(计入最后一笔, 标记未平仓)
    if open_trade is not None:
        i = n - 1
        trades.append({
            "bi": open_trade["bi"], "si": i, "bp": open_trade["bp"], "sp": closes[i],
            "pnl": None, "ret": closes[i] / open_trade["bp"] * (1 - SELL_FEE) - (1 + BUY_FEE),
            "open": True,
        })
    return equity, trades


def run_grid(closes, grids=10, lookback=120):
    """网格交易：滚动区间上下限分grids格，跌一格买一份，涨一格卖一份，资金等分。"""
    n = len(closes)
    cash = INIT_CASH
    lots = []           # 每份持仓 {idx, price, shares}
    unit_cache = None
    equity = [0.0] * n
    trades = []
    grid_level = None   # 当前所在格位
    for i in range(n):
        # 每隔 lookback 天重算网格区间(用历史数据, 避免未来函数)
        if i % lookback == 0 and i + lookback <= n and i >= 60:
            win = closes[max(0, i - lookback):i]
            if len(win) >= 30:
                lo_p, hi_p = min(win), max(win)
                step = (hi_p - lo_p) / grids
                if step > 0:
                    unit_cache = (lo_p, hi_p, step, cash / grids * 0.999)
        if unit_cache:
            lo_p, hi_p, step, unit_cash = unit_cache
            lvl = math.floor((closes[i] - lo_p) / step)
            lvl = max(0, min(grids, lvl))
            if grid_level is None:
                grid_level = lvl
            while lvl < grid_level and cash >= unit_cash and closes[i] > 0:
                sh = unit_cash * (1 - BUY_FEE) / closes[i]
                lots.append({"price": closes[i], "shares": sh})
                cash -= unit_cash
                trades.append({"bi": i, "si": None, "bp": closes[i], "sp": None})
                grid_level -= 1
            while lvl > grid_level and lots:
                lot = lots.pop(0)   # FIFO 卖出最早一份
                cash += lot["shares"] * closes[i] * (1 - SELL_FEE)
                t = next((t for t in trades if t["si"] is None), None)  # FIFO 配对最早未平仓交易, 与 lot 弹出顺序一致
                if t:
                    t["si"] = i; t["sp"] = closes[i]
                    t["ret"] = closes[i] / t["bp"] * (1 - SELL_FEE) - (1 + BUY_FEE)
                grid_level += 1
        equity[i] = cash + sum(l["shares"] * closes[i] for l in lots)
    # 期末强平统计
    for t in trades:
        if t["si"] is None:
            t["si"] = n - 1; t["sp"] = closes[-1]; t["open"] = True
            t["ret"] = closes[-1] / t["bp"] * (1 - SELL_FEE) - (1 + BUY_FEE)
    return equity, trades


# ---------- 策略定义 ----------

def strat_buy_hold(c):
    return [1] * len(c), []

def strat_ma_cross(c, fast=5, slow=20):
    f, s = sma(c, fast), sma(c, slow)
    sig = [None] * len(c)
    for i in range(len(c)):
        if f[i] is not None and s[i] is not None:
            sig[i] = 1 if f[i] > s[i] else 0
    return sig, []

def strat_macd(c):
    dif, dea = macd(c)
    sig = [None] * len(c)
    for i in range(len(c)):
        if dif[i] is not None and dea[i] is not None:
            sig[i] = 1 if dif[i] > dea[i] else 0
    return sig, []

def strat_rsi(c, n=14, lo=30, hi=70):
    r = rsi(c, n)
    sig = [None] * len(c)
    pos = 0
    for i in range(len(c)):
        if r[i] is not None:
            if r[i] < lo:
                pos = 1
            elif r[i] > hi:
                pos = 0
            sig[i] = pos
    return sig, []

def strat_boll(c, n=20, k=2.0):
    up, mid, lo = boll(c, n, k)
    sig = [None] * len(c)
    pos = 0
    for i in range(len(c)):
        if lo[i] is not None:
            if c[i] < lo[i]:
                pos = 1
            elif c[i] > mid[i]:
                pos = 0
            sig[i] = pos
    return sig, []

def strat_kdj(c, n=9, lo=20, hi=80):
    """KDJ: 低位(K<lo)K上穿D买入, 高位(K>hi)K下穿D卖出"""
    sig = [None] * len(c)
    pos = 0
    K, D = 50.0, 50.0
    for i in range(len(c)):
        if i >= n - 1:
            win = c[i - n + 1:i + 1]
            hh, ll = max(win), min(win)
            rsv = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100.0
            pK, pD = K, D
            K = pK * 2 / 3 + rsv / 3
            D = pD * 2 / 3 + K / 3
            if pK <= pD and K > D and K < lo:
                pos = 1
            elif pK >= pD and K < D and K > hi:
                pos = 0
            sig[i] = pos
    return sig, []

def strat_momentum(c, n=20):
    sig = [None] * len(c)
    for i in range(n, len(c)):
        sig[i] = 1 if c[i] > c[i - n] else 0
    return sig, []

STRATEGIES = [
    {"id": "bh",      "name": "买入持有(基准)", "desc": "期初全仓买入, 一直持有到底", "fn": strat_buy_hold, "grid": False},
    {"id": "ma",      "name": "双均线 MA5/20",   "desc": "金叉(5日上穿20日)买入, 死叉卖出", "fn": strat_ma_cross, "grid": False},
    {"id": "macd",    "name": "MACD 12/26/9",   "desc": "DIF上穿DEA买入, 下穿卖出", "fn": strat_macd, "grid": False},
    {"id": "rsi",     "name": "RSI14 反转",     "desc": "RSI<30超卖买入, RSI>70超买卖出", "fn": strat_rsi, "grid": False},
    {"id": "boll",    "name": "布林带均值回归",  "desc": "跌破下轨买入, 回归中轨卖出", "fn": strat_boll, "grid": False},
    {"id": "mom",     "name": "20日动量",       "desc": "20日涨幅为正持有, 否则空仓", "fn": strat_momentum, "grid": False},
    {"id": "kdj",     "name": "KDJ 低位金叉",    "desc": "K上穿D(超卖区K<20)买入, 下穿(超买区K>80)卖出", "fn": strat_kdj, "grid": False},
    {"id": "grid",    "name": "网格交易 10格",   "desc": "滚动高低点分10格, 跌一格买一份/涨一格卖一份", "fn": None, "grid": True},
]


def metrics(dates, closes, equity, trades):
    n = len(equity)
    total_ret = equity[-1] / INIT_CASH - 1
    years = n / 244.0
    ann = (equity[-1] / INIT_CASH) ** (1 / years) - 1 if years > 0 else 0
    rets = [equity[i] / equity[i - 1] - 1 for i in range(1, n) if equity[i - 1] > 0]
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        vol = math.sqrt(var) * math.sqrt(244)
        sharpe = (mean / math.sqrt(var) * math.sqrt(244)) if var > 0 else 0
    else:   # 样本不足(极短历史): 波动/夏普无意义, 置0避免除零
        vol = sharpe = 0.0
    # 最大回撤
    peak, mdd, mdd_i, mdd_peak_i = equity[0], 0.0, 0, 0
    cur_peak_i = 0
    for i, e in enumerate(equity):
        if e > peak:
            peak = e; cur_peak_i = i
        dd = e / peak - 1
        if dd < mdd:
            mdd = dd; mdd_i = i; mdd_peak_i = cur_peak_i
    calmar = ann / abs(mdd) if mdd < 0 else 0
    closed = [t for t in trades if t.get("ret") is not None]
    wins = [t for t in closed if t["ret"] > 0]
    win_rate = len(wins) / len(closed) if closed else None
    avg_hold = sum(t["si"] - t["bi"] for t in closed) / len(closed) if closed else None
    return {
        "totalRet": total_ret, "annRet": ann, "mdd": mdd,
        "mddStart": mdd_peak_i, "mddEnd": mdd_i,
        "vol": vol, "sharpe": sharpe, "calmar": calmar,
        "trades": len(closed), "winRate": win_rate,
        "avgHold": avg_hold, "finalEquity": equity[-1],
        "openTrades": sum(1 for t in closed if t.get("open")),
    }


def backtest_symbol(sym):
    closes = sym["close"]
    out = []
    for s in STRATEGIES:
        if s["grid"]:
            equity, trades = run_grid(closes)
        else:
            sig, _ = s["fn"](closes)
            equity, trades = run_long_short(closes, sig)
        m = metrics(sym["dates"], closes, equity, trades)
        # 净值曲线降采样: 全保留太长, 1861点其实可控, 保留全部
        nv = [round(e / INIT_CASH, 5) for e in equity]
        # 回撤序列
        peak, dd = nv[0], [0.0]
        for v in nv[1:]:
            peak = max(peak, v)
            dd.append(round(v / peak - 1, 5))
        trade_list = [{
            "bi": t["bi"], "si": t["si"], "bp": round(t["bp"], 2),
            "sp": round(t["sp"], 2) if t.get("sp") else None,
            "ret": round(t["ret"], 4) if t.get("ret") is not None else None,
            "open": bool(t.get("open")),
        } for t in trades]
        out.append({
            "id": s["id"], "name": s["name"], "desc": s["desc"],
            "metrics": m, "nav": nv, "dd": dd, "trades": trade_list,
        })
    return out


def main():
    with open("scan.json", encoding="utf-8") as f:
        scan = json.load(f)
    # 详细回测: 指数 + 推荐股
    results = []
    for sym in scan["kline"]:
        res = backtest_symbol(sym)
        results.append({
            "secid": sym["secid"], "name": sym["name"], "tag": sym["tag"],
            "dates": sym["dates"], "open": sym["open"], "high": sym["high"],
            "low": sym["low"], "close": sym["close"], "volume": sym["volume"],
            "strategies": res,
        })
        best = max(res, key=lambda r: r["metrics"]["annRet"])
        bh = next(r for r in res if r["id"] == "bh")
        print(f"{sym['name']}: 最优[{best['name']}] 年化{best['metrics']['annRet']*100:.1f}% "
              f"回撤{best['metrics']['mdd']*100:.1f}% | 基准年化{bh['metrics']['annRet']*100:.1f}%")

    # 全股票池策略统计: 哪个策略最常跑赢买入持有
    with open("universe.json", encoding="utf-8") as f:
        universe = json.load(f)
    agg = {s["id"]: {"count": 0, "sumAnn": 0.0, "sumMdd": 0.0, "beats": 0,
                     "sumSharpe": 0.0, "wins": 0} for s in STRATEGIES}
    per_symbol = []
    for sym in universe:
        try:
            res = backtest_symbol(sym)
        except Exception:
            continue
        bh_ann = next(r for r in res if r["id"] == "bh")["metrics"]["annRet"]
        row = {"name": sym["name"], "sector": sym.get("sector", ""), "best": None, "bestAnn": None}
        for r in res:
            m = r["metrics"]
            agg[r["id"]]["count"] += 1
            agg[r["id"]]["sumAnn"] += m["annRet"]
            agg[r["id"]]["sumMdd"] += m["mdd"]
            agg[r["id"]]["sumSharpe"] += m["sharpe"]
            if m["annRet"] > bh_ann:
                agg[r["id"]]["beats"] += 1
            wr = m["winRate"] or 0
            agg[r["id"]]["wins"] += wr
            if row["bestAnn"] is None or m["annRet"] > row["bestAnn"]:
                row["best"], row["bestAnn"] = r["name"], m["annRet"]
        row["bestAnn"] = round(row["bestAnn"], 4) if row["bestAnn"] is not None else None
        per_symbol.append(row)
    stats = []
    for s in STRATEGIES:
        a = agg[s["id"]]
        c = max(a["count"], 1)
        stats.append({
            "id": s["id"], "name": s["name"], "desc": s["desc"],
            "avgAnn": a["sumAnn"] / c, "avgMdd": a["sumMdd"] / c,
            "avgSharpe": a["sumSharpe"] / c, "beats": a["beats"],
            "count": a["count"], "avgWinRate": a["wins"] / c,
        })
    stats.sort(key=lambda x: -x["avgAnn"])
    best_id = stats[0]["id"]
    for s in stats:
        s["isBest"] = (s["id"] == best_id)

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump({"detail": results, "stats": stats, "perSymbol": per_symbol},
                  f, ensure_ascii=False, separators=(",", ":"))
    print("\n策略全池统计(平均年化 从高到低):")
    for s in stats:
        print(f"  {s['name']:<12} 年化{s['avgAnn']*100:6.1f}% 回撤{s['avgMdd']*100:6.1f}% "
              f"跑赢基准 {s['beats']}/{s['count']}")
    print("saved results.json")

if __name__ == "__main__":
    main()
