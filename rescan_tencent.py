# -*- coding: utf-8 -*-
"""腾讯数据源收盘定稿重扫(东财断连降级方案)
东财接口不可用时, 用腾讯日K重新计算:
- 三大指数收盘评分
- universe 全股票池收盘信号打分/止损目标
- 收盘推荐列表 (板块结构沿用缓存: universe.json 的 sector 归属)
输出覆盖 scan.json / universe.json (与 scan.py 同结构, 供 backtest/build 使用)
"""
import json
import math
import time
import urllib.request
from datetime import datetime

import scan  # 复用 index_score / stock_score / stop_target / secid_of 等

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
SLEEP = 0.15


def tx_kline(tx_code, n=300):
    """腾讯前复权日K -> 与 scan.kline 同结构 {dates, open, high, low, close, volume}"""
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
           f"?param={tx_code},day,,,{n},qfq")
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=12) as r:
                d = json.loads(r.read().decode("utf-8"))
            node = (d.get("data") or {}).get(tx_code) or {}
            rows = node.get("qfqday") or node.get("day") or []
            if not rows:
                return None
            dates = [x[0] for x in rows]
            o = [float(x[1]) for x in rows]
            c = [float(x[2]) for x in rows]
            h = [float(x[3]) for x in rows]
            l = [float(x[4]) for x in rows]
            v = [int(float(x[5])) for x in rows]
            return {"dates": dates, "open": o, "high": h, "low": l,
                    "close": c, "volume": v}
        except Exception:
            time.sleep(0.8 + attempt * 0.8)
    return None


IDX_TX = {"1.000001": "sh000001", "0.399001": "sz399001",
          "0.399006": "sz399006"}


def to_tx(secid):
    """东财 secid -> 腾讯代码: 指数走映射, 个股 1.603216->sh603216, 0.300859->sz300859"""
    if secid in IDX_TX:
        return IDX_TX[secid]
    mkt, code = secid.split(".")
    return ("sh" if code[0] == "6" else "sz") + code


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ---------- 旧缓存(板块结构) ----------
    old = json.load(open("scan.json", encoding="utf-8"))
    old_uni = json.load(open("universe.json", encoding="utf-8"))
    print(f"缓存: 板块{old['meta']['sectors']}个, 股票池{len(old_uni)}只")

    # ---------- [1/4] 指数收盘评分 ----------
    print("[1/4] 腾讯指数收盘评分...")
    indices, idx_klines = [], {}
    for secid, name in [("1.000001", "上证指数"), ("0.399001", "深证成指"),
                        ("0.399006", "创业板指")]:
        k = tx_kline(to_tx(secid))
        if k:
            idx_klines[secid] = k
            s, sigs = scan.index_score(k)
            i = len(k["close"]) - 1
            indices.append({"secid": secid, "name": name, "score": s,
                            "close": round(k["close"][i], 2),
                            "chg": round(k["close"][i] / k["close"][i - 1] - 1, 4),
                            "signals": sigs})
            print("  ", name, "OK", round(k["close"][i], 2),
                  f"{k['close'][i]/k['close'][i-1]-1:+.2%}")
        else:
            print("  ", name, "FAIL")
        time.sleep(SLEEP)
    if not indices:
        raise SystemExit("指数全部拉取失败, 腾讯源不可用, 中止")

    # ---------- [2/4] 股票池收盘重打分 ----------
    print(f"[2/4] 腾讯日K重扫 {len(old_uni)} 只...")
    universe, sec_to_sector = [], {}
    sector_close = {}   # sector -> [成分股收盘chg]
    for s in old_uni:
        k = tx_kline(to_tx(s["secid"]))
        if not k or len(k["close"]) < 80:
            print("  跳过", s["name"], "K线不足")
            time.sleep(SLEEP)
            continue
        sc, sigs = scan.stock_score(k)
        entry, stop, target = scan.stop_target(k)
        i = len(k["close"]) - 1
        universe.append({
            "secid": s["secid"], "code": s["code"], "name": s["name"],
            "sector": s["sector"], "sectorScore": s.get("sectorScore", 0),
            "score": sc, "signals": sigs,
            "price": round(k["close"][i], 2),
            "chg": round(k["close"][i] / k["close"][i - 1] - 1, 4),
            "entry": entry, "stop": stop, "target": target,
            "kline": k,
        })
        sector_close.setdefault(s["sector"], []).append(
            k["close"][i] / k["close"][i - 1] - 1)
        time.sleep(SLEEP)
    print("   成功:", len(universe), "只")
    if len(universe) < 20:
        raise SystemExit("股票池重扫失败过多, 中止")
    universe.sort(key=lambda s: -s["score"])

    # ---------- [3/4] 板块涨跌更新(成分股均值近似) ----------
    sectors = old.get("sectors", [])
    for sec in sectors:
        chgs = sector_close.get(sec["name"])
        if chgs:
            sec["chg"] = round(sum(chgs) / len(chgs), 4)   # 近似板块收盘涨跌
    top_boards = sorted(sectors, key=lambda s: -s.get("raw", 0))[:8]

    # ---------- [4/4] 收盘推荐 ----------
    good = [s for s in universe if s["score"] >= 55]
    picks, used = [], set()
    for b in top_boards:
        cand = [s for s in universe
                if s["sector"] == b["name"] and s["score"] >= 55]
        if cand:
            picks.append(cand[0]); used.add(cand[0]["code"])
    for s in good:
        if len(picks) >= 8:
            break
        if s["code"] not in used:
            picks.append(s); used.add(s["code"])
    for p in picks:
        p["reason"] = (f"{p['sector']}板块动量排名靠前(综合{p['sectorScore']}分)，"
                       f"个股触发{len(p['signals'])}项信号：{'、'.join(p['signals'][:4])}。"
                       f"建议以{p['stop']}为止损参考，分批布局。")

    market_score = int(round(sum(i["score"] for i in indices) / len(indices)))
    market_status = ("强势上行" if market_score >= 70 else
                     "震荡偏强" if market_score >= 55 else
                     "中性观望" if market_score >= 40 else "弱势防守")
    meta = {"generated": now, "universe": len(universe),
            "sectors": len(sectors), "marketScore": market_score,
            "marketStatus": market_status,
            "dataSource": "tencent-fallback(东财断连)",
            "note": "板块排名沿用盘中缓存, 指数/个股/推荐为收盘定稿"}

    kline_out = []
    for secid, name in [("1.000001", "上证指数"), ("0.399001", "深证成指"),
                        ("0.399006", "创业板指")]:
        k = idx_klines.get(secid)
        if k:
            kline_out.append({"secid": secid, "name": name, "tag": "市场指数", **k})
    for p in picks:
        kline_out.append({"secid": p["secid"], "name": p["name"],
                          "tag": p["sector"], **p["kline"]})

    scan_out = {"meta": meta, "indices": indices, "sectors": sectors[:12],
                "picks": [{k2: v2 for k2, v2 in p.items() if k2 != "kline"}
                          for p in picks],
                "kline": kline_out}
    with open("scan.json", "w", encoding="utf-8") as f:
        json.dump(scan_out, f, ensure_ascii=False, separators=(",", ":"))
    with open("universe.json", "w", encoding="utf-8") as f:
        json.dump([{k2: v2 for k2, v2 in s.items() if k2 != "kline"}
                   | {"close": s["kline"]["close"], "dates": s["kline"]["dates"]}
                   for s in universe], f, ensure_ascii=False, separators=(",", ":"))

    print("=" * 50)
    print(f"大盘: {market_status} (评分{market_score})")
    for p in picks:
        print(f"  {p['name']}({p['sector']}) 评分{p['score']} 收盘{p['price']} "
              f"{p['chg']:+.2%} 止损{p['stop']} 目标{p['target']}")
    print("saved scan.json / universe.json (腾讯收盘定稿)")


if __name__ == "__main__":
    main()
