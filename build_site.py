# -*- coding: utf-8 -*-
"""生成精美单文件网站: 量化实验室 (扫描选股 + 策略回测对比)"""
import json

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#0a0e17">
<title>QuantLab · A股量化扫描实验室</title>
<style>
:root{
  --bg:#0a0e17; --panel:#0f1524; --panel2:#141b2e; --panel3:#182136;
  --line:rgba(148,163,184,.10); --line2:rgba(148,163,184,.18);
  --txt:#e6ebf4; --mut:#8290ab; --dim:#5b6885;
  --up:#ff4d4f; --down:#00c48c; --gold:#f5c451;
  --acc:#4f7cff; --acc2:#22d3ee; --violet:#8b5cf6;
  --grad:linear-gradient(135deg,#4f7cff 0%,#22d3ee 100%);
  --gradG:linear-gradient(135deg,#f5c451,#ff8a4c);
  --r:14px;
  --mono:ui-monospace,"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{background:
  radial-gradient(1200px 500px at 85% -10%,rgba(79,124,255,.10),transparent 60%),
  radial-gradient(900px 420px at -10% 10%,rgba(139,92,246,.08),transparent 55%),
  var(--bg);
  color:var(--txt); font:14px/1.6 "Segoe UI",-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased}
::selection{background:rgba(79,124,255,.35)}
a{color:inherit;text-decoration:none}
.wrap{max-width:1240px;margin:0 auto;padding:0 22px}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.up{color:var(--up)} .down{color:var(--down)} .gold{color:var(--gold)}

/* ---------- nav ---------- */
nav{position:sticky;top:0;z-index:50;backdrop-filter:blur(14px);
  background:rgba(10,14,23,.78);border-bottom:1px solid var(--line)}
.nav-in{display:flex;align-items:center;gap:18px;height:58px}
.logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;letter-spacing:.3px}
.logo .mark{width:30px;height:30px;border-radius:9px;background:var(--grad);
  display:grid;place-items:center;color:#fff;font-size:15px;box-shadow:0 4px 14px rgba(79,124,255,.4)}
.logo em{font-style:normal;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.nav-links{display:flex;gap:4px;margin-left:14px}
.nav-links a{padding:6px 12px;border-radius:8px;color:var(--mut);font-size:13.5px;transition:.2s}
.nav-links a:hover{color:var(--txt);background:rgba(148,163,184,.08)}
.nav-right{margin-left:auto;display:flex;align-items:center;gap:10px}
.pill{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:99px;
  font-size:12.5px;border:1px solid var(--line2);color:var(--mut);background:rgba(148,163,184,.05)}
.pill b{color:var(--txt)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--down);box-shadow:0 0 8px var(--down);animation:pulse 2.2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}

/* ---------- hero ---------- */
.hero{padding:52px 0 30px;position:relative}
.hero .eyebrow{display:inline-flex;align-items:center;gap:8px;font-size:12.5px;letter-spacing:2.5px;
  color:var(--acc2);text-transform:uppercase;font-weight:600}
.hero h1{font-size:clamp(30px,4.6vw,46px);font-weight:800;letter-spacing:.5px;margin:10px 0 6px;
  background:linear-gradient(120deg,#fff 20%,#9db4ff 60%,#22d3ee 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.hero .sub{color:var(--mut);font-size:15px;max-width:640px}
.hero-meta{display:flex;flex-wrap:wrap;gap:12px;margin-top:22px}
.mstat{display:flex;align-items:center;gap:14px;padding:12px 18px;border-radius:var(--r);
  background:var(--panel);border:1px solid var(--line)}
.mstat .lbl{font-size:12px;color:var(--dim)}
.mstat .val{font-size:20px;font-weight:700}
.mstat .val small{font-size:12px;font-weight:500;color:var(--mut)}

/* ---------- sections ---------- */
section{padding:34px 0 8px;scroll-margin-top:70px}
.sec-head{display:flex;align-items:baseline;gap:12px;margin-bottom:18px}
.sec-head h2{font-size:20px;font-weight:700;letter-spacing:.3px}
.sec-head h2::before{content:"";display:inline-block;width:4px;height:18px;border-radius:3px;
  background:var(--grad);margin-right:10px;vertical-align:-2px}
.sec-head .tagline{color:var(--dim);font-size:12.5px}
.grid{display:grid;gap:14px}
.grid>*{min-width:0}

/* ---------- cards ---------- */
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:18px;min-width:0;
  transition:border-color .25s, transform .25s, box-shadow .25s}
.card:hover{border-color:var(--line2);transform:translateY(-2px);box-shadow:0 12px 32px rgba(0,0,0,.35)}

/* ---------- 选股跟踪 / 组合体检 ---------- */
.track-chips{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px}
.tch{flex:1 1 150px;padding:10px 14px;border-radius:12px;background:var(--panel);border:1px solid var(--line)}
.tch .l{font-size:11.5px;color:var(--dim)}
.tch .v{font-size:17px;font-weight:700;margin-top:2px}
.tch .v small{font-size:11px;font-weight:500;color:var(--mut)}
.track-note{color:var(--dim);font-size:11.5px;margin-top:10px;line-height:1.8}
.two-col{grid-template-columns:repeat(auto-fit,minmax(min(430px,100%),1fr))}
.card-t{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:10px}
.card-t b{font-size:14px}
.dim-note{color:var(--dim);font-size:11.5px}
.heat-scroll{overflow-x:auto;padding-bottom:6px}
.hm{border-collapse:separate;border-spacing:3px;font-size:12px}
.hm td{min-width:56px;height:24px;text-align:center;border-radius:5px;color:#eaf0fa;white-space:nowrap;font-variant-numeric:tabular-nums}
.hm td.hn{min-width:96px;text-align:left;padding:0 8px;color:var(--txt);background:transparent;font-weight:600}
.hm td.hmh{background:transparent;color:var(--mut);font-size:11px;padding:0 4px}

/* ---------- market ---------- */
.market-grid{grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.idx-top{display:flex;justify-content:space-between;align-items:flex-start}
.idx-name{font-weight:600}
.idx-name small{display:block;color:var(--dim);font-size:11.5px;font-weight:400;margin-top:1px}
.idx-score{font-size:13px;font-weight:700}
.idx-price{font-size:24px;font-weight:700;margin-top:8px}
.idx-chg{font-size:13px;margin-top:2px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.chip{font-size:11.5px;padding:3px 9px;border-radius:6px;background:rgba(79,124,255,.12);
  color:#9db4ff;border:1px solid rgba(79,124,255,.25)}
.gauge-card{display:flex;flex-direction:column;justify-content:center;align-items:center;
  background:linear-gradient(160deg,var(--panel2),var(--panel))}
.gauge-txt{margin-top:10px;text-align:center}
.gauge-txt .s{font-size:17px;font-weight:700}
.gauge-txt .d{font-size:12px;color:var(--dim);margin-top:2px}

/* ---------- intraday 盘中快照 ---------- */
.intra-bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 16px;border-radius:12px;
  background:rgba(34,211,238,.06);border:1px solid rgba(34,211,238,.22);margin-bottom:14px}
.live-badge{display:inline-flex;align-items:center;gap:7px;font-size:11.5px;font-weight:700;letter-spacing:1.5px;
  color:#22d3ee;background:rgba(34,211,238,.12);border:1px solid rgba(34,211,238,.3);padding:3px 11px;border-radius:99px}
.live-badge .dot{background:#22d3ee;box-shadow:0 0 8px #22d3ee}
.intra-phase{font-size:12.5px;font-weight:600}
.intra-note{color:var(--dim);font-size:12px;margin-left:auto}
.intra-strip{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px;margin-bottom:14px;scrollbar-width:thin}
.intra-strip .ix{flex:0 0 auto;padding:10px 16px;border-radius:12px;background:var(--panel);border:1px solid var(--line);min-width:148px}
.ix-name{font-size:12.5px;color:var(--mut)}
.ix-price{font-size:17px;font-weight:700;margin-top:2px}
.ix-chg{font-size:12.5px}
.intra-grid{grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}
.intra-card{display:flex;flex-direction:column;gap:10px;position:relative;overflow:hidden}
.intra-card::before{content:"";position:absolute;inset:0 0 auto 0;height:2px;background:var(--gradG);opacity:.55}
.intra-top2{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.intra-name{font-weight:700;font-size:15px}
.intra-name small{display:block;color:var(--dim);font-size:11px;font-weight:400;margin-top:1px}
.intra-chg{font-size:14px;font-weight:700;padding:3px 10px;border-radius:8px;background:rgba(148,163,184,.08);white-space:nowrap}
.intra-chg.up{background:rgba(255,77,79,.12)}
.intra-chg.down{background:rgba(0,196,140,.12)}
.intra-price-row{display:flex;align-items:baseline;gap:8px}
.intra-price{font-size:25px;font-weight:700}
.intra-pc{color:var(--dim);font-size:12px}
.intra-zone{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:2px}
.zone{background:var(--panel3);border-radius:10px;padding:8px 12px;text-align:center}
.zone .zl{font-size:11px;color:var(--dim)}
.zone .zv{font-size:13.5px;font-weight:600;font-family:var(--mono)}
.zone .zv small{color:var(--dim);font-weight:400}
.zone.danger{border:1px solid rgba(255,77,79,.4)}
.zone.danger .zv{color:var(--up)}
.zone.ok .zv{color:var(--down)}
.zone.gold .zv{color:var(--gold)}
.intra-warn{margin-top:2px;padding:6px 10px;border-radius:8px;font-size:12px;font-weight:600}
.intra-warn.w1{background:rgba(255,77,79,.14);color:#ff8a8c;border:1px solid rgba(255,77,79,.35)}
.intra-warn.w2{background:rgba(245,196,81,.12);color:var(--gold);border:1px solid rgba(245,196,81,.3)}
.intra-warn.gold{background:rgba(245,196,81,.15);color:var(--gold);border:1px solid rgba(245,196,81,.4)}

/* ---------- picks ---------- */
.picks-grid{grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}
.pick{display:flex;flex-direction:column;gap:12px;position:relative;overflow:hidden}
.pick::before{content:"";position:absolute;inset:0 0 auto 0;height:2px;
  background:var(--grad);opacity:0;transition:.25s}
.pick:hover::before{opacity:1}
.pick-top{display:flex;justify-content:space-between;align-items:flex-start}
.pick-sect{font-size:11px;color:var(--gold);letter-spacing:.5px}
.pick-name{font-size:16.5px;font-weight:700;margin-top:2px}
.pick-name small{color:var(--dim);font-size:12px;font-weight:400;margin-left:6px;font-family:var(--mono)}
.pick-price{font-size:22px;font-weight:700}
.ring-wrap{position:relative;width:52px;height:52px;flex:none}
.ring-wrap svg{transform:rotate(-90deg)}
.ring-txt{position:absolute;inset:0;display:grid;place-items:center;font-size:13px;font-weight:700;font-family:var(--mono)}
.sig-row{display:flex;flex-wrap:wrap;gap:6px;min-height:26px}
.pick-levels{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.lv{background:var(--panel3);border:1px solid var(--line);border-radius:9px;padding:7px 9px;text-align:center}
.lv .k{font-size:11px;color:var(--dim)}
.lv .v{font-size:13px;font-weight:600;margin-top:2px}
.lv .v.in{color:var(--up)} .lv .v.stop{color:var(--down)} .lv .v.tg{color:var(--gold)}
.pick-reason{font-size:12.5px;color:var(--mut);border-top:1px dashed var(--line2);padding-top:10px;line-height:1.65}

/* ---------- sectors ---------- */
.sector-list{display:flex;flex-direction:column;gap:8px}
.srow{display:grid;grid-template-columns:34px 1fr 96px 96px 70px 120px;align-items:center;gap:12px;
  padding:10px 14px;border-radius:10px;background:var(--panel);border:1px solid var(--line);transition:.2s}
.srow:hover{background:var(--panel2)}
.srank{font-family:var(--mono);font-size:13px;color:var(--dim)}
.srank.top{color:var(--gold);font-weight:700}
.sname{font-weight:600;font-size:13.5px}
.bar-wrap{height:6px;background:rgba(148,163,184,.1);border-radius:4px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px}
.smom{font-family:var(--mono);font-size:12px;color:var(--mut);text-align:right}
.vol-chip{font-size:11.5px;text-align:center;padding:2px 0;border-radius:6px;background:rgba(139,92,246,.13);color:#c4b5fd}
.srow .trend{font-size:15px;text-align:right;font-family:var(--mono)}

/* ---------- radar ---------- */
.radar-grid{grid-template-columns:1.35fr 1fr;align-items:stretch}
.strat-bars{display:flex;flex-direction:column;gap:12px}
.sbar{display:grid;grid-template-columns:150px 1fr 74px 96px;align-items:center;gap:12px}
.sbar .n{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sbar .track{height:22px;background:rgba(148,163,184,.07);border-radius:6px;overflow:hidden;position:relative}
.sbar .fill{height:100%;border-radius:6px;background:var(--grad);min-width:2px;
  display:flex;align-items:center;justify-content:flex-end;padding-right:8px}
.sbar .fill.best{background:var(--gradG);box-shadow:0 0 16px rgba(245,196,81,.35)}
.sbar .fill.neg{background:linear-gradient(90deg,#334155,#475569)}
.sbar .v{font-family:var(--mono);font-size:13px;text-align:right}
.sbar .beats{font-size:11.5px;color:var(--dim);text-align:right}
.insights{display:flex;flex-direction:column;gap:12px}
.insight{display:flex;gap:12px;align-items:flex-start;padding:14px;border-radius:12px;
  background:var(--panel2);border:1px solid var(--line)}
.insight .ic{width:34px;height:34px;flex:none;border-radius:9px;display:grid;place-items:center;font-size:16px}
.insight .ic.i1{background:rgba(245,196,81,.14)} .insight .ic.i2{background:rgba(79,124,255,.14)}
.insight .ic.i3{background:rgba(0,196,140,.14)} .insight .ic.i4{background:rgba(139,92,246,.14)}
.insight .t{font-size:13px;font-weight:600}
.insight .d{font-size:12.5px;color:var(--mut);margin-top:2px;line-height:1.6}

/* ---------- backtest ---------- */
.ctrl-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px}
.ctrl-group{display:flex;flex-wrap:wrap;gap:7px;align-items:center}
.ctrl-lbl{font-size:12px;color:var(--dim);margin-right:2px}
.sym-chip{padding:6px 13px;border-radius:99px;font-size:12.5px;cursor:pointer;user-select:none;
  border:1px solid var(--line2);color:var(--mut);background:rgba(148,163,184,.05);transition:.2s}
.sym-chip:hover{color:var(--txt);border-color:rgba(148,163,184,.35)}
.sym-chip.on{background:var(--grad);color:#fff;border-color:transparent;font-weight:600;
  box-shadow:0 4px 14px rgba(79,124,255,.35)}
.strat-chip{padding:5px 11px;border-radius:8px;font-size:12px;cursor:pointer;user-select:none;
  border:1px solid var(--line2);color:var(--mut);transition:.2s;display:inline-flex;gap:6px;align-items:center}
.strat-chip .sw{width:9px;height:9px;border-radius:3px}
.strat-chip.on{color:var(--txt);background:rgba(79,124,255,.12);border-color:rgba(79,124,255,.4)}
.tabs{display:flex;gap:4px;background:var(--panel2);padding:4px;border-radius:10px;width:fit-content;border:1px solid var(--line)}
.tab{padding:6px 18px;border-radius:7px;font-size:13px;color:var(--mut);cursor:pointer;transition:.2s}
.tab.on{background:var(--grad);color:#fff;font-weight:600}
.range-row{display:flex;align-items:center;gap:12px;margin-top:12px}
.range-row input[type=range]{flex:1;accent-color:#4f7cff;height:4px}
.range-row .rv{font-family:var(--mono);font-size:12px;color:var(--dim);white-space:nowrap}
.chart-box{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:var(--r);
  padding:14px 12px 8px;margin-top:14px}
.chart-box canvas{display:block;width:100%;height:auto}
.chart-title{font-size:13px;color:var(--mut);padding:0 6px 8px;display:flex;justify-content:space-between}
.chart-legend{display:flex;flex-wrap:wrap;gap:10px;padding:8px 6px 4px}
.legend-item{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--mut);cursor:pointer}
.legend-item .sw{width:10px;height:3px;border-radius:2px}
.tbl-wrap{overflow-x:auto;margin-top:14px;border:1px solid var(--line);border-radius:var(--r);background:var(--panel)}
.tbl-scroll{max-height:62vh;overflow:auto;-webkit-overflow-scrolling:touch}
.tbl-scroll th{position:sticky;top:0;background:var(--panel2);z-index:2;box-shadow:0 1px 0 var(--line2)}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:860px}
th,td{padding:9px 12px;text-align:right;white-space:nowrap}
th{color:var(--dim);font-weight:600;font-size:12px;border-bottom:1px solid var(--line2);cursor:pointer;user-select:none}
th:hover{color:var(--txt)}
th .arr{font-size:10px;color:var(--acc2)}
td:first-child,th:first-child{text-align:left}
tbody tr{border-bottom:1px solid var(--line);transition:.15s}
tbody tr:last-child{border-bottom:none}
tbody tr:hover{background:var(--panel2)}
td.name{font-weight:600}
tr.bh td.name{color:var(--gold)}
.best-cell{color:var(--gold);font-weight:700}

/* ---------- footer ---------- */
footer{margin-top:44px;padding:26px 0 40px;border-top:1px solid var(--line);color:var(--dim);font-size:12.5px}
.foot-in{display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;align-items:center}
.warn{background:rgba(245,196,81,.08);border:1px solid rgba(245,196,81,.25);color:#e8cf8f;
  padding:10px 16px;border-radius:10px;font-size:12.5px;margin-bottom:18px}

/* ---------- mobile bottom nav ---------- */
.mtabs{display:none}

/* ---------- responsive ---------- */
@media(max-width:900px){
  .radar-grid{grid-template-columns:1fr}
  .nav-links{display:none}
  .srow{grid-template-columns:30px 1fr 80px 80px 56px;row-gap:6px}
  .srow .vol-chip{grid-column:3/5}
  .srow .trend{display:none}
  .sbar{grid-template-columns:110px 1fr 64px;row-gap:6px}
  .sbar .beats{grid-column:1/4;text-align:left}
  /* 手机端快捷导航：sticky 顶栏第二行，横向滑动，常驻可达 */
  .mtabs{display:flex;gap:6px;padding:0 16px 10px;overflow-x:auto;scrollbar-width:none;
    background:rgba(10,14,23,.82)}
  .mtabs::-webkit-scrollbar{display:none}
  .mtabs a{flex:0 0 auto;padding:8px 15px;border-radius:9px;font-size:13px;color:var(--mut);
    background:var(--panel2);border:1px solid var(--line);white-space:nowrap}
  section{scroll-margin-top:104px}
  .tbl-scroll{max-height:60vh}
}
@media(max-width:560px){
  .mstat{flex:1 1 100%}
  .hero{padding-top:36px}
  .wrap{padding:0 14px}
  /* 顶栏收紧：隐藏文案 pill，logo 不换行 */
  .nav-in{height:52px}
  .logo{white-space:nowrap}
  .logo .cn{display:none}
  #navAuto{display:none}
  .nav-right{gap:6px}
  .pill{padding:4px 10px;font-size:11.5px}
  .sec-head{flex-wrap:wrap;gap:6px}
  .sec-head h2{font-size:18px}
  .sec-head .tagline{display:block;width:100%;line-height:1.5}
  .dim-note,.track-note{font-size:12.5px}
  /* 表格瘦身：手机隐藏次要列（桌面不受影响），配合横向滚动兜底 */
  table{font-size:12.5px;min-width:0}
  th,td{padding:8px 8px}
  #trackTable th:nth-child(3),#trackTable td:nth-child(3),
  #trackTable th:nth-child(4),#trackTable td:nth-child(4),
  #trackTable th:nth-child(5),#trackTable td:nth-child(5),
  #trackTable th:nth-child(6),#trackTable td:nth-child(6),
  #trackTable th:nth-child(7),#trackTable td:nth-child(7){display:none}
  #metricTable th:nth-child(2),#metricTable td:nth-child(2),
  #metricTable th:nth-child(6),#metricTable td:nth-child(6),
  #metricTable th:nth-child(7),#metricTable td:nth-child(7),
  #metricTable th:nth-child(9),#metricTable td:nth-child(9),
  #metricTable th:nth-child(10),#metricTable td:nth-child(10){display:none}
  #optTable th:nth-child(2),#optTable td:nth-child(2),
  #optTable th:nth-child(6),#optTable td:nth-child(6),
  #optTable th:nth-child(7),#optTable td:nth-child(7){display:none}
  /* 触控目标加大 */
  .sym-chip,.strat-chip{padding:8px 14px;font-size:13px}
  .tab{padding:8px 16px}
  /* 盘中指数条更紧凑 */
  .intra-strip .ix{min-width:128px;padding:8px 12px}
  .intra-note{margin-left:0;width:100%}
  .sbar .n{font-size:12px}
  /* 板块行两行布局：排名+名称+涨幅 / 动量条全宽 + 量比，避免名称竖排 */
  .srow{grid-template-columns:30px 1fr 70px;row-gap:8px;padding:12px 14px}
  .srow .bar-wrap{grid-column:1/4}
  .srow .vol-chip{grid-column:1/4;text-align:left;justify-self:start;padding:3px 12px}
  .srow .sname{font-size:13px}
}
</style>
</head>
<body>

<nav>
  <div class="wrap nav-in">
    <div class="logo"><span class="mark">◆</span><em>QuantLab</em><span class="cn">&nbsp;量化实验室</span></div>
    <div class="nav-links">
      <a href="#market">大盘扫描</a>
      <a href="#picks">今日精选</a>
      <a href="#sectors">板块扫描</a>
      <a href="#radar">策略雷达</a>
      <a href="#backtest">回测对比</a>
    </div>
    <div class="nav-right">
      <span class="pill"><span class="dot"></span><b id="navAuto">盘中每小时更新 · 收盘定稿</b></span>
      <span class="pill mono" id="navTime"></span>
    </div>
  </div>
  <!-- 手机端快捷导航（sticky 随顶栏常驻，横向滑动） -->
  <div class="mtabs" id="mtabs" aria-label="页面快捷导航">
    <a href="#market">大盘</a>
    <a href="#intraday">快照</a>
    <a href="#picks">精选</a>
    <a href="#track">跟踪</a>
    <a href="#sectors">板块</a>
    <a href="#radar">雷达</a>
    <a href="#analytics">体检</a>
    <a href="#backtest">回测</a>
    <a href="#" data-top>顶部</a>
  </div>
</nav>

<div class="wrap">

  <!-- HERO -->
  <div class="hero">
    <div class="eyebrow">TOP-DOWN QUANT SCANNER · 自上而下扫描</div>
    <h1>每日 A 股量化扫描实验室</h1>
    <p class="sub">先扫描大盘定仓位基调 → 再扫描板块找强势方向 → 最后在强势板块里筛选多信号共振个股，并对 7 大策略做回测收益对比。</p>
    <div class="hero-meta">
      <div class="mstat">
        <div><div class="lbl">大盘研判</div><div class="val" id="heroStatus"></div></div>
        <div class="ring-wrap" style="width:44px;height:44px" id="heroRing"></div>
      </div>
      <div class="mstat"><div><div class="lbl">扫描板块</div><div class="val mono" id="heroSectors"></div></div></div>
      <div class="mstat"><div><div class="lbl">个股池</div><div class="val mono" id="heroUniverse"></div></div></div>
      <div class="mstat"><div><div class="lbl">今日推荐</div><div class="val mono" id="heroPicks"></div></div></div>
    </div>
  </div>

  <!-- MARKET -->
  <section id="market">
    <div class="sec-head"><h2>大盘扫描</h2><span class="tagline">三大指数趋势评分，决定仓位基调</span></div>
    <div class="grid market-grid" id="marketGrid"></div>
  </section>

  <!-- INTRADAY -->
  <section id="intraday">
    <div class="sec-head"><h2>盘中快照</h2><span class="tagline">60分钟K线 · 小时级信号 · 价格每30秒实时刷新</span></div>
    <div class="intra-bar">
      <span class="live-badge"><span class="dot"></span>LIVE</span>
      <span class="mono" id="intraTs"></span>
      <span class="live-badge" id="intraLive" style="display:none;background:rgba(0,196,140,.15);color:#00c48c"><span class="dot"></span>实时</span>
      <span class="mono" id="intraLiveTs" style="display:none"></span>
      <span class="intra-phase" id="intraPhase"></span>
      <span class="intra-note" id="intraNote"></span>
    </div>
    <div class="intra-strip" id="intraIdx"></div>
    <div class="grid intra-grid" id="intraGrid"></div>
  </section>

  <!-- PICKS -->
  <section id="picks">
    <div class="sec-head"><h2>今日精选</h2><span class="tagline">强势板块 × 多信号共振 · 含参考价位</span></div>
    <div class="grid picks-grid" id="picksGrid"></div>
  </section>

  <!-- TRACK 历史推荐跟踪 -->
  <section id="track">
    <div class="sec-head"><h2>历史推荐跟踪</h2><span class="tagline">以推荐日收盘价买入, 统计 +1/+3/+5 交易日实际涨跌, 检验选股命中率</span></div>
    <div class="track-chips" id="trackChips"></div>
    <div class="card" style="padding:8px 12px">
      <div class="tbl-wrap tbl-scroll">
        <table id="trackTable">
          <thead><tr><th>推荐日</th><th>标的</th><th>推荐价</th><th>止损</th><th>目标</th><th>+1日</th><th>+3日</th><th>+5日</th><th>区间结果</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
    <div class="track-note" id="trackNote"></div>
  </section>

  <!-- SECTORS -->
  <section id="sectors">
    <div class="sec-head"><h2>板块扫描</h2><span class="tagline">全行业动量排名，向上溯源选股方向</span></div>
    <div class="card" style="padding:10px 8px">
      <div class="sector-list" id="sectorList"></div>
    </div>
  </section>

  <!-- RADAR -->
  <section id="radar">
    <div class="sec-head"><h2>策略雷达</h2><span class="tagline">全股票池回测统计：哪个策略平均收益最高、最常跑赢基准</span></div>
    <div class="grid radar-grid">
      <div class="card">
        <div class="strat-bars" id="stratBars"></div>
      </div>
      <div class="insights" id="insights"></div>
    </div>
  </section>

  <!-- ANALYTICS 组合体检 + 参数寻优 -->
  <section id="analytics">
    <div class="sec-head"><h2>组合体检</h2><span class="tagline">持仓相关性(找同涨同跌的对) + 月度收益热力图(看风格轮动/防守窗口)</span></div>
    <div class="grid two-col">
      <div class="card">
        <div class="card-t"><b>持仓相关性矩阵</b><span class="dim-note" id="corrNote"></span></div>
        <div class="heat-scroll" id="corrHeat"></div>
      </div>
      <div class="card">
        <div class="card-t"><b>月度收益热力图</b><span class="dim-note">红涨绿跌</span></div>
        <div class="heat-scroll" id="monHeat"></div>
      </div>
    </div>
    <div class="sec-head" style="margin-top:30px"><h2>参数寻优</h2><span class="tagline">前60%样本内选最优参数 → 后40%样本外验证 · 若最优参数样本外不及当前参数, 说明是过拟合, 不建议更换</span></div>
    <div class="card" style="padding:8px 12px">
      <div class="tbl-wrap">
        <table id="optTable">
          <thead><tr><th>策略</th><th>当前参数</th><th>样本内最优</th><th>最优→样本外年化</th><th>当前→样本外年化</th><th>样本外夏普<br><span style="font-weight:400;color:var(--dim)">最优/当前</span></th><th>跑赢基准(最优)</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- BACKTEST -->
  <section id="backtest">
    <div class="sec-head"><h2>策略回测对比</h2><span class="tagline">同一标的跑 7 策略，含手续费印花税</span></div>
    <div class="ctrl-row">
      <span class="ctrl-lbl">标的</span>
      <div class="ctrl-group" id="symChips"></div>
    </div>
    <div class="ctrl-row">
      <span class="ctrl-lbl">策略</span>
      <div class="ctrl-group" id="stratChips"></div>
      <div style="flex:1"></div>
      <div class="tabs" id="btTabs">
        <div class="tab on" data-t="nav">净值曲线</div>
        <div class="tab" data-t="dd">回撤对比</div>
        <div class="tab" data-t="kline">K线图</div>
      </div>
    </div>
    <div class="range-row">
      <span class="rv" id="rangeLbl">最近 250 根K线</span>
      <input type="range" id="rangeSlider" min="60" max="10000" value="250" step="10">
      <span class="rv" id="rangeMax">全周期</span>
    </div>
    <div class="chart-box">
      <div class="chart-title"><span id="chartName"></span><span class="mono" id="chartHint">拖动十字线查看数值</span></div>
      <canvas id="chart" width="1180" height="460"></canvas>
      <div class="chart-legend" id="chartLegend"></div>
    </div>
    <div class="tbl-wrap">
      <table id="metricTable">
        <thead><tr>
          <th data-k="name">策略</th>
          <th data-k="totalRet">总收益<span class="arr"></span></th>
          <th data-k="annRet">年化<span class="arr"></span></th>
          <th data-k="mdd">最大回撤<span class="arr"></span></th>
          <th data-k="sharpe">夏普<span class="arr"></span></th>
          <th data-k="calmar">卡玛<span class="arr"></span></th>
          <th data-k="vol">年化波动<span class="arr"></span></th>
          <th data-k="winRate">胜率<span class="arr"></span></th>
          <th data-k="trades">交易次数<span class="arr"></span></th>
          <th data-k="avgHold">平均持仓(天)<span class="arr"></span></th>
        </tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <footer>
    <div class="warn">⚠ 免责声明：本站为技术研究与教学演示，不构成任何投资建议。量化策略存在失效风险，据此操作盈亏自负。</div>
    <div class="foot-in">
      <span>数据来源：东方财富公开行情接口（前复权日线）· 回测含佣金万2.5 + 卖出印花税</span>
      <span class="mono" id="footTime"></span>
    </div>
  </footer>
</div>

<script>
const SCAN = __SCAN__;
const RES = __RES__;
const INTRADAY = __INTRADAY__;
const TRACK = __TRACK__;
const ANAL = __ANAL__;

/* ============ 工具 ============ */
const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = (v,d=2) => v == null ? '—' : v.toFixed(d);
const pct = (v,d=1) => v == null ? '—' : (v*100).toFixed(d) + '%';
const cls = v => v > 0 ? 'up' : (v < 0 ? 'down' : '');
const sign = v => v > 0 ? '+' : '';
const STATUS_COLOR = {'强势上行':'#ff4d4f','震荡偏强':'#f5c451','中性观望':'#9db4ff','弱势防守':'#00c48c'};
const S_COLORS = {bh:'#f5c451',ma:'#4f7cff',macd:'#22d3ee',rsi:'#8b5cf6',boll:'#ff8a4c',mom:'#ff4d4f',kdj:'#f472b6',grid:'#00c48c'};

function ringSVG(score, size=52, id){
  const r = size/2 - 4, c = 2*Math.PI*r, off = c*(1-Math.min(score,100)/100);
  const col = score>=80 ? '#f5c451' : score>=60 ? '#4f7cff' : score>=45 ? '#22d3ee' : '#00c48c';
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="rgba(148,163,184,.12)" stroke-width="5"/>
    <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${col}" stroke-width="5"
      stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"
      style="transition:stroke-dashoffset 1s ease"/>
  </svg>`;
}
function sparkline(vals, w=120, h=38, color){
  if(!vals || vals.length < 2) return '';
  const min = Math.min(...vals), max = Math.max(...vals), span = max-min || 1;
  const pts = vals.map((v,i)=>`${(i/(vals.length-1)*w).toFixed(1)},${(h-3-(v-min)/span*(h-8)).toFixed(1)}`).join(' ');
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none"
    stroke="${color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

/* ============ 渲染: 盘中快照 ============ */
function renderIntraday(){
  if(!INTRADAY || (!(INTRADAY.picks||[]).length && !(INTRADAY.indices||[]).length)) return;
  $('#intraTs').textContent = '数据时间 ' + (INTRADAY.ts || '—');
  const ph = INTRADAY.phase || '';
  const phEl = $('#intraPhase');
  phEl.textContent = ph;
  phEl.style.color = ph==='收盘定稿' ? '#00c48c' : '#22d3ee';
  $('#intraNote').textContent = INTRADAY.note || '';
  const strip = $('#intraIdx'); strip.innerHTML = '';
  (INTRADAY.indices||[]).forEach(ix=>{
    strip.insertAdjacentHTML('beforeend', `
    <div class="ix" data-tx="${txCode(ix.secid, true)}">
      <div class="ix-name">${esc(ix.name)}</div>
      <div class="ix-price mono ${cls(ix.chg)}" data-qt="price">${fmt(ix.price,2)}</div>
      <div class="ix-chg mono ${cls(ix.chg)}" data-qt="chg">${sign(ix.chg)}${pct(ix.chg,2)}</div>
    </div>`);
  });
  const g = $('#intraGrid'); g.innerHTML = '';
  (INTRADAY.picks||[]).forEach(p=>{
    const warnHtml = (p.warn||[]).map(w=>{
      const k = w.includes('跌破') ? 'w1' : (w.includes('接近') ? 'w2' : 'gold');
      return `<div class="intra-warn ${k}">⚠ ${esc(w)}</div>`;
    }).join('');
    const sigs = (p.signals||[]).map(s=>`<span class="chip">${esc(s)}</span>`).join('');
    const stopD = p.stop ? ((p.price/p.stop-1)*100).toFixed(1) : null;
    const tgtD = p.target ? ((p.price/p.target-1)*100).toFixed(1) : null;
    g.insertAdjacentHTML('beforeend', `
    <div class="card intra-card" data-tx="${txCode(p.secid, false)}" data-stop="${p.stop||''}" data-target="${p.target||''}" data-pc="${p.prevClose||''}">
      <div class="intra-top2">
        <div class="intra-name">${esc(p.name)}<small>${esc(p.sector||'')} · ${esc(p.code)}</small></div>
        <div class="intra-chg mono ${cls(p.chg)}" data-qt="chg">${sign(p.chg)}${pct(p.chg,2)}</div>
      </div>
      <div class="intra-price-row">
        <span class="intra-price mono ${cls(p.chg)}" data-qt="price">${fmt(p.price,2)}</span>
        <span class="intra-pc">昨收 <b data-qt="pc">${fmt(p.prevClose,2)}</b></span>
      </div>
      <div class="intra-zone">
        <div class="zone" data-qt="stopZone">
          <div class="zl">止损位</div>
          <div class="zv">${p.stop?fmt(p.stop,2):'—'} <small data-qt="stopD">${stopD!=null?stopD+'%':''}</small></div>
        </div>
        <div class="zone ok" data-qt="tgtZone">
          <div class="zl">目标位</div>
          <div class="zv">${p.target?fmt(p.target,2):'—'} <small data-qt="tgtD">${tgtD!=null?tgtD+'%':''}</small></div>
        </div>
      </div>
      <div data-qt="warnBox">${warnHtml}</div>
      <div class="chips">${sigs}</div>
    </div>`);
  });
}

/* ============ 实时行情: 浏览器每30秒直连腾讯接口 ============ */
function updateNavTime(liveStr){
  const scanT = (SCAN.meta.generated || '').replace(/^\d{4}-/, '');
  const intraT = (INTRADAY && INTRADAY.ts ? INTRADAY.ts : '').replace(/^\d{4}-/, '');
  let s = '选股定稿 ' + scanT;
  if(intraT) s += ' · 盘中 ' + intraT;
  s += ' · 报价' + (liveStr ? liveStr : '实时刷新中');
  const el = $('#navTime');
  if(el) el.textContent = s;
}
const IDX_TX = {'1.000001':'sh000001','0.399001':'sz399001','0.399006':'sz399006'};
function txCode(secid, isIdx){
  if(isIdx && IDX_TX[secid]) return IDX_TX[secid];
  const mkt = secid.split('.')[0], code = secid.split('.')[1];
  return (mkt === '1' ? 'sh' : 'sz') + code;
}
function liveWarn(price, stop, target, name){
  const w = [];
  if(stop && price <= stop) w.push(`已跌破止损位 ${stop.toFixed(2)}，按纪律应止损离场`);
  else if(stop && price/stop-1 < 0.03) w.push(`接近止损位（距止损 ${((price/stop-1)*100).toFixed(1)}%）`);
  if(target && price >= target) w.push(`已触及目标位 ${target.toFixed(2)}，可分批止盈`);
  return w;
}
let LIVE_FAIL = 0;
async function pollLiveQuotes(){
  const cards = [...document.querySelectorAll('#intraday [data-tx]')];
  if(!cards.length) return;
  const codes = [...new Set(cards.map(c => c.dataset.tx))];
  try{
    const r = await fetch('https://qt.gtimg.cn/q=' + codes.join(','), {cache:'no-store'});
    const txt = new TextDecoder('gbk').decode(await r.arrayBuffer());
    const q = {};
    txt.split(';').forEach(seg=>{
      const m = seg.match(/v_(sh|sz)(\d{6})="([^"]*)/);
      if(!m) return;
      const f = m[3].split('~');
      if(f.length > 32) q[m[1]+m[2]] = {price:+f[3], pc:+f[4], chgP:+f[32]};
    });
    let updated = 0;
    cards.forEach(card=>{
      const d = q[card.dataset.tx];
      if(!d || !d.price) return;
      updated++;
      const chg = d.pc ? d.chgP/100 : 0;
      card.querySelectorAll('[data-qt]').forEach(el=>{
        const k = el.dataset.qt;
        if(k === 'price'){ el.textContent = fmt(d.price,2); el.className = el.className.replace(/up|down|flat/g,'') + ' ' + (chg>0?'up':chg<0?'down':'flat'); }
        else if(k === 'chg'){ el.textContent = sign(chg) + pct(chg,2); el.className = el.className.replace(/up|down|flat/g,'') + ' ' + (chg>0?'up':chg<0?'down':'flat'); }
        else if(k === 'pc'){ el.textContent = fmt(d.pc,2); }
        else if(k === 'stopD'){ const s=+card.dataset.stop; el.textContent = s ? ((d.price/s-1)*100).toFixed(1)+'%' : ''; }
        else if(k === 'tgtD'){ const t=+card.dataset.target; el.textContent = t ? ((d.price/t-1)*100).toFixed(1)+'%' : ''; }
      });
      const sz = +card.dataset.stop, tg = +card.dataset.target;
      card.querySelectorAll('[data-qt="stopZone"]').forEach(z=>z.classList.toggle('danger', !!sz && d.price<=sz));
      card.querySelectorAll('[data-qt="tgtZone"]').forEach(z=>z.classList.toggle('gold', !!tg && d.price>=tg));
      card.querySelectorAll('[data-qt="warnBox"]').forEach(b=>{
        const w = liveWarn(d.price, sz, tg);
        b.innerHTML = w.map(x=>{
          const k = x.includes('跌破') ? 'w1' : (x.includes('接近') ? 'w2' : 'gold');
          return `<div class="intra-warn ${k}">⚠ ${esc(x)}</div>`;
        }).join('');
      });
    });
    if(updated > 0){
      LIVE_FAIL = 0;
      const t = new Date();
      const hh = String(t.getHours()).padStart(2,'0'), mm = String(t.getMinutes()).padStart(2,'0'), ss = String(t.getSeconds()).padStart(2,'0');
      $('#intraLive').style.display = '';
      $('#intraLiveTs').style.display = '';
      $('#intraLiveTs').textContent = '报价 ' + hh + ':' + mm + ':' + ss;
      updateNavTime(hh + ':' + mm + ':' + ss);
    }
  }catch(e){
    LIVE_FAIL++;
    if(LIVE_FAIL >= 3) $('#intraLive').style.display = 'none';
  }
}
function startLiveQuotes(){
  pollLiveQuotes();
  setInterval(()=>{ if(!document.hidden) pollLiveQuotes(); }, 30000); /* 手机后台/熄屏时暂停轮询省电 */
  document.addEventListener('visibilitychange', ()=>{ if(!document.hidden) pollLiveQuotes(); });
}

/* ============ 渲染: 大盘 ============ */
function renderMarket(){
  const g = $('#marketGrid'); g.innerHTML = '';
  SCAN.indices.forEach(idx=>{
    const col = STATUS_COLOR[idx.score>=70?'强势上行':idx.score>=55?'震荡偏强':idx.score>=40?'中性观望':'弱势防守'];
    g.insertAdjacentHTML('beforeend', `
    <div class="card">
      <div class="idx-top">
        <div class="idx-name">${idx.name}<small>趋势评分</small></div>
        <div class="idx-score" style="color:${col}">${idx.score}</div>
      </div>
      <div class="idx-price mono ${cls(idx.chg)}">${fmt(idx.close)}</div>
      <div class="idx-chg mono ${cls(idx.chg)}">${sign(idx.chg)}${pct(idx.chg)}</div>
      <div style="margin-top:8px">${sparkline(LAST_CLOSES[idx.secid] || [], 200, 40, col)}</div>
      <div class="chips">${idx.signals.map(s=>`<span class="chip">${esc(s)}</span>`).join('')}</div>
    </div>`);
  });
  const ms = SCAN.meta.marketStatus, c = STATUS_COLOR[ms] || '#9db4ff';
  $('#heroStatus').textContent = ms;
  $('#heroStatus').style.color = c;
  $('#heroRing').innerHTML = ringSVG(SCAN.meta.marketScore, 44);
  $('#heroSectors').textContent = SCAN.meta.sectors + ' 个';
  $('#heroUniverse').textContent = SCAN.meta.universe + ' 只';
  $('#heroPicks').textContent = SCAN.picks.length + ' 只';
}

/* ============ 渲染: 精选 ============ */
function renderPicks(){
  const g = $('#picksGrid'); g.innerHTML = '';
  SCAN.picks.forEach(p=>{
    const sigs = (p.signals||[]).slice(0,4);
    g.insertAdjacentHTML('beforeend', `
    <div class="card pick">
      <div class="pick-top">
        <div>
          <div class="pick-sect">${esc(p.sector)} · 板块评分 ${p.sectorScore}</div>
          <div class="pick-name">${esc(p.name)}<small>${p.code}</small></div>
        </div>
        <div class="ring-wrap">${ringSVG(p.score,52)}<div class="ring-txt">${p.score}</div></div>
      </div>
      <div class="pick-price mono ${cls(p.chg)}">${fmt(p.price)} <span style="font-size:13px">${sign(p.chg)}${pct(p.chg)}</span></div>
      <div class="sig-row">${sigs.map(s=>`<span class="chip">${esc(s)}</span>`).join('')}</div>
      <div class="pick-levels">
        <div class="lv"><div class="k">参考入场</div><div class="v in mono">${fmt(p.entry)}</div></div>
        <div class="lv"><div class="k">止损参考</div><div class="v stop mono">${fmt(p.stop)}</div></div>
        <div class="lv"><div class="k">目标参考</div><div class="v tg mono">${fmt(p.target)}</div></div>
      </div>
      <div class="pick-reason">${esc(p.reason)}</div>
    </div>`);
  });
}

/* ============ 渲染: 板块 ============ */
function renderSectors(){
  const list = $('#sectorList'); list.innerHTML = '';
  const maxAbs = Math.max(...SCAN.sectors.map(s=>Math.abs(s.mom20)*100), 5);
  SCAN.sectors.forEach((s,i)=>{
    const w = Math.min(Math.abs(s.mom20)*100/maxAbs*100, 100);
    const col = s.mom20>=0 ? 'linear-gradient(90deg,#ff4d4f,#ff7a45)' : 'linear-gradient(90deg,#00c48c,#00a884)';
    list.insertAdjacentHTML('beforeend', `
    <div class="srow">
      <div class="srank ${i<3?'top':''}">${String(i+1).padStart(2,'0')}</div>
      <div class="sname">${esc(s.name)}</div>
      <div class="bar-wrap"><div class="bar-fill" style="width:${w.toFixed(1)}%;background:${col}"></div></div>
      <div class="smom ${cls(s.mom20)}">${sign(s.mom20)}${pct(s.mom20)}</div>
      <div class="vol-chip">量比 ${fmt(s.volRatio)}</div>
      <div class="trend ${s.trend?'up':'down'}">${s.trend?'▲':'▼'}</div>
    </div>`);
  });
}

/* ============ 渲染: 策略雷达 ============ */
function renderRadar(){
  const bars = $('#stratBars'); bars.innerHTML = '';
  const stats = RES.stats;
  const maxAnn = Math.max(...stats.map(s=>s.avgAnn), 1e-9);
  stats.forEach(s=>{
    const w = Math.max(Math.abs(s.avgAnn)/maxAnn*100, s.avgAnn>0?4:2);
    bars.insertAdjacentHTML('beforeend', `
    <div class="sbar">
      <div class="n" title="${esc(s.desc)}">${esc(s.name)}</div>
      <div class="track"><div class="fill ${s.isBest?'best':''} ${s.avgAnn<0?'neg':''}" style="width:${w.toFixed(1)}%"></div></div>
      <div class="v mono ${cls(s.avgAnn)}">${sign(s.avgAnn)}${pct(s.avgAnn)}</div>
      <div class="beats">跑赢基准 ${s.beats}/${s.count}</div>
    </div>`);
  });
  const best = stats[0], mostBeats = [...stats].sort((a,b)=>b.beats-a.beats)[0],
        lowDD = [...stats].sort((a,b)=>a.avgMdd-b.avgMdd)[0],
        lowDDv = stats[0].count;
  const bh = stats.find(s=>s.id==='bh');
  const insights = [
    {ic:'i1',t:'平均年化最高的策略：'+best.name, d:`在全股票池 ${best.count} 只标的上平均年化 ${pct(best.avgAnn)}，其中 ${best.beats} 只跑赢买入持有。`},
    {ic:'i2',t:'最常跑赢基准：'+mostBeats.name, d:`在 ${mostBeats.count} 只标的上共 ${mostBeats.beats} 次跑赢买入持有（胜率 ${Math.round(mostBeats.beats/mostBeats.count*100)}%），择时逻辑更具普适性。`},
    {ic:'i3',t:'回撤控制最好：'+lowDD.name, d: lowDD.id==='bh'
      ? `基准本身的平均最大回撤就最小（${pct(lowDD.avgMdd)}）——本期趋势行情中各择时策略均未改善回撤，风险厌恶型资金可关注网格交易等低波动替代。`
      : `平均最大回撤仅 ${pct(lowDD.avgMdd)}，显著低于买入持有的 ${pct(bh.avgMdd)}，适合风险厌恶型资金。`},
    {ic:'i4',t:'今日大盘：'+SCAN.meta.marketStatus, d: SCAN.meta.marketStatus==='弱势防守' ? '大盘趋势偏弱，建议轻仓参与强势板块，严格止损。' : '大盘趋势健康，可正常仓位运行策略，重点关注强势板块。'}
  ];
  $('#insights').innerHTML = insights.map(i=>`
    <div class="insight"><div class="ic ${i.ic}">◆</div>
      <div><div class="t">${i.t}</div><div class="d">${i.d}</div></div>
    </div>`).join('');
}

/* ============ 回测对比 ============ */
let curIdx = 0, selStrats = new Set(), curTab = 'nav', rangeN = 250, sortK = 'annRet', sortAsc = -1;
const chart = $('#chart'), ctx = chart.getContext('2d');
const DPR = window.devicePixelRatio || 1;
const LAST_CLOSES = {};
RES.detail.forEach(sym=>{ LAST_CLOSES[sym.secid] = sym.close.slice(-60); });

function renderControls(){
  const sc = $('#symChips'); sc.innerHTML = '';
  RES.detail.forEach((s,i)=>{
    sc.insertAdjacentHTML('beforeend', `<div class="sym-chip ${i===curIdx?'on':''}" data-i="${i}">${esc(s.name)}<span style="opacity:.55;margin-left:5px;font-size:11px">${esc(s.tag)}</span></div>`);
  });
  sc.querySelectorAll('.sym-chip').forEach(el=>el.onclick=()=>{ curIdx=+el.dataset.i; renderControls(); draw(); renderTable(); });
  const tc = $('#stratChips'); tc.innerHTML = '';
  const stats = RES.stats;
  stats.forEach(s=>{
    const on = selStrats.has(s.id);
    tc.insertAdjacentHTML('beforeend', `<div class="strat-chip ${on?'on':''}" data-id="${s.id}">
      <span class="sw" style="background:${S_COLORS[s.id]}"></span>${esc(s.name)}</div>`);
  });
  tc.querySelectorAll('.strat-chip').forEach(el=>el.onclick=()=>{
    const id = el.dataset.id;
    selStrats.has(id) ? selStrats.delete(id) : selStrats.add(id);
    if(!selStrats.size) selStrats.add('bh');
    renderControls(); draw(); renderTable();
  });
  $('#btTabs').querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
    $('#btTabs').querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
    t.classList.add('on'); curTab = t.dataset.t; draw();
  });
  const rs = $('#rangeSlider'); rs.oninput = ()=>{ rangeN = +rs.value; $('#rangeLbl').textContent = rangeN>=9000?'全周期':`最近 ${rangeN} 根K线`; draw(); };
}

/* 图表绘制 */
let CH = 460; /* 画布高度(逻辑px)，手机端自适应 */
function fitCanvas(){
  const w = chart.parentElement.clientWidth - 24;
  CH = w < 640 ? Math.min(460, Math.max(280, Math.round(w * 1.1))) : 460;
  chart.style.width = w + 'px';
  chart.style.height = CH + 'px';
  chart.width = w * DPR; chart.height = CH * DPR;
  ctx.setTransform(DPR,0,0,DPR,0,0);
}
function draw(){
  fitCanvas();
  if(curTab==='kline') drawKline(); else if(curTab==='dd') drawDD(); else drawNav();
}
function lines(sym){
  return sym.strategies.filter(s=>selStrats.has(s.id));
}
function axisSetup(n, padL=52, padR=16, padT=14, padB=34){
  const W = chart.width/DPR, H = CH;
  return {W,H,padL,padR,padT,padB, plotW:W-padL-padR, plotH:H-padT-padB};
}
function xPos(i, n, A){ return A.padL + i/(n-1)*A.plotW; }
function yPos(v, lo, hi, A){ return A.padT + (1-(v-lo)/(hi-lo))*A.plotH; }
function drawGridAndAxes(A, hi, lo, n, dates, yfmt){
  ctx.strokeStyle='rgba(148,163,184,.07)'; ctx.fillStyle='#5b6885'; ctx.font='11px Consolas,monospace'; ctx.textAlign='right';
  for(let g=0; g<=4; g++){
    const v = lo + (hi-lo)*g/4, y = yPos(v,lo,hi,A);
    ctx.beginPath(); ctx.moveTo(A.padL,y); ctx.lineTo(A.padL+A.plotW,y); ctx.stroke();
    ctx.fillText(yfmt(v), A.padL-6, y+4);
  }
  ctx.textAlign='center';
  const step = Math.max(1, Math.floor(n/8));
  for(let i=0;i<n;i+=step){ ctx.fillText(dates[i].slice(5), xPos(i,n,A), CH-10); }
  ctx.strokeStyle='rgba(148,163,184,.15)';
  ctx.beginPath(); ctx.moveTo(A.padL,A.padT); ctx.lineTo(A.padL,A.padT+A.plotH); ctx.lineTo(A.padL+A.plotW,A.padT+A.plotH); ctx.stroke();
}
function drawLegend(){
  const sym = RES.detail[curIdx], L = $('#chartLegend'); L.innerHTML = '';
  lines(sym).forEach(s=>{
    L.insertAdjacentHTML('beforeend', `<span class="legend-item"><span class="sw" style="background:${S_COLORS[s.id]}"></span>${esc(s.name)}</span>`);
  });
  if(curTab==='kline'){
    L.innerHTML += `<span class="legend-item"><span class="sw" style="background:#f5c451"></span>MA5</span><span class="legend-item"><span class="sw" style="background:#22d3ee"></span>MA20</span>`;
    const sig = lines(sym).filter(s=>s.id!=='bh');
    if(sig.length) sig.forEach(s=>{ L.insertAdjacentHTML('beforeend', `<span class="legend-item"><span style="color:${S_COLORS[s.id]}">▲▼</span>${esc(s.name)}</span>`); });
    else L.insertAdjacentHTML('beforeend', `<span class="legend-item" style="opacity:.6">勾选择时策略可显示其买卖点</span>`);
  }
}
function tooltipAt(px, n, A, sym, mode, from){
  const i = Math.round((px-A.padL)/A.plotW*(n-1));
  if(i<0||i>=n) return;
  const j = from + i;   // 可视区索引 -> 全序列索引
  const v = sym.close[j];
  let html = `<b>${sym.dates[j]}</b> 收 ${fmt(v)}`;
  if(mode==='kline'){ html += ` 开${fmt(sym.open[j])} 高${fmt(sym.high[j])} 低${fmt(sym.low[j])}`; }
  lines(sym).forEach(s=>{
    if(mode==='kline') return;
    const nav = s.nav[j], dd = s.dd[j];
    if(mode==='nav') html += `<br><span style="color:${S_COLORS[s.id]}">●</span>${esc(s.name)} ${fmt(nav,3)} (${pct(nav-1)})`;
    else html += `<br><span style="color:${S_COLORS[s.id]}">●</span>${esc(s.name)} ${pct(dd)}`;
  });
  return {i, html};
}
function drawNav(){
  const sym = RES.detail[curIdx], n = sym.dates.length, from = Math.max(0, n-rangeN), cnt = n-from;
  const ls = lines(sym), A = axisSetup(cnt);
  let lo = Infinity, hi = -Infinity;
  ls.forEach(s=>{ const seg = s.nav.slice(from); lo = Math.min(lo, ...seg); hi = Math.max(hi, ...seg); });
  const pad = (hi-lo)*.08 || .01; lo-=pad; hi+=pad;
  ctx.clearRect(0,0,chart.width/DPR,CH);
  drawGridAndAxes(A, hi, lo, cnt, sym.dates.slice(from), v=>fmt(v,2));
  ls.forEach(s=>{
    const seg = s.nav.slice(from);
    ctx.strokeStyle = S_COLORS[s.id]; ctx.lineWidth = s.id==='bh'?2.2:1.7; ctx.lineJoin='round';
    ctx.globalAlpha = s.id==='bh'?1:.85;
    ctx.beginPath();
    seg.forEach((v,i)=>{ const x=xPos(i,cnt,A), y=yPos(v,lo,hi,A); i?ctx.lineTo(x,y):ctx.moveTo(x,y); });
    ctx.stroke(); ctx.globalAlpha=1;
  });
  $('#chartName').textContent = `${sym.name} · 净值曲线（${from+1}~${n} 日）`;
  drawLegend();
  chart.onmousemove = e=>{
    const r = chart.getBoundingClientRect();
    const t = tooltipAt(e.clientX-r.left, cnt, A, sym, 'nav', from);
    if(!t) return;
    const x = xPos(t.i,cnt,A);
    ctx.save(); ctx.strokeStyle='rgba(148,163,184,.4)'; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(x,A.padT); ctx.lineTo(x,A.padT+A.plotH); ctx.stroke(); ctx.restore();
    drawTooltipBox(e.clientX-r.left, A.padT+8, t.html);
  };
  chart.onmouseleave = ()=>drawTooltipBox(null);
}
function drawDD(){
  const sym = RES.detail[curIdx], n = sym.dates.length, from = Math.max(0, n-rangeN), cnt = n-from;
  const ls = lines(sym), A = axisSetup(cnt);
  let lo = -0.05, hi = 0.02;
  ls.forEach(s=>{ lo = Math.min(lo, ...s.dd.slice(from)); });   // 数据自适应, 回撤超-60%也不会画出界
  ctx.clearRect(0,0,chart.width/DPR,CH);
  drawGridAndAxes(A, hi, lo, cnt, sym.dates.slice(from), v=>pct(v));
  ls.forEach(s=>{
    const seg = s.dd.slice(from);
    ctx.beginPath();
    seg.forEach((v,i)=>{ const x=xPos(i,cnt,A), y=yPos(v,lo,hi,A); i?ctx.lineTo(x,y):ctx.moveTo(x,y); });
    ctx.strokeStyle=S_COLORS[s.id]; ctx.lineWidth=1.7; ctx.stroke();
    ctx.lineTo(xPos(cnt-1,cnt,A), A.padT+A.plotH); ctx.lineTo(A.padL, A.padT+A.plotH); ctx.closePath();
    ctx.fillStyle=S_COLORS[s.id]; ctx.globalAlpha=.10; ctx.fill(); ctx.globalAlpha=1;
  });
  const worst = ls.reduce((a,s)=>Math.min(...a.dd.slice(from))<Math.min(...s.dd.slice(from))?a:s, ls[0]);
  const wi = from + worst.dd.slice(from).indexOf(Math.min(...worst.dd.slice(from)));
  const wx = xPos(wi-from,cnt,A), wy = yPos(worst.dd[wi],lo,hi,A);
  ctx.fillStyle='#f5c451'; ctx.font='bold 12px Consolas'; ctx.textAlign='left';
  ctx.fillText(`最深 ${pct(worst.dd[wi])} · ${sym.dates[wi]}`, wx+8, wy-6);
  ctx.strokeStyle='rgba(245,196,81,.5)'; ctx.setLineDash([4,3]);
  ctx.beginPath(); ctx.moveTo(wx,wy); ctx.lineTo(wx,A.padT+A.plotH); ctx.stroke(); ctx.setLineDash([]);
  $('#chartName').textContent = `${sym.name} · 回撤对比（${from+1}~${n} 日）`;
  drawLegend();
  chart.onmousemove = e=>{
    const r = chart.getBoundingClientRect();
    const t = tooltipAt(e.clientX-r.left, cnt, A, sym, 'dd', from);
    if(!t) return;
    const x = xPos(t.i,cnt,A);
    ctx.save(); ctx.strokeStyle='rgba(148,163,184,.4)'; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(x,A.padT); ctx.lineTo(x,A.padT+A.plotH); ctx.stroke(); ctx.restore();
    drawTooltipBox(e.clientX-r.left, A.padT+8, t.html);
  };
  chart.onmouseleave = ()=>drawTooltipBox(null);
}
function drawKline(){
  const sym = RES.detail[curIdx], n = sym.dates.length, from = Math.max(0, n-rangeN), cnt = n-from;
  const A = axisSetup(cnt, 56, 16, 16, 78);
  const o=sym.open, h=sym.high, l=sym.low, c=sym.close, v=sym.volume;
  let lo = Math.min(...l.slice(from)), hi = Math.max(...h.slice(from));
  const pad = (hi-lo)*.1; lo-=pad; hi+=pad;
  ctx.clearRect(0,0,chart.width/DPR,CH);
  drawGridAndAxes(A, hi, lo, cnt, sym.dates.slice(from), x=>fmt(x));
  // 成交量
  const vMax = Math.max(...v.slice(from));
  ctx.fillStyle='rgba(148,163,184,.25)';
  for(let i=0;i<cnt;i++){
    const x = xPos(i,cnt,A), bw = Math.max(1.2, A.plotW/cnt*.6);
    const vh = (v[from+i]/vMax)*(A.plotH*.13);
    ctx.fillStyle = c[from+i]>=o[from+i] ? 'rgba(255,77,79,.45)' : 'rgba(0,196,140,.45)';
    ctx.fillRect(x-bw/2, A.padT+A.plotH+6-vh, bw, vh);
  }
  // 蜡烛
  const bw = Math.max(1, A.plotW/cnt*.62);
  for(let i=0;i<cnt;i++){
    const j=from+i, x=xPos(i,cnt,A), up=c[j]>=o[j], col=up?'#ff4d4f':'#00c48c';
    ctx.strokeStyle=col; ctx.fillStyle=col; ctx.lineWidth=1;
    ctx.beginPath(); ctx.moveTo(x,yPos(l[j],lo,hi,A)); ctx.lineTo(x,yPos(h[j],lo,hi,A)); ctx.stroke();
    const y1=yPos(Math.max(o[j],c[j]),lo,hi,A), y2=yPos(Math.min(o[j],c[j]),lo,hi,A);
    if(y2-y1<1){ ctx.fillRect(x-bw/2, y1-0.5, bw, 1); }
    else ctx.fillRect(x-bw/2, y1, bw, Math.max(1,y2-y1));
  }
  // MA5 / MA20
  const ma5 = SMA(c,5), ma20 = SMA(c,20);
  drawLine(ma5.slice(from), 'f5c451', 1.4, A, cnt, lo, hi);
  drawLine(ma20.slice(from), '22d3ee', 1.4, A, cnt, lo, hi);
  // 买卖信号：跟随当前勾选的策略（各自用与曲线一致的颜色，纵向错开避免重叠）
  const sigStrats = lines(sym).filter(s=>s.id!=='bh');
  ctx.font='bold 10px sans-serif'; ctx.textAlign='center';
  sigStrats.forEach((s,k)=>{
    const col = S_COLORS[s.id], dy = k*10;
    (s.trades||[]).forEach(t=>{
      const bi = t.bi-from, si = (t.si==null?-1:t.si)-from;
      if(bi>=0&&bi<cnt){ const x=xPos(bi,cnt,A), y=Math.min(yPos(l[from+bi],lo,hi,A)+7+dy, A.padT+A.plotH-4);
        ctx.fillStyle=col; ctx.beginPath();
        ctx.moveTo(x,y); ctx.lineTo(x+5,y+7); ctx.lineTo(x-5,y+7); ctx.closePath(); ctx.fill(); }
      if(si>=0&&si<cnt){ const x=xPos(si,cnt,A), y=Math.max(yPos(h[from+si],lo,hi,A)-7-dy, A.padT+3);
        ctx.fillStyle=col; ctx.beginPath();
        ctx.moveTo(x,y); ctx.lineTo(x+5,y-7); ctx.lineTo(x-5,y-7); ctx.closePath(); ctx.fill(); }
    });
  });
  $('#chartName').textContent = `${sym.name} · K线（${from+1}~${n} 日） · 红涨绿跌 · 买卖点随所选策略着色`;
  drawLegend();
  chart.onmousemove = e=>{
    const r = chart.getBoundingClientRect();
    const t = tooltipAt(e.clientX-r.left, cnt, A, sym, 'kline', from);
    if(!t) return;
    const x = xPos(t.i,cnt,A);
    ctx.save(); ctx.strokeStyle='rgba(148,163,184,.4)'; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(x,A.padT); ctx.lineTo(x,A.padT+A.plotH); ctx.stroke(); ctx.restore();
    drawTooltipBox(e.clientX-r.left, A.padT+8, t.html);
  };
  chart.onmouseleave = ()=>drawTooltipBox(null);
}
function drawLine(arr, hex, w, A, cnt, lo, hi){
  ctx.strokeStyle='#'+hex; ctx.lineWidth=w; ctx.beginPath();
  arr.forEach((v,i)=>{ if(v==null) return; const x=xPos(i,cnt,A), y=yPos(v,lo,hi,A); i&&arr[i-1]!=null?ctx.lineTo(x,y):ctx.moveTo(x,y); });
  ctx.stroke();
}
function SMA(x,n){
  const out = new Array(x.length).fill(null); let s=0;
  for(let i=0;i<x.length;i++){ s+=x[i]; if(i>=n) s-=x[i-n]; if(i>=n-1) out[i]=s/n; }
  return out;
}
function drawTooltipBox(x, y, html){
  const tt = $('#tip') || (()=>{ const d=document.createElement('div'); d.id='tip';
    d.style.cssText='position:absolute;pointer-events:none;background:rgba(10,14,23,.92);border:1px solid rgba(148,163,184,.25);border-radius:8px;padding:8px 11px;font-size:12px;color:#e6ebf4;z-index:9;box-shadow:0 8px 24px rgba(0,0,0,.4);backdrop-filter:blur(6px)';
    $('.chart-box').appendChild(d); return d; })();
  if(html==null){ tt.style.display='none'; return; }
  tt.style.display='block'; tt.innerHTML = html;
  const r = chart.getBoundingClientRect();
  let tx = x+14, ty = y;
  if(tx+180 > r.width) tx = x-190;
  if(ty+80 > CH) ty = CH-90;
  tt.style.left = tx+'px'; tt.style.top = ty+'px';
}

/* ============ 指标表 ============ */
function renderTable(){
  const sym = RES.detail[curIdx], ls = lines(sym);
  const tbody = $('#metricTable tbody'); tbody.innerHTML = '';
  ls.slice().sort((a,b)=>{
    const av = sortK==='name'?a.name:b.metrics[sortK] ?? -1e9;
    const bv = sortK==='name'?b.name:a.metrics[sortK] ?? -1e9;
    return (av<bv?-1:av>bv?1:0)*sortAsc;
  }).forEach(s=>{
    const m = s.metrics;
    const best = s.id !== 'bh' && ls.some(o=>o.id==='bh' && m.annRet > o.metrics.annRet);
    const bhM = ls.find(o=>o.id==='bh');
    tbody.insertAdjacentHTML('beforeend', `<tr class="${s.id==='bh'?'bh':''}">
      <td class="name">${esc(s.name)}${best?' <span class="best-cell">★</span>':''}</td>
      <td class="mono ${cls(m.totalRet)}">${sign(m.totalRet)}${pct(m.totalRet)}</td>
      <td class="mono ${cls(m.annRet)}">${sign(m.annRet)}${pct(m.annRet)}</td>
      <td class="mono ${cls(m.mdd)}">${pct(m.mdd)}</td>
      <td class="mono">${fmt(m.sharpe)}</td>
      <td class="mono">${fmt(m.calmar)}</td>
      <td class="mono">${pct(m.vol)}</td>
      <td class="mono">${m.winRate==null?'—':pct(m.winRate)}</td>
      <td class="mono">${m.trades}</td>
      <td class="mono">${m.avgHold==null?'—':fmt(m.avgHold,0)}</td>
    </tr>`);
  });
  $$('#metricTable th').forEach(th=>th.onclick=()=>{
    const k = th.dataset.k;
    if(sortK===k) sortAsc*=-1; else { sortK=k; sortAsc = (k==='name'?1:-1); }
    $$('#metricTable th').forEach(x=>x.querySelector('.arr').textContent = x.dataset.k===k?(sortAsc>0?'↓':'↑'):'');
    renderTable();
  });
  { const el = $('#metricTable th[data-k="name"] .arr'); if(el) el.textContent = sortK==='name'?(sortAsc>0?'↓':'↑'):''; }
}

/* ============ 渲染: 历史推荐跟踪 ============ */
const cellRet = v => v==null ? '<span style="color:var(--dim)">…</span>' : `<span class="${v>0?'up':'down'}" style="font-weight:600">${sign(v)}${pct(v,1)}</span>`;
function renderTrack(){
  const sec = $('#track');
  if(!TRACK || !(TRACK.records||[]).length){ if(sec) sec.style.display='none'; return; }
  const st = TRACK.stats || {};
  const chips = [
    ['累计推荐', st.total+' 只'],
    ['已满5日评估', st.matured+' 只'],
    ['待评估', st.pending+' 只'],
    ['+5日命中率', st.hit5Rate==null?'积累中':(st.hit5Rate*100).toFixed(0)+'%'],
    ['+5日平均收益', st.avg5==null?'—':sign(st.avg5)+(st.avg5*100).toFixed(2)+'%'],
    ['触目标 / 触止损', (st.target||0)+' / '+(st.stop||0)],
  ];
  $('#trackChips').innerHTML = chips.map(c=>`<div class="tch"><div class="l">${c[0]}</div><div class="v">${c[1]}</div></div>`).join('');
  const tbody = $('#trackTable tbody'); tbody.innerHTML = '';
  TRACK.records.slice().reverse().forEach(r=>{
    const out = r.outcome==null ? '<span style="color:var(--dim)">跟踪中…</span>'
      : r.outcome==='target' ? '<span class="up" style="font-weight:700">触目标 ✓</span>'
      : r.outcome==='stop' ? '<span class="down" style="font-weight:700">触止损 ✗</span>'
      : '<span style="color:var(--mut)">区间内</span>';
    tbody.insertAdjacentHTML('beforeend', `<tr>
      <td class="mono">${esc((r.date||'').slice(5))}</td>
      <td><b>${esc(r.name||'')}</b> <span style="color:var(--dim)">${esc(r.sector||'')}</span></td>
      <td class="mono">${fmt(r.entry,2)}</td>
      <td class="mono" style="color:var(--down)">${r.stop?fmt(r.stop,2):'—'}</td>
      <td class="mono" style="color:var(--up)">${r.target?fmt(r.target,2):'—'}</td>
      <td class="mono">${cellRet(r.r1)}</td>
      <td class="mono">${cellRet(r.r3)}</td>
      <td class="mono">${cellRet(r.r5)}</td>
      <td>${out}</td>
    </tr>`);
  });
  const firstDate = TRACK.records[0].date || '';
  $('#trackNote').textContent = `口径: 以推荐日收盘价买入, 之后每满 1/3/5 个交易日按收盘价结算(红涨绿跌); 触目标/触止损以区间内当日最高/最低价判断, 先到哪个算哪个。数据自 ${firstDate} 起每日收盘后自动累积, 满5个交易日后进入命中率统计。`;
}

/* ============ 渲染: 组合体检 ============ */
const heatStyle = (v, scale) => {
  if(v==null) return '';
  const a = Math.min(Math.abs(v)/scale, 1).toFixed(3);
  return v>0 ? `background:rgba(255,77,79,${a})` : `background:rgba(0,196,140,${a})`;
};
function renderAnalytics(){
  const sec = $('#analytics');
  if(!ANAL || !ANAL.corr || !(ANAL.corr.names||[]).length){ if(sec) sec.style.display='none'; return; }
  const {names, mat} = ANAL.corr;
  $('#corrNote').textContent = `最近${ANAL.corr.bars||120}个交易日 · 红=同向 绿=反向`;
  let h = '<table class="hm"><tr><td class="hn"></td>' + names.map(n=>`<td class="hmh">${esc(String(n).slice(0,4))}</td>`).join('') + '</tr>';
  mat.forEach((row,i)=>{
    h += `<tr><td class="hn">${esc(names[i])}</td>`;
    row.forEach((v,j)=>{
      h += i===j
        ? `<td style="background:rgba(148,163,184,.2);color:var(--mut)">${v.toFixed(2)}</td>`
        : `<td style="${heatStyle(v,1)}">${v.toFixed(2)}</td>`;
    });
    h += '</tr>';
  });
  $('#corrHeat').innerHTML = h + '</table>';
  const M = ANAL.monthly;
  if(M && M.rows && M.rows.length){
    const all = [];
    M.rows.forEach(r=>r.rets.forEach(v=>{ if(v!=null) all.push(Math.abs(v)); }));
    const scale = Math.max.apply(null, all.concat([0.05]));
    let t = '<table class="hm"><tr><td class="hn"></td>' + M.months.map(m=>`<td class="hmh">${esc(String(m).slice(2))}</td>`).join('') + '</tr>';
    M.rows.forEach(r=>{
      t += `<tr><td class="hn">${esc(r.name)}</td>`;
      r.rets.forEach(v=>{
        t += v==null
          ? `<td style="background:rgba(148,163,184,.08);color:var(--dim)">·</td>`
          : `<td style="${heatStyle(v,scale)}">${(v*100).toFixed(1)}</td>`;
      });
      t += '</tr>';
    });
    $('#monHeat').innerHTML = t + '</table>';
  }
  const opt = ANAL.opt || [];
  const tb = $('#optTable tbody'); tb.innerHTML = '';
  if(!opt.length){
    tb.insertAdjacentHTML('beforeend', '<tr><td colspan="7" style="color:var(--dim);text-align:center;padding:14px">参数寻优尚未运行</td></tr>');
    return;
  }
  opt.forEach(r=>{
    const diff = r.bestOosAnn - r.curOosAnn;
    const tag = diff > 0.005 ? '<span class="up">建议换用</span>'
      : diff < -0.005 ? '<span class="down">过拟合·保持当前</span>'
      : '<span style="color:var(--mut)">无差异</span>';
    tb.insertAdjacentHTML('beforeend', `<tr>
      <td><b>${esc(r.name)}</b></td>
      <td class="mono">${esc((r.current||'').replace('(当前)',''))}</td>
      <td class="mono" style="color:var(--gold)">${esc((r.best||'').replace('(当前)',''))}</td>
      <td class="mono ${cls(r.bestOosAnn)}">${sign(r.bestOosAnn)}${pct(r.bestOosAnn)}</td>
      <td class="mono ${cls(r.curOosAnn)}">${sign(r.curOosAnn)}${pct(r.curOosAnn)}</td>
      <td class="mono">${fmt(r.bestOosSharpe)} / ${fmt(r.curOosSharpe)}</td>
      <td class="mono">${r.bestOosBeat}/${r.n} <span style="font-weight:500">${tag}</span></td>
    </tr>`);
  });
}

/* ============ init ============ */
(function init(){
  selStrats = new Set(['bh','ma','macd']);
  updateNavTime();
  $('#footTime').textContent = 'Generated ' + SCAN.meta.generated;
  renderMarket(); renderPicks(); renderSectors(); renderRadar();
  renderIntraday();
  renderTrack(); renderAnalytics();
  renderControls(); draw(); renderTable();
  startLiveQuotes();
  window.addEventListener('resize', draw);
})();
</script>
</body>
</html>
"""


def main():
    import os
    scan = json.load(open("scan.json", encoding="utf-8"))
    res = json.load(open("results.json", encoding="utf-8"))
    try:
        intraday = json.load(open("intraday.json", encoding="utf-8"))
    except Exception:
        intraday = {"ts": "", "phase": "", "picks": [], "indices": [],
                    "note": "盘中快照暂未生成（交易时段每小时自动更新）"}
    try:
        track = json.load(open("picks_history.json", encoding="utf-8"))
    except Exception:
        track = {"records": [], "stats": {}}
    try:
        anl = json.load(open("analytics.json", encoding="utf-8"))
        anl["opt"] = json.load(open("param_scan.json", encoding="utf-8")).get("rows", [])
    except Exception:
        anl = {"corr": None, "monthly": None, "opt": []}
    html = TEMPLATE.replace("__SCAN__", json.dumps(scan, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__RES__", json.dumps(res, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__INTRADAY__", json.dumps(intraday, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__TRACK__", json.dumps(track, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__ANAL__", json.dumps(anl, ensure_ascii=False, separators=(",", ":")))
    out = "量化实验室.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    os.makedirs("deploy", exist_ok=True)
    with open("deploy/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"saved {out}  ({len(html)/1024:.0f} KB)  + deploy/index.html")


if __name__ == "__main__":
    main()
