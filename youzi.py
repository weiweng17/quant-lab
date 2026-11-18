# -*- coding: utf-8 -*-
"""游资模式回测: 涨停板接力策略 -> youzi.json

规则(日线近似游资打法):
  1) 信号: 当日涨停(东财涨停池, 含连板数 lbc / 所属行业); 东财该接口历史窗口约 15 个交易日
  2) 执行: 次日开盘买入(open_t1); 次日开盘接近涨停/一字板视为买不进, 剔除
  3) 持有: 固定 1/2/3 个交易日后收盘卖出; 期间跌破 -7% 止损
  4) 情绪过滤: 当日涨停家数 >= 40 才接力(退潮日不做), 单独一列对比
  5) 成本: 佣金万2.5 双边 + 卖出印花税 0.05%

口径说明: 每笔等权, "累计"为各笔收益率线性累加(非复利), 回撤基于累加曲线;
不含抢筹滑点/资金容量/盘中执行 —— 真实游资的高收益有相当部分来自这些日线无法复现的优势。
"""
import json
import os
import time
import urllib.request
from collections import Counter
from datetime import datetime, timedelta

from rescan_tencent import tx_kline, to_tx      # 腾讯日线兜底(无全局熔断)

DAYS = 40          # 目标覆盖交易日数(受东财接口历史窗口限制, 实际约 15)
MAX_CODES = 450    # 最多拉多少只个股日线(按涨停频次取前 N)
SLEEP = 0.16
STOP_PCT = 0.07
ZT_FILTER = 40
CACHE_FILE = "youzi_kline_cache.json"

BEG = (datetime.now() - timedelta(days=200)).strftime("%Y%m%d")
END = datetime.now().strftime("%Y%m%d")
HOSTS = ["https://push2his.eastmoney.com", "https://1.push2his.eastmoney.com",
         "https://17.push2his.eastmoney.com", "https://52.push2his.eastmoney.com"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://quote.eastmoney.com/"}


def limit_up_pool(date_str):
    url = ("https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989"
           f"&dpt=wz.ztzt&Pageindex=0&pagesize=320&sort=fbt%3Aasc&date={date_str}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode("utf-8"))
        return (d.get("data") or {}).get("pool") or []
    except Exception:
        return []


def east_kline(secid, host):
    """东财日线单次尝试(短超时), 失败交给调用方切腾讯兜底"""
    url = ("/api/qt/stock/kline/get"
           f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
           "&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
           f"&klt=101&fqt=1&beg={BEG}&end={END}")
    try:
        req = urllib.request.Request(host + url, headers=UA)
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read().decode("utf-8"))
        kl = (d.get("data") or {}).get("klines") or []
        if not kl:
            return None
        dates, o, c, h, l = [], [], [], [], []
        for row in kl:
            p = row.split(",")
            dates.append(p[0]); o.append(float(p[1])); c.append(float(p[2]))
            h.append(float(p[3])); l.append(float(p[4]))
        return {"dates": dates, "open": o, "close": c, "high": h, "low": l}
    except Exception:
        return None


def sina_kline(code):
    """新浪前复权日线(无鉴权, 稳定): [{day,open,high,low,close}] -> 统一结构"""
    sym = ("sh" if code[0] == "6" else "sz") + code
    url = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           f"CN_MarketData.getKLineData?symbol={sym}&scale=240&ma=no&datalen=120")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finance.sina.com.cn"})
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = json.loads(r.read().decode("utf-8", "ignore"))
        if not rows:
            return None
        return {"dates": [x["day"] for x in rows],
                "open": [float(x["open"]) for x in rows],
                "close": [float(x["close"]) for x in rows],
                "high": [float(x["high"]) for x in rows],
                "low": [float(x["low"]) for x in rows]}
    except Exception:
        return None


def fetch_kline(code, idx=0):
    """新浪优先, 东财兜底(限流时东财会直接断连)"""
    kl = sina_kline(code)
    if kl:
        return kl
    secid = ("1." if code[0] == "6" else "0.") + code
    return east_kline(secid, HOSTS[idx % len(HOSTS)])


def tradable(code, name):
    if not code or len(code) != 6:
        return False
    if code[0] not in "036":            # 仅沪深主板/创业板
        return False
    if code.startswith("68"):           # 排除科创板(20% 规则另算)
        return False
    if "ST" in (name or "").upper() or (name or "").startswith("*"):
        return False
    return True


def board_limit(code):
    return 0.198 if code.startswith("30") else 0.098


def simulate(sig, kl, hold):
    """信号日收盘涨停 -> 次日开盘买 -> 持有 hold 日后收盘卖, 期间 -7% 止损。"""
    dates = kl["dates"]
    try:
        i = dates.index(sig["date"])
    except ValueError:
        return None
    if i + 1 >= len(dates):
        return None
    entry, prev_close = kl["open"][i + 1], kl["close"][i]
    if entry <= 0 or prev_close <= 0:
        return None
    if entry / prev_close - 1 >= board_limit(sig["code"]) * 0.97:
        return {"skipped": "gap_limit"}      # 一字板/抢不到
    exit_i = i + 1 + hold - 1
    if exit_i >= len(dates):
        return None
    stop = entry * (1 - STOP_PCT)
    sell, reason = kl["close"][exit_i], "hold"
    for j in range(i + 1, exit_i + 1):
        if kl["low"][j] <= stop:
            sell = kl["open"][j] if kl["open"][j] < stop else stop
            reason, exit_i = "stop", j
            break
    ret = sell / entry * (1 - 0.00025 - 0.0005) - (1 + 0.00025)
    return {"date": sig["date"], "code": sig["code"], "name": sig["name"],
            "lbc": sig["lbc"], "industry": sig["industry"],
            "buy": round(entry, 2), "sell": round(sell, 2),
            "ret": ret, "days": exit_i - i, "reason": reason,
            "exitDate": dates[exit_i]}


def stats(trades):
    """等权口径: 每笔固定仓位, 累计=收益率线性累加, 回撤基于累加曲线。"""
    if not trades:
        return None
    order = sorted(trades, key=lambda x: (x["exitDate"], x["code"]))
    rets = [t["ret"] for t in order]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    cum, peak, mdd = 0.0, 0.0, 0.0
    for r in rets:
        cum += r
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
    avg_w = sum(wins) / len(wins) if wins else 0.0
    avg_l = sum(losses) / len(losses) if losses else 0.0
    return {"trades": len(rets), "winRate": round(len(wins) / len(rets), 4),
            "avgRet": round(sum(rets) / len(rets), 4),
            "medianRet": round(sorted(rets)[len(rets) // 2], 4),
            "avgWin": round(avg_w, 4), "avgLoss": round(avg_l, 4),
            "payoff": round(abs(avg_w / avg_l), 2) if avg_l else None,
            "sumRet": round(cum, 4), "mdd": round(mdd, 4),
            "best": round(max(rets), 4), "worst": round(min(rets), 4),
            "stopRate": round(sum(1 for t in trades if t["reason"] == "stop") / len(rets), 4)}


def main():
    print("[1/4] 拉取历史涨停池...")
    days, daily, sigs = [], [], []
    d = datetime.now()
    empty_streak = 0
    while len(days) < DAYS and (datetime.now() - d).days < 130 and empty_streak < 6:
        if d.weekday() < 5:
            pool = limit_up_pool(d.strftime("%Y%m%d"))
            if pool:
                empty_streak = 0
                ds = d.strftime("%Y-%m-%d")
                days.append(ds)
                lb = [p.get("lbc", 1) or 1 for p in pool]
                rows = [{"date": ds, "code": str(p.get("c", "")).zfill(6), "name": p.get("n", ""),
                         "lbc": p.get("lbc", 1) or 1, "industry": p.get("hybk", "")}
                        for p in pool if tradable(str(p.get("c", "")).zfill(6), p.get("n", ""))]
                sigs.extend(rows)
                daily.append({"date": ds, "ztCount": len(pool), "maxLb": max(lb),
                              "signals": len(rows)})
                print(f"  {ds} 涨停{len(pool):>3}只 -> 可用信号 {len(rows)}")
            else:
                empty_streak += 1
            time.sleep(0.15)
        d -= timedelta(days=1)
    daily.sort(key=lambda x: x["date"])
    print(f"  覆盖 {len(daily)} 个交易日, 信号 {len(sigs)} 笔, "
          f"唯一标的 {len({s['code'] for s in sigs})} 只")
    if not sigs:
        raise SystemExit("涨停池数据为空, 中止")

    print(f"[2/4] 拉取个股日线(按涨停频次取前 {MAX_CODES} 只)...")
    freq = Counter(s["code"] for s in sigs)
    codes = [c for c, _ in freq.most_common(MAX_CODES)]
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            c = json.load(open(CACHE_FILE, encoding="utf-8"))
            if c.get("date") == datetime.now().strftime("%Y-%m-%d"):
                cache = c.get("data") or {}       # 当天重跑直接复用
                print(f"  复用当日缓存 {len(cache)} 只")
        except Exception:
            pass
    kls = dict(cache)
    todo = [c for c in codes if c not in kls]
    if todo:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        done = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(fetch_kline, c, i): c for i, c in enumerate(todo)}
            for fut in as_completed(futs):
                code = futs[fut]
                try:
                    kl = fut.result()
                except Exception:
                    kl = None
                if kl:
                    kls[code] = kl
                done += 1
                if done % 100 == 0:
                    print(f"  {done}/{len(todo)} (成功 {len(kls)}) ...")
    print(f"  日线就绪 {len(kls)}/{len(codes)} 只")
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": datetime.now().strftime("%Y-%m-%d"), "data": kls},
                  f, ensure_ascii=False, separators=(",", ":"))
    if len(kls) < 50:
        raise SystemExit(f"日线仅取到 {len(kls)} 只, 数据源异常, 中止(保留旧 youzi.json)")

    print("[3/4] 模拟交易(次日开盘买 / 持有1-3日 / -7%止损)...")
    zt_by_date = {x["date"]: x["ztCount"] for x in daily}
    variants_def = [
        ("first_h1", "首板 · 持有1日", 1, lambda s: s["lbc"] == 1),
        ("first_h2", "首板 · 持有2日", 2, lambda s: s["lbc"] == 1),
        ("first_h3", "首板 · 持有3日", 3, lambda s: s["lbc"] == 1),
        ("relay_h1", "连板接力 · 持有1日", 1, lambda s: 2 <= s["lbc"] <= 4),
        ("relay_h2", "连板接力 · 持有2日", 2, lambda s: 2 <= s["lbc"] <= 4),
        ("all_h1", "全部涨停 · 持有1日", 1, lambda s: True),
    ]
    variants, all_trades, gap_skipped = [], [], 0
    for vid, vname, hold, pick in variants_def:
        tr = []
        for s in sigs:
            if not pick(s) or s["code"] not in kls:
                continue
            r = simulate(s, kls[s["code"]], hold)
            if not r:
                continue
            if r.get("skipped"):
                if vid == "all_h1":
                    gap_skipped += 1
                continue
            tr.append(r)
        st = stats(tr)
        if st:
            st.update({"id": vid, "name": vname, "hold": hold})
            variants.append(st)
            print(f"  {vname:<12} {st['trades']:>4} 笔 胜率{st['winRate']*100:>5.1f}% "
                  f"均收益{st['avgRet']*100:>6.2f}% 盈亏比{st['payoff']} 累加{st['sumRet']*100:>7.1f}%")
        if vid == "all_h1":
            all_trades = tr

    filt = []
    for s in sigs:
        if s["code"] in kls and zt_by_date.get(s["date"], 0) >= ZT_FILTER and s["lbc"] <= 4:
            r = simulate(s, kls[s["code"]], 1)
            if r and not r.get("skipped"):
                filt.append(r)
    st_filt = stats(filt)
    if st_filt:
        st_filt.update({"id": "filter_h1", "name": f"情绪过滤(涨停≥{ZT_FILTER}) · 持有1日", "hold": 1})
        variants.append(st_filt)
        print(f"  情绪过滤版   {st_filt['trades']:>4} 笔 胜率{st_filt['winRate']*100:>5.1f}% "
              f"均收益{st_filt['avgRet']*100:>6.2f}% 累加{st_filt['sumRet']*100:>7.1f}%")

    print("[4/4] 汇总输出...")
    out = {
        "meta": {"generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "days": len(daily), "period": [daily[0]["date"], daily[-1]["date"]],
                 "signals": len(sigs), "universe": len(kls),
                 "gapSkipped": gap_skipped, "stopPct": STOP_PCT,
                 "fee": "佣金万2.5双边 + 印花税0.05%",
                 "rules": "信号日涨停 → 次日开盘买入 → 持有1-3日收盘卖出 → 期间-7%止损",
                 "note": "东财涨停池历史窗口约15个交易日; 等权口径, 累计为收益率线性累加"},
        "daily": [{"date": x["date"], "ztCount": x["ztCount"], "maxLb": x["maxLb"]}
                  for x in daily],
        "variants": variants,
        "recent": sorted(all_trades, key=lambda t: (t["exitDate"], t["code"]))[-15:][::-1],
    }
    with open("youzi.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("saved youzi.json")


if __name__ == "__main__":
    main()
