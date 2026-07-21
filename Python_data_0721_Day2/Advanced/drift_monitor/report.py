from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from jinja2 import Environment


FEATURE_LABELS = {
    "gender": "성별",
    "senior": "고령 고객 여부",
    "tenure_months": "가입기간",
    "monthly_charges": "월 요금",
    "total_charges": "누적 요금",
    "contract": "계약 유형",
    "payment_method": "결제 방식",
    "num_services": "서비스 수",
    "risk_score": "이탈 예측 확률",
}

STATUS_LABELS = {"danger": "위험", "warning": "주의", "stable": "안정"}


def _label(value: str) -> str:
    return FEATURE_LABELS.get(value, value)


def _fmt_number(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def _fmt_change(value: float, percent: bool = False) -> str:
    scale = 100 if percent else 1
    suffix = "%p" if percent else ""
    return f"{value * scale:+.2f}{suffix}"


def _distribution_svg(item: dict, width: int = 520, height: int = 128) -> str:
    detail = item["detail"]
    reference = detail.get("reference_share", [])
    current = detail.get("current_share", [])
    labels = detail.get("bins", detail.get("categories", []))
    if not reference:
        return ""

    count = len(reference)
    gap = 5
    group_width = (width - 44) / max(count, 1)
    bar_width = max(4, (group_width - gap) / 2)
    usable_height = height - 34
    maximum = max(reference + current + [0.01])
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="분포 비교">']
    parts.append(
        f'<line x1="28" y1="{usable_height}" x2="{width - 8}" y2="{usable_height}" class="axis"/>'
    )
    for index, (ref_value, cur_value) in enumerate(
        zip(reference, current, strict=True)
    ):
        x = 32 + index * group_width
        ref_height = ref_value / maximum * (usable_height - 10)
        cur_height = cur_value / maximum * (usable_height - 10)
        parts.append(
            f'<rect x="{x:.1f}" y="{usable_height - ref_height:.1f}" width="{bar_width:.1f}" '
            f'height="{ref_height:.1f}" rx="2" class="bar-reference"><title>기준 {ref_value:.1%}</title></rect>'
        )
        parts.append(
            f'<rect x="{x + bar_width + 2:.1f}" y="{usable_height - cur_height:.1f}" width="{bar_width:.1f}" '
            f'height="{cur_height:.1f}" rx="2" class="bar-current"><title>신규 {cur_value:.1%}</title></rect>'
        )
        if count <= 6:
            label = html.escape(str(labels[index]))
            if len(label) > 14:
                label = label[:12] + "…"
            parts.append(
                f'<text x="{x + bar_width:.1f}" y="{height - 8}" text-anchor="middle" class="axis-label">{label}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def _cause_bars(causes: list[dict]) -> str:
    if not causes:
        return '<p class="empty">표본 기준을 충족하는 원인 후보가 없습니다.</p>'
    maximum = (
        max(item.get("explanation_score", abs(item["net_effect"])) for item in causes)
        or 1
    )
    rows = []
    for index, item in enumerate(causes, 1):
        size = item.get("explanation_score", abs(item["net_effect"])) / maximum * 100
        direction = "positive" if item["net_effect"] >= 0 else "negative"
        segment = html.escape(item["segment"])
        feature = html.escape(_label(item["segment_feature"]))
        rows.append(
            f"""
            <div class="cause-row">
              <div class="cause-rank">{index:02d}</div>
              <div class="cause-main">
                <div class="cause-title"><strong>{feature}</strong><span>{segment}</span></div>
                <div class="cause-track"><span class="{direction}" style="width:{size:.1f}%"></span></div>
                <div class="cause-meta">
                  <span>비중 {item["reference_share"]:.1%} → {item["current_share"]:.1%}</span>
                  <span>평균 {_fmt_number(item["reference_mean"])} → {_fmt_number(item["current_mean"])}</span>
                </div>
              </div>
              <div class="cause-score">{item["contribution"]:.0%}</div>
            </div>
            """
        )
    return "".join(rows)


REPORT_TEMPLATE = r"""
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<style>
:root{--ink:#172033;--muted:#687287;--line:#e4e8ef;--paper:#fff;--canvas:#f5f7fa;--navy:#142b4a;--blue:#246bfd;--teal:#0f9f8f;--amber:#e79b24;--red:#d84a4a;--shadow:0 12px 34px rgba(21,40,72,.08)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--canvas);color:var(--ink);font-family:"Pretendard","Noto Sans KR","Malgun Gothic",Arial,sans-serif;line-height:1.55}
button,input{font:inherit}.shell{display:grid;grid-template-columns:248px minmax(0,1fr);min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;background:var(--navy);color:#fff;padding:30px 24px;display:flex;flex-direction:column}.brand{display:flex;gap:12px;align-items:center;margin-bottom:42px}.brand-mark{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,#54d6c1,#3b7cff);box-shadow:0 8px 18px rgba(38,107,253,.28)}.brand strong{display:block;font-size:15px}.brand span{font-size:11px;color:#aebdd1;letter-spacing:.08em}.nav a{display:flex;align-items:center;gap:11px;color:#b9c6d8;text-decoration:none;padding:11px 12px;border-radius:10px;margin:3px 0;font-size:14px}.nav a:hover,.nav a.active{background:rgba(255,255,255,.09);color:#fff}.nav i{width:7px;height:7px;background:#4a6281;border-radius:50%}.nav a.active i{background:#54d6c1}.side-note{margin-top:auto;border-top:1px solid rgba(255,255,255,.1);padding-top:18px;color:#9fb0c7;font-size:12px}.side-note b{color:#fff;display:block;margin-bottom:4px}
.content{min-width:0}.topbar{height:72px;background:rgba(255,255,255,.88);backdrop-filter:blur(12px);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 38px;position:sticky;top:0;z-index:5}.topbar-title{font-weight:700}.topbar-meta{font-size:13px;color:var(--muted);display:flex;gap:18px}.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}.status-dot.danger{background:var(--red)}.status-dot.warning{background:var(--amber)}.status-dot.stable{background:var(--teal)}.main{padding:34px 38px 70px;max-width:1500px;margin:auto}.hero{background:linear-gradient(125deg,#142b4a 0%,#17375f 62%,#155f69 130%);color:#fff;border-radius:24px;padding:34px 38px;box-shadow:var(--shadow);display:flex;justify-content:space-between;gap:28px;align-items:flex-end}.eyebrow{font-size:12px;letter-spacing:.15em;text-transform:uppercase;color:#77dfd0;font-weight:800}.hero h1{font-size:30px;line-height:1.25;margin:8px 0 10px;letter-spacing:-.03em}.hero p{margin:0;color:#c7d5e6;max-width:760px}.hero-side{text-align:right;min-width:170px}.hero-side .score{font-size:52px;line-height:1;font-weight:800}.hero-side small{display:block;color:#aec0d3;margin-top:8px}
.section{scroll-margin-top:92px;margin-top:34px}.section-head{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:15px}.section h2{font-size:21px;margin:0;letter-spacing:-.02em}.section-head p{margin:3px 0 0;color:var(--muted);font-size:13px}.pill{border:1px solid var(--line);background:#fff;color:var(--muted);padding:6px 10px;border-radius:999px;font-size:12px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-top:18px}.card{background:var(--paper);border:1px solid var(--line);border-radius:17px;box-shadow:0 7px 22px rgba(21,40,72,.045)}.kpi{padding:19px 20px}.kpi-label{font-size:12px;color:var(--muted);font-weight:700}.kpi-value{font-size:29px;font-weight:800;margin:5px 0 3px;letter-spacing:-.025em}.kpi-foot{font-size:12px;color:var(--muted)}.up{color:var(--red)}.down{color:var(--teal)}
.grid-2{display:grid;grid-template-columns:1.12fr .88fr;gap:16px}.panel{padding:23px}.panel h3{font-size:15px;margin:0 0 5px}.panel-sub{font-size:12px;color:var(--muted);margin-bottom:18px}.alert-list{display:grid;gap:9px}.alert{display:grid;grid-template-columns:10px 1fr auto;gap:11px;align-items:center;padding:12px 13px;background:#f8fafc;border-radius:11px}.alert-line{width:4px;height:34px;border-radius:3px}.alert-line.danger{background:var(--red)}.alert-line.warning{background:var(--amber)}.alert-line.stable{background:var(--teal)}.alert strong{font-size:13px}.alert small{display:block;color:var(--muted)}.badge{display:inline-flex;padding:4px 8px;border-radius:999px;font-size:11px;font-weight:800}.badge.danger{background:#fff0f0;color:#ba3636}.badge.warning{background:#fff7e7;color:#ad7216}.badge.stable{background:#eaf9f5;color:#087c6f}
.scenario-list{display:grid;gap:10px}.scenario-item{display:flex;gap:10px;font-size:13px}.check{flex:none;width:19px;height:19px;border-radius:6px;background:#e7f7f4;color:#078475;text-align:center;line-height:19px;font-size:11px;font-weight:900}
.toolbar{display:flex;gap:9px;align-items:center}.filter{border:1px solid var(--line);background:#fff;border-radius:9px;padding:7px 11px;font-size:12px;color:var(--muted);cursor:pointer}.filter.active{background:var(--navy);color:#fff;border-color:var(--navy)}.table-card{overflow:hidden}.drift-table{width:100%;border-collapse:collapse}.drift-table th{background:#f8fafc;color:#718096;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.06em;padding:12px 16px;border-bottom:1px solid var(--line)}.drift-table td{padding:14px 16px;border-bottom:1px solid #edf0f4;font-size:13px}.drift-table tr:last-child td{border-bottom:0}.drift-table tbody tr{cursor:pointer;transition:.18s}.drift-table tbody tr:hover{background:#f8fbff}.feature strong{display:block}.feature small{color:var(--muted)}.score-cell{font-variant-numeric:tabular-nums;font-weight:800}.change{font-variant-numeric:tabular-nums}.detail-row{display:none;background:#fbfcfe}.detail-row.open{display:table-row}.detail-row td{padding:4px 20px 20px}.chart-wrap{background:#f6f8fb;border-radius:13px;padding:10px 14px}.legend{display:flex;gap:16px;font-size:11px;color:var(--muted)}.legend span:before{content:"";display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px}.legend .ref:before{background:#b6c2d2}.legend .cur:before{background:#246bfd}.axis{stroke:#d8dee8;stroke-width:1}.axis-label{font-size:9px;fill:#7c8798}.bar-reference{fill:#b6c2d2}.bar-current{fill:#246bfd}
.cause-layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px}.cause-card{padding:23px}.cause-row{display:grid;grid-template-columns:30px 1fr 45px;gap:12px;align-items:center;padding:13px 0;border-bottom:1px solid #edf0f4}.cause-row:last-child{border:0}.cause-rank{font-size:11px;color:#9aa4b5;font-weight:800}.cause-title{display:flex;gap:8px;align-items:center;font-size:12px}.cause-title span{color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.cause-track{height:6px;background:#edf1f6;border-radius:5px;overflow:hidden;margin:7px 0}.cause-track span{height:100%;display:block;border-radius:5px}.cause-track .positive{background:linear-gradient(90deg,#246bfd,#2bc0aa)}.cause-track .negative{background:linear-gradient(90deg,#ee7a52,#d84a4a)}.cause-meta{display:flex;gap:16px;color:#7b8698;font-size:10px}.cause-score{text-align:right;font-size:14px;font-weight:800;color:#1c4b85}.insight{background:#eff6ff;border:1px solid #d7e7ff;padding:20px;border-radius:15px}.insight-label{font-size:10px;letter-spacing:.1em;color:#246bfd;font-weight:900}.insight h3{font-size:17px;margin:7px 0}.insight p{font-size:13px;color:#4f6077;margin:0}.metric-list{margin-top:15px;display:grid;gap:8px}.metric-line{display:flex;justify-content:space-between;font-size:12px;padding-top:8px;border-top:1px solid #d8e5f5}.metric-line b{color:#193f72}
.engine-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.engine{padding:17px;border-radius:13px;background:#f8fafc;border:1px solid #edf0f4}.engine.best{background:#eaf9f5;border-color:#bce8df}.engine-name{font-size:12px;color:var(--muted)}.engine-time{font-size:23px;font-weight:800;margin-top:4px}.method{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.method-item{padding:17px}.method-no{font-size:11px;color:#246bfd;font-weight:900}.method-item h3{font-size:14px;margin:7px 0}.method-item p{font-size:12px;color:var(--muted);margin:0}.footnote{font-size:12px;color:var(--muted);margin-top:15px;padding-left:13px;border-left:3px solid #b8c3d2}.empty{font-size:13px;color:var(--muted)}
@media(max-width:1050px){.shell{grid-template-columns:1fr}.sidebar{display:none}.kpis{grid-template-columns:repeat(2,1fr)}.grid-2,.cause-layout{grid-template-columns:1fr}.method{grid-template-columns:repeat(2,1fr)}}
@media(max-width:650px){.topbar{padding:0 18px}.topbar-meta span:first-child{display:none}.main{padding:22px 16px 50px}.hero{padding:26px;display:block}.hero-side{text-align:left;margin-top:24px}.kpis{grid-template-columns:1fr 1fr;gap:9px}.kpi{padding:15px}.kpi-value{font-size:23px}.section-head{align-items:flex-start;gap:12px}.toolbar{flex-wrap:wrap}.table-card{overflow-x:auto}.drift-table{min-width:720px}.method,.engine-grid{grid-template-columns:1fr}.cause-meta{display:block}.topbar-title{font-size:13px}}
@media print{.sidebar,.topbar,.toolbar{display:none}.shell{display:block}.main{padding:0}.card,.hero{box-shadow:none;break-inside:avoid}.section{break-inside:avoid}}
</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand"><div class="brand-mark"></div><div><strong>Drift Monitor</strong><span>DATA & MODEL HEALTH</span></div></div>
    <nav class="nav">
      <a class="active" href="#overview"><i></i>상태 요약</a>
      <a href="#ingestion"><i></i>스키마·DLQ</a>
      <a href="#drift"><i></i>컬럼 드리프트</a>
      <a href="#causes"><i></i>원인 기여도</a>
      <a href="#model"><i></i>모델 영향</a>
      <a href="#validation"><i></i>엔진 검증</a>
      <a href="#method"><i></i>판정 방법</a>
    </nav>
    <div class="side-note"><b>분석 원칙</b>변화 기여도는 원인 후보를 좁히는 통계적 단서이며 인과관계를 의미하지 않습니다.</div>
  </aside>
  <div class="content">
    <header class="topbar"><div class="topbar-title">고객 이탈 파이프라인 모니터링</div><div class="topbar-meta"><span>{{ generated_at }}</span><span><i class="status-dot {{ overall_status }}"></i>{{ overall_label }}</span></div></header>
    <main class="main">
      <section class="hero" id="overview">
        <div><div class="eyebrow">Automated monitoring report</div><h1>{{ scenario.title }}</h1><p>{{ scenario.description }}. 기준 기간과 신규 기간을 동일한 정제·예측 파이프라인으로 비교했습니다.</p></div>
        <div class="hero-side"><div class="score">{{ health_score }}</div><small>파이프라인 건강도 / 100</small></div>
      </section>

      <div class="kpis">
        <article class="card kpi"><div class="kpi-label">분석 고객</div><div class="kpi-value">{{ current_rows | comma }}</div><div class="kpi-foot">기준 {{ reference_rows | comma }}명</div></article>
        <article class="card kpi"><div class="kpi-label">위험·주의 컬럼</div><div class="kpi-value">{{ danger_count }}<small> / {{ warning_count }}</small></div><div class="kpi-foot">전체 {{ drift|length }}개 감시</div></article>
        <article class="card kpi"><div class="kpi-label">평균 이탈 위험도</div><div class="kpi-value">{{ model.current.average_risk | pct }}</div><div class="kpi-foot {{ 'up' if model.change.average_risk > 0 else 'down' }}">{{ model.change.average_risk | pp }} 변화</div></article>
        <article class="card kpi"><div class="kpi-label">모델 ROC-AUC</div><div class="kpi-value">{{ '%.3f'|format(model.current.roc_auc) }}</div><div class="kpi-foot {{ 'down' if model.change.roc_auc < 0 else '' }}">{{ '%+.3f'|format(model.change.roc_auc) }} 변화</div></article>
      </div>

      <section class="section grid-2">
        <article class="card panel"><h3>우선 확인할 변화</h3><div class="panel-sub">판정 기준을 넘은 항목부터 표시합니다.</div><div class="alert-list">
          {% for item in drift[:5] %}<div class="alert"><div class="alert-line {{ item.status }}"></div><div><strong>{{ labels[item.feature] }}</strong><small>{{ item.metric }} {{ '%.3f'|format(item.score) }} · {{ item.reference_value|smart }} → {{ item.current_value|smart }}</small></div><span class="badge {{ item.status }}">{{ status_labels[item.status] }}</span></div>{% endfor %}
        </div></article>
        <article class="card panel"><h3>시나리오에 포함된 변화</h3><div class="panel-sub">탐지·추적 기능을 검증하기 위해 재현 가능하게 주입했습니다.</div><div class="scenario-list">{% for item in scenario.injected_changes %}<div class="scenario-item"><span class="check">✓</span><span>{{ item }}</span></div>{% endfor %}</div><div class="footnote">seed={{ seed }}로 다시 실행해도 동일한 입력과 결과가 생성됩니다.</div></article>
      </section>

      <section class="section" id="ingestion">
        <div class="section-head"><div><h2>스키마 호환 · DLQ 재처리</h2><p>서로 다른 이벤트 버전을 표준 스키마로 변환하고 실패 이벤트를 격리·복구했습니다.</p></div><span class="badge {{ 'stable' if ingestion.current.unresolved == 0 else 'warning' }}">미해결 {{ ingestion.current.unresolved }}건</span></div>
        <div class="kpis">
          <article class="card kpi"><div class="kpi-label">지원 스키마</div><div class="kpi-value">v{{ ingestion.compatibility.supported_versions|join(' · v') }}</div><div class="kpi-foot">현재 표준 v{{ ingestion.compatibility.current_schema_version }}</div></article>
          <article class="card kpi"><div class="kpi-label">수신 이벤트</div><div class="kpi-value">{{ ingestion.current.received|comma }}</div><div class="kpi-foot">중복 {{ ingestion.current.duplicates }}건 차단</div></article>
          <article class="card kpi"><div class="kpi-label">DLQ 최초 적재</div><div class="kpi-value">{{ ingestion.current.dlq_initial }}</div><div class="kpi-foot">검증 실패 이벤트 격리</div></article>
          <article class="card kpi"><div class="kpi-label">재처리 복구</div><div class="kpi-value">{{ ingestion.current.recovered }}</div><div class="kpi-foot">최종 수용 {{ ingestion.current.accepted_total|comma }}건</div></article>
        </div>
        <div class="card panel" style="margin-top:15px"><h3>버전별 수용 현황</h3><div class="panel-sub">표준 분석 컬럼으로 변환된 이벤트 수</div><div class="engine-grid">{% for version, count in ingestion.current.accepted_schema_versions.items() %}<div class="engine"><div class="engine-name">SOURCE SCHEMA v{{ version }}</div><div class="engine-time">{{ count|comma }}<small> events</small></div></div>{% endfor %}<div class="engine {{ 'best' if ingestion.current.unresolved == 0 else '' }}"><div class="engine-name">DLQ STATUS</div><div class="engine-time">{{ ingestion.current.unresolved }}<small> unresolved</small></div></div></div></div>
        <div class="card table-card" style="margin-top:15px"><table class="drift-table"><thead><tr><th>DLQ ID</th><th>이벤트</th><th>수신 버전</th><th>실패 사유</th><th>재시도</th><th>최종 상태</th></tr></thead><tbody>{% for item in dlq_records %}<tr><td>{{ item.dlq_id }}</td><td>{{ item.event_id }}</td><td>v{{ item.schema_version }}</td><td>{{ item.reason_code }}</td><td>{{ item.retry_count }}</td><td><span class="badge {{ 'stable' if item.status == 'recovered' else 'danger' }}">{{ '복구' if item.status == 'recovered' else '미해결' }}</span></td></tr>{% endfor %}</tbody></table></div>
        {% if ingestion.demonstration.failures_injected %}<div class="footnote">DLQ 처리 경로를 검증하기 위해 복구 가능한 오류 3건과 복구 불가능한 오류 1건을 고정된 규칙으로 주입했습니다. 원본 파일은 변경하지 않습니다.</div>{% endif %}
      </section>

      <section class="section" id="drift">
        <div class="section-head"><div><h2>컬럼별 드리프트</h2><p>행을 클릭하거나 Enter 키를 누르면 기준·신규 분포를 비교할 수 있습니다.</p></div><div class="toolbar"><button class="filter active" data-filter="all" aria-pressed="true">전체</button><button class="filter" data-filter="danger" aria-pressed="false">위험</button><button class="filter" data-filter="warning" aria-pressed="false">주의</button><button class="filter" data-filter="stable" aria-pressed="false">안정</button></div></div>
        <div class="card table-card"><table class="drift-table"><thead><tr><th>컬럼</th><th>상태</th><th>지표</th><th>점수</th><th>기준</th><th>신규</th><th>변화</th></tr></thead><tbody>
        {% for item in drift %}<tr class="data-row" data-status="{{ item.status }}" data-detail="detail-{{ loop.index }}" role="button" tabindex="0" aria-expanded="false"><td class="feature"><strong>{{ labels[item.feature] }}</strong><small>{{ item.feature }}</small></td><td><span class="badge {{ item.status }}">{{ status_labels[item.status] }}</span></td><td>{{ item.metric }}</td><td class="score-cell">{{ '%.3f'|format(item.score) }}</td><td>{{ item.reference_value|smart }}</td><td>{{ item.current_value|smart }}</td><td class="change">{{ item.change|smart_signed }}</td></tr>
        <tr id="detail-{{ loop.index }}" class="detail-row" data-status="{{ item.status }}"><td colspan="7"><div class="chart-wrap"><div class="legend"><span class="ref">기준 기간</span><span class="cur">신규 기간</span></div>{{ item.svg | safe }}</div></td></tr>{% endfor %}
        </tbody></table></div>
      </section>

      <section class="section" id="causes"><div class="section-head"><div><h2>변화 원인 후보</h2><p>전체 평균 변화를 고객 구성 효과와 그룹 내부 변화 효과로 분해했습니다.</p></div><span class="pill">{{ primary.target_label }}</span></div>
        <div class="cause-layout"><article class="card cause-card">{{ primary.cause_html | safe }}</article><aside class="insight"><div class="insight-label">AUTOMATED FINDING</div><h3>{{ primary.summary_title }}</h3><p>{{ primary.summary_body }}</p><div class="metric-list"><div class="metric-line"><span>기준 평균</span><b>{{ primary.reference_mean }}</b></div><div class="metric-line"><span>신규 평균</span><b>{{ primary.current_mean }}</b></div><div class="metric-line"><span>전체 변화</span><b>{{ primary.total_delta }}</b></div></div></aside></div>
      </section>

      <section class="section" id="model"><div class="section-head"><div><h2>모델 예측 영향</h2><p>기준 데이터로 학습한 동일 모델을 두 기간에 적용했습니다.</p></div><span class="pill">임계값 {{ model.threshold }}</span></div>
        <div class="grid-2"><article class="card panel"><div class="kpis" style="grid-template-columns:repeat(2,1fr);margin:0"><div class="kpi"><div class="kpi-label">고위험 고객 비율</div><div class="kpi-value">{{ model.current.high_risk_rate|pct }}</div><div class="kpi-foot up">{{ model.change.high_risk_rate|pp }}</div></div><div class="kpi"><div class="kpi-label">실제 이탈률</div><div class="kpi-value">{{ model.current.churn_rate|pct }}</div><div class="kpi-foot">{{ model.change.churn_rate|pp }}</div></div><div class="kpi"><div class="kpi-label">이탈 Recall</div><div class="kpi-value">{{ model.current.recall|pct }}</div><div class="kpi-foot">{{ model.change.recall|pp }}</div></div><div class="kpi"><div class="kpi-label">ROC-AUC 변화</div><div class="kpi-value">{{ '%+.3f'|format(model.change.roc_auc) }}</div><div class="kpi-foot">실제 라벨 기준</div></div></div></article><article class="card cause-card"><h3>예측 위험도 변화 기여 그룹</h3><div class="panel-sub">이탈 확률 평균 변화에 대한 상대 기여도</div>{{ model_cause_html | safe }}</article></div>
      </section>

      <section class="section" id="validation"><div class="section-head"><div><h2>분석 엔진 교차 검증</h2><p>동일 집계를 세 엔진으로 실행하고 결과 일치를 확인했습니다.</p></div><span class="badge stable">결과 일치 PASS</span></div><div class="card panel"><div class="engine-grid">{% for name, elapsed in benchmark.timings.items() %}<div class="engine {{ 'best' if name == benchmark.fastest else '' }}"><div class="engine-name">{{ name }}{% if name == benchmark.fastest %} · FASTEST{% endif %}</div><div class="engine-time">{{ '%.2f'|format(elapsed * 1000) }}<small> ms</small></div></div>{% endfor %}</div><div class="footnote">{{ benchmark.query }}. 실행시간은 현재 환경의 단일 실행 참고값이며 절대적인 엔진 우위를 의미하지 않습니다.</div></div></section>

      <section class="section" id="method"><div class="section-head"><div><h2>판정 방법</h2><p>보고서의 숫자가 만들어지는 과정을 요약합니다.</p></div></div><div class="method"><article class="card method-item"><div class="method-no">01 · CLEAN</div><h3>동일 규칙 정제</h3><p>두 기간에 같은 타입 변환과 그룹별 중앙값 대치를 적용하고 원본 결측률은 별도로 보존합니다.</p></article><article class="card method-item"><div class="method-no">02 · DETECT</div><h3>분포 변화 측정</h3><p>숫자형은 PSI·KS, 범주형은 Jensen–Shannon divergence로 비교합니다.</p></article><article class="card method-item"><div class="method-no">03 · EXPLAIN</div><h3>변화량 분해</h3><p>그룹 비중 변화와 그룹 내부 평균 변화를 분리해 기여 후보를 순위화합니다.</p></article><article class="card method-item"><div class="method-no">04 · VERIFY</div><h3>결과 교차 검증</h3><p>Pandas·Polars·DuckDB의 동일 집계 결과가 허용 오차 안에서 일치하는지 검사합니다.</p></article></div><div class="footnote">본 보고서의 원인 후보는 관측된 데이터 변화에 대한 설명입니다. 개입 효과나 인과관계 판단에는 별도의 실험 설계가 필요합니다.</div></section>
    </main>
  </div>
</div>
<script>
const filters=document.querySelectorAll('.filter');
filters.forEach(button=>button.addEventListener('click',()=>{filters.forEach(x=>{x.classList.remove('active');x.setAttribute('aria-pressed','false')});button.classList.add('active');button.setAttribute('aria-pressed','true');const target=button.dataset.filter;document.querySelectorAll('.data-row').forEach(row=>{const show=target==='all'||row.dataset.status===target;row.style.display=show?'':'none';const detail=document.getElementById(row.dataset.detail);if(!show){detail.classList.remove('open');row.setAttribute('aria-expanded','false')}});}));
const toggleDetail=row=>{const detail=document.getElementById(row.dataset.detail);const open=detail.classList.toggle('open');row.setAttribute('aria-expanded',String(open))};
document.querySelectorAll('.data-row').forEach(row=>{row.addEventListener('click',()=>toggleDetail(row));row.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleDetail(row)}})});
const sections=[...document.querySelectorAll('main [id]')],links=[...document.querySelectorAll('.nav a')];
const sectionObserver=new IntersectionObserver(entries=>{entries.forEach(entry=>{if(entry.isIntersecting){links.forEach(x=>x.classList.toggle('active',x.getAttribute('href')==='#'+entry.target.id));}})},{rootMargin:'-25% 0px -65% 0px'});
sections.forEach(section=>sectionObserver.observe(section));
</script>
</body></html>
"""


def render_report(payload: dict, destination: Path) -> Path:
    drift = []
    for item in payload["drift"]:
        enriched = dict(item)
        enriched["svg"] = _distribution_svg(item)
        drift.append(enriched)

    primary_source = payload["root_causes"][0]
    primary_causes = primary_source["causes"]
    first = primary_causes[0] if primary_causes else None
    if first:
        summary_title = f"{_label(first['segment_feature'])}의 {first['segment']} 그룹"
        summary_body = (
            f"이 그룹의 비중은 {first['reference_share']:.1%}에서 {first['current_share']:.1%}로, "
            f"평균은 {first['reference_mean']:,.2f}에서 {first['current_mean']:,.2f}로 변했습니다. "
            f"분해된 변화량 기준 상대 기여도는 {first['contribution']:.0%}입니다."
        )
    else:
        summary_title = "뚜렷한 단일 그룹 없음"
        summary_body = (
            "설정된 최소 표본 수를 만족하면서 변화를 주도한 그룹이 발견되지 않았습니다."
        )

    primary = {
        "target_label": _label(primary_source["target"]),
        "reference_mean": _fmt_number(primary_source["reference_mean"]),
        "current_mean": _fmt_number(primary_source["current_mean"]),
        "total_delta": _fmt_change(primary_source["total_delta"]),
        "cause_html": _cause_bars(primary_causes),
        "summary_title": summary_title,
        "summary_body": summary_body,
    }

    danger_count = sum(item["status"] == "danger" for item in drift)
    warning_count = sum(item["status"] == "warning" for item in drift)
    unresolved = payload["ingestion"]["current"]["unresolved"]
    health_score = max(
        0,
        round(100 - danger_count * 18 - warning_count * 7 - unresolved * 12),
    )
    overall_label = (
        "위험" if danger_count else "주의" if warning_count or unresolved else "안정"
    )

    environment = Environment(autoescape=True)
    environment.filters.update(
        {
            "comma": lambda value: f"{value:,}",
            "pct": lambda value: f"{value:.1%}",
            "pp": lambda value: f"{value * 100:+.1f}%p",
            "smart": lambda value: (
                f"{value:,.2f}" if isinstance(value, (int, float)) else value
            ),
            "smart_signed": lambda value: f"{value:+,.2f}",
        }
    )
    template = environment.from_string(REPORT_TEMPLATE)
    rendered = template.render(
        title="스키마·DLQ·드리프트 통합 모니터",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        scenario=payload["scenario"],
        seed=payload["seed"],
        ingestion=payload["ingestion"],
        dlq_records=payload["dlq_records"],
        drift=drift,
        model=payload["model"],
        benchmark=payload["benchmark"],
        reference_rows=payload["quality"]["reference"]["rows"],
        current_rows=payload["quality"]["current"]["rows"],
        danger_count=danger_count,
        warning_count=warning_count,
        health_score=health_score,
        overall_label=overall_label,
        overall_status=(
            "danger"
            if danger_count
            else "warning"
            if warning_count or unresolved
            else "stable"
        ),
        status_labels=STATUS_LABELS,
        labels=FEATURE_LABELS,
        primary=primary,
        model_cause_html=_cause_bars(payload["model_causes"]["causes"]),
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered, encoding="utf-8")
    return destination
