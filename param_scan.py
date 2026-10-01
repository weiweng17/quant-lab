# -*- coding: utf-8 -*-
"""参数寻优: 样本内(前60%)选最优参数 -> 样本外(后40%)验证, 防过拟合 -> param_scan.json"""
import json
import backtest as bt

# 各策略参数网格: (label, params)
GRIDS = {
    "ma":   [("MA5/20(当前)", (5, 20)), ("MA5/60", (5, 60)), ("MA10/30", (10, 30)),
             ("MA10/60", (10, 60)), ("MA20/60", (20, 60)), ("MA3/10", (3, 10))],
    "macd": [("12/26/9(当前)", (12, 26, 9)), ("6/13/5", (6, 13, 5)), ("12/26/5", (12, 26, 5)),
             ("19/39/9", (19, 39, 9)), ("5/35/5", (5, 35, 5)), ("8/21/5", (8, 21, 5))],
    "rsi":  [("RSI14·30/70(当前)", (14, 30, 70)), ("RSI7·30/70", (7, 30, 70)), ("RSI14·20/80", (14, 20, 80)),
             ("RSI21·30/70", (21, 30, 70)), ("RSI14·40/60", (14, 40, 60)), ("RSI21·25/75", (21, 25, 75))],
    "boll": [("BOLL20·2(当前)", (20, 2.0)), ("BOLL20·2.5", (20, 2.5)), ("BOLL20·1.5", (20, 1.5)),
             ("BOLL30·2", (30, 2.0)), ("BOLL15·2", (15, 2.0)), ("BOLL10·2", (10, 2.0))],
    "mom":  [("20日(当前)", (20,)), ("10日", (10,)), ("30日", (30,)), ("40日", (40,)), ("60日", (60,))],
    "kdj":  [("KDJ9·20/80(当前)", (9, 20, 80)), ("KDJ14·20/80", (14, 20, 80)), ("KDJ9·30/70", (9, 30, 70)),
             ("KDJ14·30/70", (14, 30, 70)), ("KDJ5·20/80", (5, 20, 80))],
}
NAMES = {"ma": "双均线", "macd": "MACD", "rsi": "RSI反转", "boll": "布林带", "mom": "动量", "kdj": "KDJ金叉"}


def sig_ma(c, args):
    f, s = args
    fv, sv = bt.sma(c, f), bt.sma(c, s)
    out = [None] * len(c)
    for i in range(len(c)):
        if fv[i] is not None and sv[i] is not None:
            out[i] = 1 if fv[i] > sv[i] else 0
    return out


def sig_macd(c, args):
    f, s, g = args
    dif, dea = bt.macd(c, f, s, g)
    out = [None] * len(c)
    for i in range(len(c)):
        if dif[i] is not None and dea[i] is not None:
            out[i] = 1 if dif[i] > dea[i] else 0
    return out


def sig_rsi(c, args):
    n, lo, hi = args
    r = bt.rsi(c, n)
    out = [None] * len(c)
    pos = 0
    for i in range(len(c)):
        if r[i] is not None:
            if r[i] < lo:
                pos = 1
            elif r[i] > hi:
                pos = 0
            out[i] = pos
    return out


def sig_boll(c, args):
    n, k = args
    up, mid, lo = bt.boll(c, n, k)
    out = [None] * len(c)
    pos = 0
    for i in range(len(c)):
        if lo[i] is not None:
            if c[i] < lo[i]:
                pos = 1
            elif c[i] > mid[i]:
                pos = 0
            out[i] = pos
    return out


def sig_mom(c, args):
    n = args[0]
    out = [None] * len(c)
    for i in range(n, len(c)):
        out[i] = 1 if c[i] > c[i - n] else 0
    return out


def sig_kdj(c, args):
    n, lo, hi = args
    out = [None] * len(c)
    pos, K, D = 0, 50.0, 50.0
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
            out[i] = pos
    return out


BUILDERS = {"ma": sig_ma, "macd": sig_macd, "rsi": sig_rsi,
            "boll": sig_boll, "mom": sig_mom, "kdj": sig_kdj}


def run_window(closes):
    """返回 {label: (ann, sharpe, mdd, beatBase)}"""
    # 基准(买入持有)
    bh_eq, _ = bt.run_long_short(closes, [1] * len(closes))
    bh_ann = bt.metrics(None, closes, bh_eq, [])["annRet"]
    out = {}
    for sid, grid in GRIDS.items():
        fn = BUILDERS[sid]
        for label, args in grid:
            sig = fn(closes, args)
            eq, trades = bt.run_long_short(closes, sig)
            m = bt.metrics(None, closes, eq, trades)
            out[(sid, label)] = (m["annRet"], m["sharpe"], m["mdd"], m["annRet"] > bh_ann)
    return out


def main():
    with open("universe.json", encoding="utf-8") as f:
        universe = json.load(f)

    # 每窗口每参数累计: [annSum, sharpeSum, mddSum, beatCnt, count]
    agg = {sid: {"is": {lab: [0.0, 0.0, 0.0, 0, 0] for lab, _ in GRIDS[sid]},
                 "oos": {lab: [0.0, 0.0, 0.0, 0, 0] for lab, _ in GRIDS[sid]}}
           for sid in GRIDS}
    for sym in universe:
        c = sym["close"]
        if not c or len(c) < 100:
            continue
        is_end = int(len(c) * 0.6)
        for win_name, win in (("is", c[:is_end]), ("oos", c[is_end:])):
            if len(win) < 60:
                continue
            res = run_window(win)
            for sid in GRIDS:
                for label, _ in GRIDS[sid]:
                    ann, sharpe, mdd, beat = res[(sid, label)]
                    a = agg[sid][win_name][label]
                    a[0] += ann
                    a[1] += sharpe
                    a[2] += mdd
                    a[3] += 1 if beat else 0
                    a[4] += 1

    rows = []
    for sid, grid in GRIDS.items():
        is_rows = {}
        for label, _ in grid:
            v = agg[sid]["is"][label]
            is_rows[label] = v[0] / max(v[4], 1)
        best = max(grid, key=lambda x: is_rows[x[0]])
        bestL = best[0]
        curL = next(l for l, _ in grid if "(当前)" in l)
        bv = agg[sid]["oos"][bestL]
        cv = agg[sid]["oos"][curL]
        rows.append({
            "id": sid, "name": NAMES[sid],
            "current": curL, "best": bestL,
            "bestIsAnn": round(is_rows[bestL], 5),
            "bestOosAnn": round(bv[0] / max(bv[4], 1), 5),
            "bestOosSharpe": round(bv[1] / max(bv[4], 1), 3),
            "bestOosMdd": round(bv[2] / max(bv[4], 1), 4),
            "bestOosBeat": bv[3],
            "curOosAnn": round(cv[0] / max(cv[4], 1), 5),
            "curOosSharpe": round(cv[1] / max(cv[4], 1), 3),
            "curOosMdd": round(cv[2] / max(cv[4], 1), 4),
            "curOosBeat": cv[3],
            "n": max(bv[4], 1),
        })
        d = rows[-1]
        diff = d["bestOosAnn"] - d["curOosAnn"]
        print(f"{d['name']:<6} 样本内最优[{d['best']}] 样本外年化{d['bestOosAnn']*100:6.1f}% "
              f"(当前[{d['current']}] {d['curOosAnn']*100:6.1f}%, 差{diff*100:+.1f}pp) "
              f"夏普{d['bestOosSharpe']:.2f} 跑赢基准{d['bestOosBeat']}/{d['n']}")

    with open("param_scan.json", "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "universe": len(universe)}, f,
                  ensure_ascii=False, separators=(",", ":"))
    print("saved param_scan.json")


if __name__ == "__main__":
    main()
