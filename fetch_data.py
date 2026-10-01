# -*- coding: utf-8 -*-
"""拉取真实A股日线数据(东方财富公开接口) -> data_raw.json"""
import json
import time
import urllib.request

SYMBOLS = [
    ("1.600519", "贵州茅台", "白酒龙头·大盘蓝筹"),
    ("0.300750", "宁德时代", "动力电池·高波动成长"),
    ("1.601318", "中国平安", "保险金融·低波动权重"),
    ("0.002594", "比亚迪",   "新能源车·趋势性强"),
    ("1.600036", "招商银行", "银行蓝筹·震荡分红"),
    ("1.000001", "上证指数", "市场基准指数"),
]

BEG, END = "20190101", "20260902"

def fetch(secid):
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
        f"&klt=101&fqt=1&beg={BEG}&end={END}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

out = []
for secid, name, tag in SYMBOLS:
    d = fetch(secid)["data"]
    dates, o, h, l, c, v = [], [], [], [], [], []
    for row in d["klines"]:
        p = row.split(",")
        dates.append(p[0])
        o.append(float(p[1])); c.append(float(p[2]))
        h.append(float(p[3])); l.append(float(p[4]))
        v.append(int(float(p[5])))
    out.append({
        "secid": secid, "name": name, "tag": tag,
        "dates": dates, "open": o, "high": h, "low": l, "close": c, "volume": v,
    })
    print(f"{name}: {len(dates)} bars, {dates[0]} ~ {dates[-1]}, last close {c[-1]}")
    time.sleep(0.5)

with open("data_raw.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print("saved data_raw.json")
