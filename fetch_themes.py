# -*- coding: utf-8 -*-
"""盘中题材/情绪快照: 只刷新 scan.json 的 hot(同花顺强势股/热门题材) 与 meta.sentiment(涨停温度),
不动选股结论(picks/评分) —— 由 intraday workflow 每小时调用, 降低题材热度滞后性。
任何失败都不中断: 保留旧数据, 由 build_site.py 照常构建。"""
import json
import os
from datetime import datetime

import scan


def main():
    if not os.path.exists("scan.json"):
        print("scan.json 不存在, 跳过题材刷新")
        return
    s = json.load(open("scan.json", encoding="utf-8"))
    rows = scan.fetch_ths_rows()
    hot = scan.build_hot_payload(rows)
    if hot:
        old = s.get("hot") or {}
        s["hot"] = hot
        s.setdefault("meta", {})["hotUpdated"] = hot["updated"]
        print(f"题材热度已刷新: {hot['total']} 只强势股, "
              f"热门题材: {'、'.join(t['tag'] for t in hot['themes'][:3])} (更新于 {hot['updated']})")
    else:
        old = s.get("hot")
        print("同花顺强势股拉取失败, 保留旧题材数据" + (f"({old['updated']})" if old else ""))
    sent = scan.fetch_limit_up_pool()
    if sent:
        s.setdefault("meta", {})["sentiment"] = sent
        print(f"涨停情绪温度: {sent['score']}({sent['label']})")

    # 建议仓位: 大盘趋势定基调 + 情绪温度修正 (与 scan.py 同一公式)
    W = scan.load_weights()
    TA = W.get("thresholdAdjust", scan.DEFAULT_WEIGHTS["thresholdAdjust"])
    ms = (s.get("meta") or {}).get("marketScore")
    if ms is not None:
        pos = (8 if ms >= 70 else 6 if ms >= 55 else 4 if ms >= 40 else 2)
        sent_now = (s.get("meta") or {}).get("sentiment")
        if sent_now:
            if sent_now["score"] < TA["sentimentIceBelow"]:
                pos -= 2
            elif sent_now["score"] > TA["sentimentHotAbove"]:
                pos += 1
        s["meta"]["position"] = max(0, min(9, pos))
        print(f"建议仓位: {s['meta']['position']} 成")
    with open("scan.json", "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, separators=(",", ":"))
    print("saved scan.json (hot/sentiment only)")


if __name__ == "__main__":
    main()
