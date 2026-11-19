# -*- coding: utf-8 -*-
"""策略实验室: 替代「动量追涨」的新策略族回测验证
背景: 跟踪数据显示动量选股 T+20 均值 -8.7%(超额 -2.6%), 熔断已触发。
本脚本用统一口径(open_t1 + 手续费)对比:

  mom         动量Top3(现状等价, 无择时)      —— 问题基准
  mom_gate    动量Top3 + 上证MA20开关        —— 浅层择时
  os_gate     超跌反弹(RSI6<25) + MA20开关   —— 均值回归
  etf_rot     行业ETF动量轮动(持币防守)      —— 轮动对照
  toggle_cyb  风险开关: 创业板ETF/黄金ETF    —— 主推(上证>MA20持创业板, 否则黄金)
  toggle_1000 风险开关: 中证1000ETF/黄金ETF
  toggle_300  风险开关: 沪深300ETF/黄金ETF   —— 保守档
  bh300       沪深300买入持有(基准)

参数: 上证收盘 vs MA20, 每5个交易日收盘检查, 次日开盘执行(open_t1)。
数据: Sina 日线 1200 根(约2021-12至今, 覆盖完整牛熊)。
输出: strategy_lab.json
"""
import json
import ssl
import urllib.request
from datetime import datetime

BUY_FEE = 0.00025
SELL_FEE = 0.00025 + 0.0005
HOLD = 5
NSLOTS = 3
KLINE_LEN = 1200          # 覆盖约 2021-12 至今
GATE_MA = 20              # 大盘开关均线
CHECK_EVERY = 5           # 开关检查频率(交易日)
ETF_POOL = [
    ("sh510300", "沪深300ETF"),
    ("sh512100", "中证1000ETF"),
    ("sz159915", "创业板ETF"),
    ("sh512000", "券商ETF"),
    ("sh512480", "半导体ETF"),
    ("sh512660", "军工ETF"),
    ("sh512010", "医药ETF"),
    ("sz159928", "消费ETF"),
    ("sh516160", "新能源车ETF"),
    ("sh518880", "黄金ETF"),
]
GOLD = "sh518880"
CTX = ssl.create_default_context()


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn",
    })
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode("utf-8", "ignore")


def sina_kline(sym, n=KLINE_LEN):
    url = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={sym}&scale=240&ma=no&datalen={n}")
    out = {}
    for row in json.loads(http_get(url)):
        out[row["day"]] = (float(row["open"]), float(row["close"]))
    return out


# ---------- 指标 ----------

def sma_series(x, n):
    out = [None] * len(x)
    s, q = 0.0, []
    for i, v in enumerate(x):
        if v is None:
            q.clear(); s = 0.0; continue
        q.append(v); s += v
        if len(q) > n:
            s -= q.pop(0)
        if len(q) == n:
            out[i] = s / n
    return out


def rsi(closes, n=6):
    out = [None] * len(closes)
    gains, losses = [], []
    for i in range(1, len(closes)):
        c0, c1 = closes[i - 1], closes[i]
        if c0 is None or c1 is None:
            gains.append(0.0); losses.append(0.0); continue
        ch = c1 - c0
        gains.append(max(ch, 0.0)); losses.append(max(-ch, 0.0))
        if i >= n:
            g = sum(gains[i - n:i]) / n
            l = sum(losses[i - n:i]) / n
            out[i] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    return out


# ---------- 个股组合模拟(槽数轮动, open_t1) ----------

def sim_slots(dates, px, signals, hold=HOLD, nslots=NSLOTS):
    budget = 1.0 / nslots
    slots = [{"cash": budget, "shares": 0.0, "code": None, "bp": 0.0, "bi": 0, "sell_i": None}
             for _ in range(nslots)]
    nav, trades = [], []
    for i in range(len(dates)):
        for s in slots:
            if s["shares"] > 0 and s["sell_i"] is not None and s["sell_i"] <= i:
                o = px[s["code"]][0][i]
                if o:
                    trades.append({"ret": o * (1 - SELL_FEE) / s["bp"] - 1,
                                   "bi": s["bi"], "si": i, "code": s["code"]})
                    s["cash"], s["shares"], s["code"], s["sell_i"] = \
                        s["shares"] * o * (1 - SELL_FEE), 0.0, None, None
                else:
                    s["sell_i"] = i + 1
        if i > 0:
            for code in (signals[i - 1] or []):
                free = next((s for s in slots if s["shares"] == 0), None)
                if free is None:
                    break
                if code in [s["code"] for s in slots]:
                    continue
                o = px[code][0][i]
                if o:
                    free.update(shares=free["cash"] * (1 - BUY_FEE) / o, code=code,
                                bp=o, bi=i, sell_i=i + hold, cash=0.0)
        total = sum(s["cash"] for s in slots)
        for s in slots:
            if s["shares"] > 0:
                c = px[s["code"]][1][i]
                total += s["shares"] * (c if c else s["bp"])
        nav.append(total)
    return nav, trades


def momentum_signals(dates, closes, gate, topk=6):
    sigs = [[] for _ in dates]
    codes = list(closes)
    for i in range(21, len(dates)):
        cands = []
        for c in codes:
            cl = closes[c]
            if cl[i] and cl[i - 20]:
                m = cl[i] / cl[i - 20] - 1
                if m > 0:
                    cands.append((m, c))
        cands.sort(reverse=True)
        sigs[i] = [c for _, c in cands[:topk]]
    return apply_gate(sigs, gate)


def oversold_signals(dates, closes, rsi_vals, gate, max_rsi=25.0, topk=6):
    sigs = [[] for _ in dates]
    codes = list(closes)
    for i in range(21, len(dates)):
        cands = []
        for c in codes:
            r = rsi_vals[c][i]
            if r is not None and r < max_rsi:
                cands.append((r, c))
        cands.sort()
        sigs[i] = [c for _, c in cands[:topk]]
    return apply_gate(sigs, gate)


def apply_gate(sigs, gate):
    if gate is None:
        return sigs
    return [[] if gate[i] is False else s for i, s in enumerate(sigs)]


# ---------- ETF 风险开关 / 轮动 ----------

def sim_toggle(dates, al, strong_sym, gate):
    """风险开关: gate[i]为True持strong_sym, False持黄金, None观望不动"""
    cash, shares, cur, pending = 1.0, 0.0, None, None
    nav, trades, switches = [], [], []
    for i in range(len(dates)):
        if pending is not None and i > 0:
            o_new = al[pending][0][i]
            if o_new:
                if cur is not None and cur["sym"] != pending:
                    o_old = al[cur["sym"]][0][i]
                    if o_old:
                        trades.append({"ret": (o_old * (1 - SELL_FEE)) / cur["bp"] - 1,
                                       "si": i, "code": cur["sym"]})
                        cash = shares * o_old * (1 - SELL_FEE)
                        shares, cur = 0.0, None
                if cur is None:
                    shares = cash * (1 - BUY_FEE) / o_new
                    cash = 0.0
                    cur = {"sym": pending, "bp": o_new, "bi": i}
                    switches.append({"date": dates[i], "to": pending})
                pending = None
        if i % CHECK_EVERY == 0 and i >= GATE_MA and gate[i] is not None:
            target = strong_sym if gate[i] else GOLD
            if cur is None or cur["sym"] != target:
                pending = target
        hv = 0.0
        if cur:
            c = al[cur["sym"]][1][i]
            hv = shares * (c if c else cur["bp"])
        nav.append(cash + hv)
    return nav, trades, switches


def sim_rotation(dates, al, gate, lookback=20, fallback=None):
    """行业ETF动量轮动: 每5日选 lookback 动量最强且在自身MA20上方的ETF"""
    cash, shares, cur, pending = 1.0, 0.0, None, None
    nav, trades = [], []
    for i in range(len(dates)):
        if pending is not None and i > 0:
            tgt = None if pending == "CASH" else pending
            if tgt is None:
                if cur is not None:
                    o = al[cur["sym"]][0][i]
                    if o:
                        trades.append({"ret": (o * (1 - SELL_FEE)) / cur["bp"] - 1,
                                       "si": i, "code": cur["sym"]})
                        cash = shares * o * (1 - SELL_FEE)
                        shares, cur = 0.0, None
                        pending = None
            else:
                o_new = al[tgt][0][i]
                if o_new:
                    if cur is not None and cur["sym"] != tgt:
                        o_old = al[cur["sym"]][0][i]
                        if o_old:
                            trades.append({"ret": (o_old * (1 - SELL_FEE)) / cur["bp"] - 1,
                                           "si": i, "code": cur["sym"]})
                            cash = shares * o_old * (1 - SELL_FEE)
                            shares, cur = 0.0, None
                    if cur is None:
                        shares = cash * (1 - BUY_FEE) / o_new
                        cash = 0.0
                        cur = {"sym": tgt, "bp": o_new, "bi": i}
                    pending = None
        if i % CHECK_EVERY == 0 and i >= lookback:
            blocked = gate[i] is False
            best, bm = None, None
            if not blocked:
                for sym in al:
                    cl = al[sym][1]
                    if cl[i] and cl[i - lookback]:
                        m = cl[i] / cl[i - lookback] - 1
                        ma = sma_series(cl, 20)
                        if m > 0 and ma[i] and cl[i] > ma[i]:
                            if bm is None or m > bm:
                                best, bm = sym, m
            if best is None and fallback is not None and not blocked:
                best = fallback
            target = best if best else "CASH"
            now = cur["sym"] if cur else "CASH"
            if target != now:
                pending = target
        hv = 0.0
        if cur:
            c = al[cur["sym"]][1][i]
            hv = shares * (c if c else cur["bp"])
        nav.append(cash + hv)
    return nav, trades


# ---------- 统计 ----------

def metrics(dates, nav, trades):
    total = nav[-1] - 1
    yrs = max(len(dates) / 244.0, 0.25)
    ann = (1 + total) ** (1 / yrs) - 1 if total > -1 else -1
    peak, mdd = nav[0], 0.0
    for v in nav:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    rets = [t["ret"] for t in trades]
    wins = sum(1 for r in rets if r > 0)
    return {"totalRet": round(total, 4), "annRet": round(ann, 4), "mdd": round(mdd, 4),
            "trades": len(trades),
            "winRate": round(wins / len(rets), 4) if rets else None,
            "avgRet": round(sum(rets) / len(rets), 4) if rets else None}


def main():
    print("[1/5] 拉取指数与ETF日线(Sina, 1200根)...")
    idx = sina_kline("sh000001")
    etf_px, etf_meta = {}, {}
    for sym, name in ETF_POOL:
        try:
            etf_px[sym] = sina_kline(sym)
            etf_meta[sym] = name
            print(f"   {name} ok ({len(etf_px[sym])} bars)")
        except Exception as e:
            print(f"   {name} 失败: {e}")
    if len(etf_px) < 5:
        raise SystemExit("ETF 数据源失败过多, 终止")

    print("[2/5] 构建日历与对齐序列...")
    dates = sorted(set(idx) | set().union(*[set(k) for k in etf_px.values()]))

    def align(kl):
        return ([kl[d][0] if d in kl else None for d in dates],
                [kl[d][1] if d in kl else None for d in dates])

    al = {sym: align(etf_px[sym]) for sym in etf_px}
    _, idx_c = align(idx)

    gate_f = sma_series(idx_c, GATE_MA)
    gate = [None if (idx_c[i] is None or gate_f[i] is None) else idx_c[i] > gate_f[i]
            for i in range(len(dates))]

    # 个股池(universe.json, 当前强势池63只)
    universe = json.load(open("universe.json", encoding="utf-8"))
    stock_px = {}
    for sym in universe:
        kl = {d: (o, c) for d, o, c in zip(sym["dates"], sym["open"], sym["close"])}
        stock_px[sym["code"]] = align(kl)
    closes_by_code = {c: stock_px[c][1] for c in stock_px}

    print("[3/5] 个股策略回测...")
    rsi_vals = {c: rsi(closes_by_code[c], 6) for c in closes_by_code}
    specs = [
        ("mom", "动量Top3(现状等价)", "全池20日涨幅排名 · 3仓轮动 · 持5日 · 无择时",
         lambda: sim_slots(dates, stock_px, momentum_signals(dates, closes_by_code, None))),
        ("mom_gate", "动量Top3 + 大盘开关", "同上, 上证<MA20禁止开仓",
         lambda: sim_slots(dates, stock_px, momentum_signals(dates, closes_by_code, gate))),
        ("os_gate", "超跌反弹 + 大盘开关", "RSI6<25超卖排序 · 持5日 · 上证<MA20禁开仓",
         lambda: sim_slots(dates, stock_px, oversold_signals(dates, closes_by_code, rsi_vals, gate))),
    ]
    results = []
    for sid, name, desc, fn in specs:
        nav, trades = fn()
        m = metrics(dates, nav, trades)
        results.append({"id": sid, "name": name, "desc": desc, "metrics": m,
                        "nav": [round(v, 5) for v in nav]})
        print(f"   {name}: 累计{m['totalRet']*100:+.1f}% 回撤{m['mdd']*100:.1f}% "
              f"笔数{m['trades']} 胜率{m['winRate']}")

    print("[4/5] ETF 开关/轮动回测...")
    for sid, name, desc, fn in [
        ("etf_rot", "行业ETF动量轮动", "9只行业ETF每5日轮动 · 持最强且在MA20上方 · 全弱持币",
         lambda: sim_rotation(dates, al, gate)),
        ("toggle_cyb", "风险开关: 创业板/黄金 ★主推", f"上证>MA{GATE_MA}持创业板ETF, 否则切黄金ETF, 每{CHECK_EVERY}日检查",
         lambda: sim_toggle(dates, al, "sz159915", gate)),
        ("toggle_1000", "风险开关: 中证1000/黄金", f"上证>MA{GATE_MA}持中证1000ETF, 否则切黄金ETF",
         lambda: sim_toggle(dates, al, "sh512100", gate)),
        ("toggle_300", "风险开关: 沪深300/黄金(保守)", f"上证>MA{GATE_MA}持沪深300ETF, 否则切黄金ETF",
         lambda: sim_toggle(dates, al, "sh510300", gate)),
    ]:
        out = fn()
        if len(out) == 3:
            nav, trades, switches = out
        else:
            nav, trades = out
            switches = []
        m = metrics(dates, nav, trades)
        results.append({"id": sid, "name": name, "desc": desc, "metrics": m,
                        "nav": [round(v, 5) for v in nav],
                        "switches": switches[-10:]})
        print(f"   {name}: 累计{m['totalRet']*100:+.1f}% 年化{m['annRet']*100:+.1f}% "
              f"回撤{m['mdd']*100:.1f}% 换手{m['trades']}")

    # 基准: 沪深300 B&H (缺失日前向填充, 前缀缺失跳过)
    _, hs_c = align(etf_px["sh510300"])
    bh_c, lastv, first_i = [], None, None
    for i, v in enumerate(hs_c):
        if v is not None:
            if first_i is None:
                first_i = i
            lastv = v
        bh_c.append(lastv)
    base = bh_c[first_i]
    nav_bh = [None] * first_i + [round(v / base, 5) for v in bh_c[first_i:]]
    m_bh = metrics(dates[first_i:], nav_bh[first_i:], [])
    results.append({"id": "bh300", "name": "沪深300买入持有(基准)", "desc": "被动持有对照",
                    "metrics": m_bh, "nav": nav_bh})
    print(f"   基准B&H300: 累计{m_bh['totalRet']*100:+.1f}% 回撤{m_bh['mdd']*100:.1f}%")

    print("[5/5] 当前状态与结论...")
    i = len(dates) - 1
    etf_rank = []
    for sym in al:
        cl = al[sym][1]
        ma = sma_series(cl, 20)
        mom = cl[i] / cl[i - 20] - 1 if cl[i] and cl[i - 20] else None
        etf_rank.append({"code": sym, "name": etf_meta[sym], "close": cl[i],
                         "mom20": round(mom, 4) if mom is not None else None,
                         "aboveMa20": bool(cl[i] and ma[i] and cl[i] > ma[i])})
    etf_rank.sort(key=lambda x: -(x["mom20"] or -9))

    def g(sid):
        return next(r for r in results if r["id"] == sid)["metrics"]

    best = max([r for r in results if r["id"].startswith("toggle")],
               key=lambda r: r["metrics"]["annRet"])
    verdict = (
        f"动量追涨(现状等价)同期累计 {g('mom')['totalRet']*100:+.1f}%, 而风险开关策略 "
        f"[{best['name'].replace(' ★主推','')}] 累计 {best['metrics']['totalRet']*100:+.1f}% / "
        f"年化 {best['metrics']['annRet']*100:+.1f}% / 回撤 {best['metrics']['mdd']*100:.1f}%。"
        f"当前大盘{'在MA20上方→开关策略应持进攻腿(创业板/1000)' if gate[i] else '在MA20下方→开关策略应持黄金ETF防守'}。"
    )

    out = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "range": [dates[0], dates[-1]],
        "gateMa": GATE_MA, "checkEvery": CHECK_EVERY,
        "regime": {"indexClose": idx_c[i], "ma20": round(gate_f[i], 2) if gate_f[i] else None,
                   "inMarket": bool(gate[i])},
        "etfRank": etf_rank,
        "strategies": results,
        "verdict": verdict,
    }
    with open("strategy_lab.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("saved strategy_lab.json")
    print("VERDICT:", verdict)


if __name__ == "__main__":
    main()
