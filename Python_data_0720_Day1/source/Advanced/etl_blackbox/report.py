"""=============================================================================
파일명: report.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: ETL 블랙박스 실행 결과를 인터랙티브 HTML 리포트로 생성

입력:
    시나리오와 실행 모드별 RunSummary 목록

주요 항목:
    핵심 지표 카드, 실행 시간 비교, p95 지연, 동시성 변화,
    성공·재시도·dead-letter 비교표

실행:
    python Advanced/etl_blackbox/main.py
=============================================================================
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    from Advanced.etl_blackbox.models import RunSummary
except ModuleNotFoundError:
    from models import RunSummary


def render_report(summaries: list[RunSummary], output_path: Path) -> None:
    """실행 결과를 외부 라이브러리 없는 단일 HTML 파일로 저장합니다."""
    data = json.dumps(
        [summary.model_dump(mode="json") for summary in summaries],
        ensure_ascii=False,
    ).replace("</", "<\\/")
    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ETL 블랙박스 · 복원력 관제 리포트</title>
<style>
:root{{--bg:#f4f4f1;--panel:#fbfbf9;--line:#e6e6e1;--text:#242522;--muted:#858680;
--accent:#3b3c38;--soft:#ededE8;--mid:#a2a39d}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);
font-family:"Pretendard","Pretendard JP",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
font-weight:400;letter-spacing:-0.015em;line-height:1.5}}
main{{width:min(1100px,calc(100% - 40px));margin:52px auto 72px}}
header{{padding:0 4px 26px}}
h1{{margin:6px 0 0;font-size:34px;font-weight:700;letter-spacing:-0.045em}}
.eyebrow{{color:var(--muted);font-size:13px;font-weight:500}}
.sub{{color:var(--muted);margin:9px 0 0;font-size:15px}}
.toolbar{{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0 16px;padding:6px;background:#e8e8e3;border-radius:14px;width:max-content}}
button{{border:0;background:transparent;color:#6f706b;padding:8px 14px;border-radius:10px;
font:inherit;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s,color .15s}}
button:hover{{background:var(--panel)}} button.active{{background:var(--panel);color:var(--text);box-shadow:0 1px 3px #24252212}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.card,.panel{{background:var(--panel);border:0;border-radius:18px;padding:22px}}
.card.wide{{grid-column:1/-1;padding:18px 22px;background:var(--soft)}}
.label{{color:var(--muted);font-size:13px}}
.value{{font-size:30px;font-weight:700;margin-top:5px;letter-spacing:-0.04em}}
.value.good,.value.warn{{color:var(--text)}}
.grid{{display:grid;grid-template-columns:1.15fr .85fr;gap:12px;margin-top:12px}}
h2{{font-size:17px;font-weight:700;margin:0 0 18px;letter-spacing:-0.025em}}
.bar-row{{display:grid;grid-template-columns:145px 1fr 62px;gap:12px;align-items:center;margin:13px 0;font-size:13px}}
.track{{height:8px;background:var(--soft);border-radius:999px;overflow:hidden}}
.fill{{height:100%;border-radius:999px;background:var(--accent)}}
.spark{{display:flex;gap:4px;align-items:end;height:82px;padding-top:12px}}
.spark span{{flex:1;min-width:5px;background:var(--mid);border-radius:5px 5px 2px 2px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{padding:13px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}}
th:first-child,td:first-child{{text-align:left}}
th{{color:var(--muted);font-weight:500;position:sticky;top:0;background:var(--panel)}}
tbody tr:hover{{background:#f7f7f4}} .table-wrap{{overflow:auto;max-height:460px}}
.badge{{padding:4px 8px;border-radius:7px;background:var(--soft);color:#5f605b;font-weight:500}}
.risk{{color:var(--text);font-weight:750}} .ok{{color:var(--muted);font-weight:600}}
.detail{{margin-top:5px;font-weight:700;font-size:15px;color:var(--text)}}
@media(max-width:850px){{.cards{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}}}
@media(max-width:560px){{main{{width:min(100% - 24px,1100px);margin-top:32px}}.cards{{grid-template-columns:1fr}}
.toolbar{{width:100%;overflow:auto;flex-wrap:nowrap}}.bar-row{{grid-template-columns:112px 1fr 52px}}}}
</style>
</head>
<body><main>
<header><div class="eyebrow">ETL 장애 시뮬레이션</div>
<h1>실행 현황</h1><p class="sub">동시성 설정에 따른 처리 시간과 장애 복구 결과를 비교합니다.</p></header>
<div class="toolbar" id="filters"></div>
<section class="cards" id="cards"></section>
<section class="grid">
  <article class="panel"><h2>실행 시간 비교</h2><div id="bars"></div></article>
  <article class="panel"><h2>적응형 동시성 변화</h2><div id="adaptive"></div></article>
</section>
<section class="panel" style="margin-top:10px"><h2>실행 상세</h2>
<div class="table-wrap"><table><thead><tr><th>실행</th><th>추출</th><th>재시도</th><th>최종 실패</th>
<th>검증 실패</th><th>p95</th><th>시간</th></tr></thead><tbody id="rows"></tbody></table></div></section>
</main>
<script>
const allData={data};
let selected="all";
const modes={{"fixed-3":"고정 3","fixed-10":"고정 10","fixed-30":"고정 30","adaptive":"적응형"}};
const scenarios=[...new Map(allData.map(x=>[x.scenario,x.scenario_label])).entries()];
function filtered(){{return selected==="all"?allData:allData.filter(x=>x.scenario===selected)}}
function fmt(x,n=2){{return Number(x).toFixed(n)}}
function renderFilters(){{
 const target=document.querySelector("#filters");
 target.innerHTML=[["all","전체"],...scenarios].map(([id,label])=>
 `<button class="${{selected===id?"active":""}}" data-id="${{id}}">${{label}}</button>`).join("");
 target.querySelectorAll("button").forEach(b=>b.onclick=()=>{{selected=b.dataset.id;render()}});
}}
function renderCards(data){{
 const totalRetries=data.reduce((a,x)=>a+x.retries,0);
 const failed=data.reduce((a,x)=>a+x.extract_failed,0);
 const fastest=[...data].sort((a,b)=>a.total_seconds-b.total_seconds)[0];
 const adaptive=data.filter(x=>x.mode==="adaptive");
 const avgP95=adaptive.reduce((a,x)=>a+x.p95_latency_ms,0)/Math.max(adaptive.length,1);
 document.querySelector("#cards").innerHTML=`
 <article class="card"><div class="label">실험 실행 수</div><div class="value">${{data.length}}</div></article>
 <article class="card"><div class="label">총 재시도</div><div class="value warn">${{totalRetries}}</div></article>
 <article class="card"><div class="label">최종 격리</div><div class="value ${{failed?"warn":"good"}}">${{failed}}</div></article>
 <article class="card"><div class="label">적응형 평균 p95</div><div class="value">${{fmt(avgP95,0)}}ms</div></article>
 <article class="card wide"><div class="label">가장 빠른 실행</div>
 <div class="detail">${{fastest.scenario_label}} · ${{modes[fastest.mode]}} · ${{fmt(fastest.total_seconds)}}초</div></article>`;
}}
function renderBars(data){{
 const max=Math.max(...data.map(x=>x.total_seconds),.001);
 document.querySelector("#bars").innerHTML=data.map(x=>`<div class="bar-row">
 <span>${{x.scenario_label}} · ${{modes[x.mode]}}</span><div class="track"><div class="fill" style="width:${{x.total_seconds/max*100}}%"></div></div>
 <strong>${{fmt(x.total_seconds)}}s</strong></div>`).join("");
}}
function renderAdaptive(data){{
 const runs=data.filter(x=>x.mode==="adaptive");
 document.querySelector("#adaptive").innerHTML=runs.map(x=>{{
  const max=Math.max(...x.concurrency_history,1);
  return `<div style="margin-bottom:16px"><div class="label">${{x.scenario_label}} · ${{x.concurrency_history.join(" → ")}}</div>
  <div class="spark">${{x.concurrency_history.map(v=>`<span title="${{v}}" style="height:${{Math.max(v/max*72,8)}}px"></span>`).join("")}}</div></div>`;
 }}).join("")||"<div class='label'>적응형 실행이 없습니다.</div>";
}}
function renderRows(data){{
 document.querySelector("#rows").innerHTML=data.map(x=>`<tr><td><span class="badge">${{x.scenario_label}} · ${{modes[x.mode]}}</span></td>
 <td>${{x.extracted}}/${{x.requested}}</td><td>${{x.retries}}</td>
 <td class="${{x.extract_failed?"risk":"ok"}}">${{x.extract_failed}}</td>
 <td>${{x.transform_invalid}}</td><td>${{fmt(x.p95_latency_ms,0)}}ms</td><td>${{fmt(x.total_seconds)}}s</td></tr>`).join("");
}}
function render(){{renderFilters();const data=filtered();renderCards(data);renderBars(data);renderAdaptive(data);renderRows(data)}}
render();
</script></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
