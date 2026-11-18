# -*- coding: utf-8 -*-
"""自上而下扫描引擎: 大盘评分 -> 板块动量排名 -> 个股信号打分 -> 每日推荐
输出 scan.json(网站+回测用) 与 universe.json(全股票池, 供策略统计)
数据源: 东方财富公开接口
"""
import json
import math
import time
import urllib.request
from datetime import datetime

try:
    from backtest import sma, ema, macd, rsi
except Exception:
    # 兜底: 若 backtest.py 不可导入则内联轻量实现
    def sma(x, n):
        out = [None] * len(x); s = 0.0
        for i, v in enumerate(x):
            s += v
            if i >= n: s -= x[i - n]
            if i >= n - 1: out[i] = s / n
        return out
    def ema(x, n):
        out = [None] * len(x); k = 2.0 / (n + 1); prev = None
        for i, v in enumerate(x):
            prev = v if prev is None else v * k + prev * (1 - k)
            out[i] = prev
        return out
    def macd(c, fast=12, slow=26, sig=9):
        ef, es = ema(c, fast), ema(c, slow)
        dif = [a - b for a, b in zip(ef, es)]
        return dif, ema(dif, sig)
    def rsi(c, n=14):
        out = [None] * len(c); gs = ls = 0.0; ag = al = 0.0
        for i in range(1, len(c)):
            ch = c[i] - c[i - 1]; g, d = max(ch, 0.0), max(-ch, 0.0)
            if i <= n:
                gs += g; ls += d
                if i == n: ag, al = gs / n, ls / n
            else:
                ag = (ag * (n - 1) + g) / n; al = (al * (n - 1) + d) / n
            out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
        return out

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://quote.eastmoney.com/"}
BEG, END = "20240701", datetime.now().strftime("%Y%m%d")
SLEEP = 0.15
HOSTS = ["https://push2his.eastmoney.com", "https://1.push2his.eastmoney.com",
         "https://17.push2his.eastmoney.com", "https://52.push2his.eastmoney.com",
         "https://push2his.eastmoney.com"]
import random


FUSED = False   # 东财整体断连熔断: 全主机重试一轮仍失败后置位, 后续请求立即失败, 让自动化快速切兜底


def fetch_json(url):
    """指数退避重试 + 多主机轮询, 应对东财限流/断连; 整体断连时熔断快速失败"""
    global FUSED
    if FUSED:
        raise RuntimeError("eastmoney fused (fast-fail)")
    last = None
    order = list(range(len(HOSTS)))
    for h_i in order:
        host = HOSTS[h_i]
        for attempt in range(5):
            try:
                req = urllib.request.Request(host + url, headers=UA)
                with urllib.request.urlopen(req, timeout=15) as r:
                    return json.loads(r.read().decode("utf-8"))
            except Exception as e:
                last = e
                time.sleep(0.6 + attempt * 0.9 + random.random() * 0.4)
    FUSED = True
    raise last


def kline(secid):
    url = ("/api/qt/stock/kline/get"
           f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
           "&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
           f"&klt=101&fqt=1&beg={BEG}&end={END}")
    d = fetch_json(url)["data"]
    if not d or not d.get("klines"):
        return None
    dates, o, h, l, c, v = [], [], [], [], [], []
    for row in d["klines"]:
        p = row.split(",")
        dates.append(p[0]); o.append(float(p[1])); c.append(float(p[2]))
        h.append(float(p[3])); l.append(float(p[4])); v.append(int(float(p[5])))
    return {"dates": dates, "open": o, "high": h, "low": l, "close": c, "volume": v}


def board_list():
    url = ("/api/qt/clist/get?pn=1&pz=200&po=1&np=1"
           "&fltt=2&invt=2&fid=f12&fs=m:90+t:2&fields=f12,f14,f104,f105")
    d = fetch_json(url)
    items = (d.get("data") or {}).get("diff") or []
    out = []
    for it in items:
        code, name = it.get("f12"), it.get("f14")
        members = (it.get("f104") or 0) + (it.get("f105") or 0)
        if code and name and members >= 12:  # 过滤迷你板块, 保证流动性
            out.append((code, name))
    return out


def constituents(bk_code, limit=8):
    url = ("/api/qt/clist/get?pn=1&pz=20&po=1&np=1"
           "&fltt=2&invt=2&fid=f20"
           f"&fs=b:{bk_code}&fields=f12,f14")
    d = fetch_json(url)
    items = (d.get("data") or {}).get("diff") or []
    out = []
    for it in items:
        code = it.get("f12", "")
        if code and code[0] in "036" and not code.startswith("68"):
            # 只留沪深主板/创业板; 排除科创板(68x, 20%涨跌幅规则不同)与B股(9xx)
            out.append((code, it.get("f14", "")))
    return out[:limit]


def secid_of(code):
    return ("1." if code[0] == "6" else "0.") + code


# ---------- 权重外置(data/weights/<ver>.json 为唯一事实源, 代码内兜底) ----------

DEFAULT_WEIGHTS = {
    "version": "code-fallback",
    "signalWeights": {"maBull": 1.0, "maCross": 1.5, "macdBull": 1.0, "macdCross": 1.5,
                      "rsiBand": 0.8, "high20": 1.2, "volume": 0.8, "mom20": 0.6, "ma60": 0.8},
    "factorWeights": {"technical": 0.45, "hotTheme": 0.35, "sector": 0.20},
    "thresholdAdjust": {"sentimentIce": 5, "sentimentHot": -5,
                        "sentimentIceBelow": 30, "sentimentHotAbove": 80},
}


def load_weights(path="data/weights/v2.json"):
    try:
        with open(path, encoding="utf-8") as f:
            w = json.load(f)
        assert abs(sum(w["factorWeights"].values()) - 1.0) < 1e-6, "factorWeights 合计须为 1.0"
        return w
    except Exception as e:
        print(f"   权重文件加载失败({e}), 使用代码内兜底权重")
        return dict(DEFAULT_WEIGHTS)


# ---------- 题材热度 / 涨停情绪 数据源 ----------

def fetch_ths_rows():
    """同花顺当日强势股(零鉴权) 全量行: [{code,name,tags}]。失败返回 []。"""
    url = (f"http://zx.10jqka.com.cn/event/api/getharden/"
           f"date/{datetime.now().strftime('%Y-%m-%d')}/orderby/date/orderway/desc/charset/GBK/")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "http://zx.10jqka.com.cn/"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read().decode("gbk", "ignore"))
        if d.get("errocode", 0) != 0:
            return []
        out = []
        for row in (d.get("data") or []):
            code = str(row.get("code", "")).zfill(6)
            reason = str(row.get("reason", "") or "")
            tags = [t.strip() for t in reason.split("+") if t.strip()]
            if code and tags:
                out.append({"code": code, "name": str(row.get("name", "") or ""),
                            "tags": tags})
        return out
    except Exception as e:
        print("   同花顺强势股拉取失败(题材因子中性化):", e)
        return []


def fetch_ths_hot():
    """强势股 {code: tags} 映射(题材因子计分用), 基于 fetch_ths_rows。"""
    return {r["code"]: r["tags"] for r in fetch_ths_rows()}


def build_hot_payload(rows):
    """热门题材榜 + 强势股池 payload(供 scan.json['hot'] 与页面题材专区)。
    updated 为数据抓取时间: 盘中由 fetch_themes.py 每小时刷新, 降低滞后性。"""
    if not rows:
        return None
    tag_counts = {}
    for r in rows:
        for t in r["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    themes = [{"tag": t, "count": c,
               "stocks": [r["name"] for r in rows if t in r["tags"]]}
              for t, c in sorted(tag_counts.items(), key=lambda x: -x[1])[:12]]
    return {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total": len(rows), "themes": themes,
            "stocks": [{"code": r["code"], "name": r["name"], "tags": r["tags"]}
                       for r in rows]}


def hot_theme_score(code, name, hot_map, tag_counts):
    """题材热度 0-100: 在强势股池=基础加分, 题材标签的全局热度(同标签强势股数量)再加分。
    hot_map 为空(接口失败)时全员中性 50, 合成分不受影响。"""
    if not hot_map:
        return 50, []
    tags = hot_map.get(code)
    if not tags:
        return 40, []
    score = 55.0
    # 题材名气: 该股标签里热度最高的两个, 按全局出现次数加分(每个标签最多+10)
    top = sorted(tags, key=lambda t: -tag_counts.get(t, 0))[:2]
    for t in top:
        score += min(10.0, tag_counts.get(t, 0) * 2.0)
    return min(100.0, score), top


def fetch_limit_up_pool():
    """东财涨停池: 涨停家数/连板分布 -> 情绪温度。失败返回 None。"""
    url = ("https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989"
           "&dpt=wz.ztzt&Pageindex=0&pagesize=320&sort=fbt%3Aasc"
           f"&date={datetime.now().strftime('%Y%m%d')}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read().decode("utf-8"))
        pool = (d.get("data") or {}).get("pool") or []
        if not pool:
            return None
        max_lb = max(p.get("lbc", 1) or 1 for p in pool)
        count = len(pool)
        # 情绪温度: 家数为主(1分/家), 连板高度加成(每高一级+8), 上限100
        score = int(min(100, count + (max_lb - 1) * 8))
        label = ("冰点" if score < 30 else
                 "降温" if score < 45 else
                 "温和" if score < 70 else "亢奋")
        return {"ztCount": count, "maxLb": max_lb, "score": score, "label": label}
    except Exception as e:
        print("   涨停池拉取失败(情绪温度缺失):", e)
        return None


# ---------- 指标打分 ----------

def atr(high, low, close, n=14):
    trs, out = [], [None] * len(close)
    for i in range(1, len(close)):
        trs.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
        if len(trs) >= n:
            out[i] = sum(trs[-n:]) / n
    return out


def index_score(k):
    c = k["close"]; ma20 = sma(c, 20); ma60 = sma(c, 60); dif, dea = macd(c)
    i = len(c) - 1
    s = 0; sigs = []
    if c[i] > ma20[i]: s += 30; sigs.append("站上20日线")
    if c[i] > ma60[i]: s += 30; sigs.append("站上60日线")
    if ma20[i] > ma60[i]: s += 20; sigs.append("中期趋势向上")
    if dif[i] > dea[i]: s += 20; sigs.append("MACD多头")
    return s, sigs


def sector_raw(k):
    c = k["close"]; v = k["volume"]; ma20 = sma(c, 20)
    i = len(c) - 1
    mom20 = c[i] / c[max(0, i - 20)] - 1 if i >= 20 else 0.0
    mom60 = c[i] / c[max(0, i - 60)] - 1 if i >= 60 else 0.0
    trend = 1 if c[i] > ma20[i] else 0
    v5 = sum(v[i - 4:i + 1]) / 5 if i >= 4 else v[i]
    v20 = sum(v[max(0, i - 19):i + 1]) / min(20, i + 1)
    vr = v5 / v20 if v20 > 0 else 1.0
    return {"mom20": mom20, "mom60": mom60, "trend": trend, "volRatio": vr,
            "close": c[i], "chg": c[i] / c[i - 1] - 1 if i > 0 else 0.0}


def stock_score(k, sig_w=None):
    """技术信号打分(0-100)。信号权重来自 weights 文件(signalWeights), 代码内兜底。"""
    sw = (sig_w or DEFAULT_WEIGHTS["signalWeights"])
    w_sum = sum(sw.values()) or 1.0
    c = k["close"]; h = k["high"]; l = k["low"]; v = k["volume"]
    ma5 = sma(c, 5); ma20 = sma(c, 20); ma60 = sma(c, 60)
    dif, dea = macd(c); r = rsi(c, 14)
    i = len(c) - 1
    score = 0.0; sigs = []
    if ma5[i] > ma20[i]: score += sw["maBull"]; sigs.append("MA5>MA20")
    for j in range(max(0, i - 5), i + 1):
        if ma5[j] is not None and ma20[j] is not None and j > 0 \
           and ma5[j - 1] <= ma20[j - 1] and ma5[j] > ma20[j]:
            score += sw["maCross"]; sigs.append("MA5上穿MA20"); break
    if dif[i] > dea[i] and dif[i] > 0: score += sw["macdBull"]; sigs.append("MACD多头")
    for j in range(max(0, i - 10), i + 1):
        if dif[j] is not None and dea[j] is not None and j > 0 \
           and dif[j - 1] <= dea[j - 1] and dif[j] > dea[j]:
            score += sw["macdCross"]; sigs.append("MACD金叉"); break
    if r[i] is not None and 45 <= r[i] <= 72: score += sw["rsiBand"]
    hi20 = max(h[max(0, i - 20):i]) if i >= 20 else max(h[:i])
    if c[i] > hi20: score += sw["high20"]; sigs.append("创20日新高")
    v5 = sum(v[max(0, i - 4):i + 1]) / min(5, i + 1)
    v20 = sum(v[max(0, i - 19):i + 1]) / min(20, i + 1)
    vr = v5 / v20 if v20 > 0 else 1.0
    if vr > 1.15: score += sw["volume"]; sigs.append("温和放量")
    if c[i] > c[max(0, i - 20)]: score += sw["mom20"]; sigs.append("20日上涨")
    if ma60[i] is not None and c[i] > ma60[i]: score += sw["ma60"]; sigs.append("站上60日线")
    return min(100, int(round(score / w_sum * 100))), list(dict.fromkeys(sigs))


def stop_target(k):
    a = atr(k["high"], k["low"], k["close"], 14)
    i = len(k["close"]) - 1
    atr_v = a[i] if a[i] else k["close"][i] * 0.02
    entry = round(k["close"][i], 2)
    stop = round(max(entry - 2.2 * atr_v, entry * 0.85), 2)
    target = round(entry + 1.5 * (entry - stop), 2)
    return entry, stop, target


# ---------- 主流程 ----------

def main():
    print("[0/4] 加载权重 + 题材/情绪数据...")
    W = load_weights()
    FW = W["factorWeights"]
    TA = W.get("thresholdAdjust", DEFAULT_WEIGHTS["thresholdAdjust"])
    print(f"   权重版本 {W['version']} · 技术{FW['technical']} 题材{FW['hotTheme']} 板块{FW['sector']}")
    ths_rows = fetch_ths_rows()
    hot_map = {r["code"]: r["tags"] for r in ths_rows}
    tag_counts = {}
    for tags in hot_map.values():
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    print(f"   同花顺强势股 {len(hot_map)} 只" + (f", 热门题材: {'、'.join(sorted(tag_counts, key=tag_counts.get, reverse=True)[:3])}" if tag_counts else "(接口不可用, 题材因子中性化)"))
    sentiment = fetch_limit_up_pool()
    if sentiment:
        print(f"   涨停情绪温度: {sentiment['score']}({sentiment['label']}) · 涨停{sentiment['ztCount']}家 · 最高{sentiment['maxLb']}连板")
    else:
        print("   涨停池不可用, 情绪温度缺失(不影响选股, 仅展示层缺一项)")

    print("[1/4] 拉取大盘指数...")
    indices = []
    idx_klines = {}
    for secid, name in [("1.000001", "上证指数"), ("0.399001", "深证成指"),
                        ("0.399006", "创业板指")]:
        k = kline(secid)
        if k:
            idx_klines[secid] = k
            s, sigs = index_score(k)
            i = len(k["close"]) - 1
            indices.append({"secid": secid, "name": name, "score": s,
                            "close": round(k["close"][i], 2),
                            "chg": round(k["close"][i] / k["close"][i - 1] - 1, 4),
                            "signals": sigs})
        print("  ", name, "OK" if k else "FAIL")
        time.sleep(SLEEP)
    if not indices:
        raise SystemExit("三大指数全部拉取失败(东财不可用), 中止; 自动化可改跑 rescan_tencent.py 兜底")

    print("[2/4] 拉取行业板块列表与K线...")
    boards = board_list()
    print("   板块数:", len(boards))
    sectors = []
    for code, name in boards:
        try:
            k = kline("90." + code)
            if k and len(k["close"]) >= 70:
                raw = sector_raw(k)
                raw.update({"code": code, "name": name})
                sectors.append(raw)
        except Exception as e:
            print("   板块跳过", code, e)
        time.sleep(SLEEP)
    # zscore 归一化 -> 百分位排名分
    def zs(key):
        vals = [s[key] for s in sectors]
        m = sum(vals) / len(vals)
        sd = math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals)) or 1e-9
        return [(x - m) / sd for x in vals]
    z20, z60 = zs("mom20"), zs("mom60")
    vols = [min(max(s["volRatio"], 0.5), 2.5) for s in sectors]
    vm = sum(vols) / len(vols); vsd = math.sqrt(sum((x - vm) ** 2 for x in vols) / len(vols)) or 1e-9
    zvol = [(x - vm) / vsd for x in vols]
    for s, a, b, c in zip(sectors, z20, z60, zvol):
        s["raw"] = 0.35 * a + 0.25 * b + 0.25 * (s["trend"] * 2 - 1) + 0.15 * c
    sectors.sort(key=lambda s: -s["raw"])
    n = len(sectors)
    for rank, s in enumerate(sectors):
        s["score"] = int(round((n - rank) / n * 100))
    top_boards = sectors[:8]
    print("   强势板块Top8:", " / ".join(s["name"] for s in top_boards))

    print("[3/4] 扫描强势板块成分股...")
    universe = []
    seen = set()
    for b in top_boards:
        try:
            members = constituents(b["code"], 8)
        except Exception as e:
            print("   成分股跳过", b["name"], e)
            members = []
        for code, name in members:
            if code in seen:
                continue
            if "ST" in name.upper() or name.startswith("*"):
                seen.add(code)   # ST/退市风险股直接排除, 不进股票池
                continue
            seen.add(code)
            try:
                k = kline(secid_of(code))
                if k and len(k["close"]) >= 80:
                    sc, sigs = stock_score(k, W["signalWeights"])
                    theme_sc, hot_tags = hot_theme_score(code, name, hot_map, tag_counts)
                    # 三因子合成: 技术(0-100) × 题材热度(0-100) × 板块强度(0-100)
                    comp = (FW["technical"] * sc + FW["hotTheme"] * theme_sc
                            + FW["sector"] * b["score"])
                    entry, stop, target = stop_target(k)
                    i = len(k["close"]) - 1
                    universe.append({
                        "secid": secid_of(code), "code": code, "name": name,
                        "sector": b["name"], "sectorScore": b["score"],
                        "score": int(round(comp)), "techScore": sc,
                        "themeScore": int(round(theme_sc)),
                        "isHot": bool(hot_map.get(code)),
                        "hotTags": hot_tags,
                        "signals": sigs,
                        "price": round(k["close"][i], 2),
                        "chg": round(k["close"][i] / k["close"][i - 1] - 1, 4),
                        "entry": entry, "stop": stop, "target": target,
                        "kline": k,
                    })
            except Exception as e:
                print("   个股跳过", code, e)
            time.sleep(SLEEP)
    print("   股票池:", len(universe))
    if len(universe) < 20:
        raise SystemExit(f"股票池仅{len(universe)}只(数据源异常), 中止; 自动化可改跑 rescan_tencent.py 兜底")
    universe.sort(key=lambda s: -s["score"])

    # 大盘状态与动态门槛: 市场越弱, 入选分数要求越高, 避免弱市凑数推荐
    market_score = int(round(sum(i["score"] for i in indices) / len(indices)))
    market_status = ("强势上行" if market_score >= 70 else
                     "震荡偏强" if market_score >= 55 else
                     "中性观望" if market_score >= 40 else "弱势防守")
    pick_th = (55 if market_score >= 70 else
               60 if market_score >= 55 else
               65 if market_score >= 40 else 70)
    if sentiment:   # 情绪温度联动: 冰点收紧、亢奋放宽
        if sentiment["score"] < TA["sentimentIceBelow"]:
            pick_th += TA["sentimentIce"]
            print(f"   情绪{sentiment['label']}({sentiment['score']}) -> 门槛+{TA['sentimentIce']}")
        elif sentiment["score"] > TA["sentimentHotAbove"]:
            pick_th = max(50, pick_th + TA["sentimentHot"])
            print(f"   情绪{sentiment['label']}({sentiment['score']}) -> 门槛{TA['sentimentHot']}")

    good = [s for s in universe if s["score"] >= pick_th]
    print(f"   大盘{market_status}(评分{market_score}) -> 入选门槛 {pick_th} 分, "
          f"候选 {len(good)} 只")

    print("[4/4] 生成推荐列表...")
    # 板块多样性: 每个强势板块取最优 1 只, 优先; 不足则从全局高分补齐
    picks, used = [], set()
    for b in top_boards:
        cand = [s for s in universe if s["sector"] == b["name"] and s["score"] >= pick_th]
        if cand:
            picks.append(cand[0]); used.add(cand[0]["code"])
    for s in good:
        if len(picks) >= 8:
            break
        if s["code"] not in used:
            picks.append(s); used.add(s["code"])
    for p in picks:
        hot_txt = f"，同花顺强势股题材：{'、'.join(p['hotTags'][:3])}" if p.get("hotTags") else ""
        p["reason"] = (f"{p['sector']}板块动量排名靠前(综合{p['sectorScore']}分)"
                       f"，技术{p['techScore']}/题材{p['themeScore']}{hot_txt}"
                       f"，个股触发{len(p['signals'])}项信号：{'、'.join(p['signals'][:4])}。"
                       f"建议以{ p['stop']}为止损参考，分批布局。")

    # 建议仓位: 大盘趋势定基调, 情绪温度修正(冰点减仓/亢奋略加), 0-9 成
    pos = (8 if market_score >= 70 else 6 if market_score >= 55 else
           4 if market_score >= 40 else 2)
    if sentiment:
        if sentiment["score"] < TA["sentimentIceBelow"]:
            pos -= 2
        elif sentiment["score"] > TA["sentimentHotAbove"]:
            pos += 1
    pos = max(0, min(9, pos))
    print(f"   建议仓位: {pos} 成")

    meta = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "universe": len(universe), "sectors": len(sectors),
            "marketScore": market_score, "marketStatus": market_status,
            "pickThreshold": pick_th,
            "position": pos,
            "weightsVersion": W["version"],
            "factorWeights": {"technical": FW["technical"], "hotTheme": FW["hotTheme"],
                              "sector": FW["sector"]},
            "sentiment": sentiment}

    # 回测/图表用的全量K线: 指数 + 推荐股 (复用已拉数据, 不重复请求)
    kline_out = []
    for secid, name in [("1.000001", "上证指数"), ("0.399001", "深证成指"),
                        ("0.399006", "创业板指")]:
        k = idx_klines.get(secid)
        if k:
            kline_out.append({"secid": secid, "name": name, "tag": "市场指数", **k})
    for p in picks:
        kline_out.append({"secid": p["secid"], "name": p["name"], "tag": p["sector"], **p["kline"]})

    scan = {"meta": meta, "indices": indices, "sectors": sectors[:12],
            "picks": [{k2: v2 for k2, v2 in p.items() if k2 != "kline"} for p in picks],
            "hot": build_hot_payload(ths_rows),
            "kline": kline_out}
    with open("scan.json", "w", encoding="utf-8") as f:
        json.dump(scan, f, ensure_ascii=False, separators=(",", ":"))
    # 全股票池(供策略胜率统计, 不落K线图)
    with open("universe.json", "w", encoding="utf-8") as f:
        json.dump([{k2: v2 for k2, v2 in s.items() if k2 != "kline"}
                   | {"close": s["kline"]["close"], "open": s["kline"]["open"],
                      "dates": s["kline"]["dates"]}
                   for s in universe], f, ensure_ascii=False, separators=(",", ":"))

    print("=" * 50)
    print(f"大盘状态: {market_status} (评分{market_score})")
    print(f"推荐 {len(picks)} 只:")
    for p in picks:
        print(f"  {p['name']}({p['sector']}) 评分{p['score']} 现价{p['price']} "
              f"止损{p['stop']} 目标{p['target']}  [{','.join(p['signals'][:3])}]")
    print("saved scan.json / universe.json")


if __name__ == "__main__":
    main()
