# -*- coding: utf-8 -*-
"""盘中快照引擎: 基于 60分钟K线(分时) 生成盘中监控数据
输出 intraday.json: 推荐股小时级信号 + 指数盘中状态 + 止损/目标预警
与 scan.py 共用同一套东财接口封装(指数退避+多主机轮询)
"""
import json
import random
import time
import urllib.request
from datetime import datetime, timedelta

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://quote.eastmoney.com/"}
HOSTS = ["https://push2his.eastmoney.com", "https://1.push2his.eastmoney.com",
         "https://17.push2his.eastmoney.com", "https://52.push2his.eastmoney.com",
         "https://push2his.eastmoney.com"]
SLEEP = 0.12
NOW = datetime.now()
END = NOW.strftime("%Y%m%d")
BEG60 = (NOW - timedelta(days=60)).strftime("%Y%m%d")   # 60分钟K: 近60自然日
BEG_DAY = (NOW - timedelta(days=15)).strftime("%Y%m%d")  # 日K取昨收: 近15自然日

# ---- 数据源熔断: 东财失败一次后, 后续全部走腾讯兜底, 避免重复等待重试 ----
USE_TX = False


def to_tx_sym(secid):
    """东财 secid(1.603216) -> 腾讯代码(sh603216)"""
    return ("sh" if secid.startswith("1.") else "sz") + secid.split(".")[1]


def tx_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_json(url):
    """指数退避重试 + 主机轮询, 应对东财限流/断连; 熔断后不再走东财"""
    global USE_TX
    if USE_TX:
        raise RuntimeError("eastmoney fused -> tx")
    last = None
    for host in HOSTS[:2]:
        for attempt in range(2):
            try:
                req = urllib.request.Request(host + url, headers=UA)
                with urllib.request.urlopen(req, timeout=6) as r:
                    return json.loads(r.read().decode("utf-8"))
            except Exception as e:
                last = e
                time.sleep(0.3 + attempt * 0.4)
    USE_TX = True  # 东财不可用 -> 熔断, 全部走腾讯
    raise last


def probe_eastmoney():
    """启动时快速探测东财(1次/4秒), 失败立即熔断, 避免并行请求各自撞重试墙"""
    global USE_TX
    try:
        url = ("/api/qt/stock/kline/get?secid=1.000001&fields1=f1"
               "&fields2=f51&klt=101&fqt=1&end=" + END)
        req = urllib.request.Request(HOSTS[0] + url, headers=UA)
        with urllib.request.urlopen(req, timeout=4) as r:
            json.loads(r.read().decode("utf-8"))
        print("[probe] eastmoney OK")
        return True
    except Exception:
        USE_TX = True
        print("[probe] eastmoney down -> fuse to tencent")
        return False


def tx_minute_kline(secid, n=240):
    """腾讯60分钟K线兜底"""
    sym = to_tx_sym(secid)
    d = tx_get(f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={sym},m60,,{n}")
    rows = ((d.get("data") or {}).get(sym) or {}).get("m60") or []
    dates, close, volume = [], [], []
    for r in rows:
        dates.append(r[0]); close.append(float(r[2])); volume.append(int(float(r[5])))
    if not dates:
        return None
    return {"dates": dates, "close": close, "volume": volume}


def tx_prev_close(secid):
    """腾讯日K兜底取昨收"""
    sym = to_tx_sym(secid)
    d = tx_get(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={sym},day,,,6,qfq")
    node = (d.get("data") or {}).get(sym) or {}
    rows = node.get("qfqday") or node.get("day") or []
    if not rows:
        return None
    last_date = rows[-1][0]
    if last_date.startswith(NOW.strftime("%Y-%m-%d")) and len(rows) >= 2:
        return float(rows[-2][2])   # 盘中: 昨日收盘
    return float(rows[-1][2])        # 非交易日: 最近收盘


def minute_kline(secid, klt=60, beg=None):
    """拉取分钟K线, 返回 {dates, close, volume}; 东财失败自动切腾讯"""
    try:
        url = ("/api/qt/stock/kline/get"
               f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
               "&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
               f"&klt={klt}&fqt=1&beg={beg or BEG60}&end={END}")
        d = fetch_json(url)["data"]
        if not d or not d.get("klines"):
            raise ValueError("no klines")
        dates, close, volume = [], [], []
        for row in d["klines"]:
            p = row.split(",")
            dates.append(p[0]); close.append(float(p[2]))
            volume.append(int(float(p[5])))
        return {"dates": dates, "close": close, "volume": volume}
    except Exception:
        return tx_minute_kline(secid)


def prev_close(secid):
    """昨收: 拉日K, 若最后一根是今天(盘中)则取倒数第二根收盘; 东财失败切腾讯"""
    try:
        url = ("/api/qt/stock/kline/get"
               f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
               "&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
               f"&klt=101&fqt=1&beg={BEG_DAY}&end={END}")
        d = fetch_json(url)["data"]
        if not d or not d.get("klines"):
            raise ValueError("no klines")
        klines = d["klines"]
        last_date = klines[-1].split(",")[0]
        if last_date.startswith(NOW.strftime("%Y-%m-%d")) and len(klines) >= 2:
            return float(klines[-2].split(",")[2])  # 盘中: 昨日收盘
        return float(klines[-1].split(",")[2])       # 非交易日: 最近收盘
    except Exception:
        return tx_prev_close(secid)


def ma(x, n):
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


def hourly_signals(kl):
    """60分钟K线信号: 小时MA5/20金叉死叉, 小时MACD金叉死叉, 放量, 现价/涨跌幅"""
    c, v = kl["close"], kl["volume"]
    n = len(c)
    if n < 25:
        return None
    ma5, ma20 = ma(c, 5), ma(c, 20)
    dif = [a - b for a, b in zip(ema(c, 12), ema(c, 26))]   # DIF = EMA12 - EMA26
    dea = ema(dif, 9)                                        # DEA = DIF 的 9 期 EMA
    last_c = c[-1]
    prev_c = c[-2] if n >= 2 else last_c
    chg = last_c / prev_c - 1 if prev_c else 0.0
    sigs = []
    if ma5[-1] is not None and ma20[-1] is not None:
        if ma5[-1] > ma20[-1]:
            sigs.append("小时MA5>MA20")
        if ma5[-2] is not None and ma5[-2] <= ma20[-2] and ma5[-1] > ma20[-1]:
            sigs.append("小时金叉")
        if ma5[-2] is not None and ma5[-2] >= ma20[-2] and ma5[-1] < ma20[-1]:
            sigs.append("小时死叉")
    if dif[-1] > dea[-1]:
        sigs.append("小时MACD多头")
    if dif[-2] <= dea[-2] and dif[-1] > dea[-1]:
        sigs.append("MACD小时金叉")
    elif dif[-2] >= dea[-2] and dif[-1] < dea[-1]:
        sigs.append("MACD小时死叉")
    if n >= 21:
        avg_v = sum(v[-21:-1]) / 20
        if avg_v > 0 and v[-1] > 1.5 * avg_v:
            sigs.append("放量")
    return {"price": last_c, "chg": chg, "signals": sigs,
            "ma5": ma5[-1], "ma20": ma20[-1], "vol_ratio":
            (v[-1] / (sum(v[-21:-1]) / 20)) if n >= 21 and sum(v[-21:-1]) > 0 else None}


def _fetch_pick(p):
    """单只推荐股: 拉分钟K+昨收, 打信号与预警"""
    secid = p["secid"]
    try:
        kl = minute_kline(secid)
        hs = hourly_signals(kl) if kl else None
        pc = prev_close(secid)
    except Exception:
        return None
    if not hs:
        return None
    chg = (hs["price"] / pc - 1) if pc else 0.0
    item = {"secid": secid, "code": p["code"], "name": p["name"],
            "sector": p["sector"], "price": round(hs["price"], 2),
            "prevClose": round(pc, 2) if pc else None,
            "chg": round(chg, 4),
            "stop": p.get("stop"), "target": p.get("target"),
            "signals": hs["signals"],
            "volRatio": round(hs["vol_ratio"], 2) if hs["vol_ratio"] else None}
    warn = []
    if item["stop"] and item["price"] <= item["stop"]:
        warn.append("跌破止损位")
    elif item["stop"]:
        d = (item["price"] / item["stop"] - 1) * 100
        if d <= 3:
            warn.append(f"接近止损({d:.1f}%)")
    if item["target"] and item["price"] >= item["target"]:
        warn.append("触及目标位")
    item["warn"] = warn
    return item


def _fetch_index(ix):
    """单个指数: 拉分钟K+昨收, 打小时信号"""
    secid = ix["secid"]
    try:
        kl = minute_kline(secid)
        hs = hourly_signals(kl) if kl else None
        pc = prev_close(secid)
    except Exception:
        return None
    if not hs:
        return None
    chg = (hs["price"] / pc - 1) if pc else 0.0
    return {"secid": secid, "name": ix["name"],
            "price": round(hs["price"], 2), "chg": round(chg, 4),
            "signals": hs["signals"]}


def main():
    from concurrent.futures import ThreadPoolExecutor
    probe_eastmoney()
    scan = json.load(open("scan.json", encoding="utf-8"))
    picks, indices = scan.get("picks", []), scan.get("indices", [])

    with ThreadPoolExecutor(max_workers=6) as pool:
        out_picks = [r for r in pool.map(_fetch_pick, picks) if r]
        out_idx = [r for r in pool.map(_fetch_index, indices) if r]

    ts = NOW.strftime("%Y-%m-%d %H:%M")
    hour = NOW.hour
    phase = "盘中快照"
    if hour >= 15:
        phase = "收盘定稿"
    elif hour < 9:
        phase = "盘前"
    elif hour >= 11 and hour < 13:
        phase = "午间休市"
    out = {"ts": ts, "phase": phase, "picks": out_picks, "indices": out_idx,
           "note": "盘中数据基于60分钟K线, 仅供参考; 最终信号以收盘后日线定稿为准"}
    with open("intraday.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[intraday] {ts} {phase} picks={len(out_picks)} indices={len(out_idx)}")
    for it in out_picks:
        w = ",".join(it["warn"]) if it["warn"] else "-"
        print(f"  {it['name']:6s} 价{it['price']:8.2f} 涨跌{it['chg']*100:+6.2f}% "
              f"信号[{','.join(it['signals'])}] 预警[{w}]")
    return out


if __name__ == "__main__":
    main()
