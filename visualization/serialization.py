"""Integrity-checked JSON persistence and standalone HTML rendering."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from visualization.models import VisualizationBundle


class VisualizationSerializationError(ValueError):
    pass


def _primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _primitive(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_primitive(item) for item in value]
    return value


def bundle_to_dict(bundle: VisualizationBundle) -> dict[str, Any]:
    if not isinstance(bundle, VisualizationBundle):
        raise TypeError("bundle must be a VisualizationBundle")
    return _primitive(bundle)


def _canonical(raw: dict[str, Any]) -> str:
    return json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint_bundle(bundle: VisualizationBundle) -> str:
    data = bundle_to_dict(bundle)
    data.pop("bundle_fingerprint", None)
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def dumps_bundle(bundle: VisualizationBundle, *, indent: int = 2) -> str:
    data = bundle_to_dict(bundle)
    if fingerprint_bundle(bundle) != bundle.bundle_fingerprint:
        raise VisualizationSerializationError("Visualization bundle fingerprint does not match its content")
    return json.dumps(data, ensure_ascii=False, indent=indent, allow_nan=False)


def _strict(raw: Any, cls: type, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise VisualizationSerializationError(f"{path} must be a JSON object")
    allowed = {item.name for item in fields(cls)}
    missing, unknown = allowed - set(raw), set(raw) - allowed
    if missing:
        raise VisualizationSerializationError(f"{path} missing field(s): {', '.join(sorted(missing))}")
    if unknown:
        raise VisualizationSerializationError(f"{path} has unknown field(s): {', '.join(sorted(unknown))}")
    return raw


def bundle_from_dict(raw: Any) -> VisualizationBundle:
    raw = _strict(raw, VisualizationBundle, "visualization_bundle")
    if not isinstance(raw["warnings"], list) or any(not isinstance(item, str) for item in raw["warnings"]):
        raise VisualizationSerializationError("warnings must be an array of strings")
    try:
        bundle = VisualizationBundle(
            schema_version=raw["schema_version"], bundle_id=raw["bundle_id"],
            created_at=raw["created_at"], artifact_id=raw["artifact_id"],
            artifact_fingerprint=raw["artifact_fingerprint"], project_id=raw["project_id"],
            project_title=raw["project_title"], revision_id=raw["revision_id"],
            revision_version=raw["revision_version"], paradigm=raw["paradigm"],
            backend_name=raw["backend_name"], experiment_id=raw["experiment_id"],
            experiment_fingerprint=raw["experiment_fingerprint"], data=raw["data"],
            warnings=tuple(raw["warnings"]), bundle_fingerprint=raw["bundle_fingerprint"],
        )
    except (TypeError, ValueError) as error:
        raise VisualizationSerializationError(f"Visualization bundle is invalid: {error}") from error
    if fingerprint_bundle(bundle) != bundle.bundle_fingerprint:
        raise VisualizationSerializationError("Visualization bundle fingerprint does not match its stored content")
    return bundle


def loads_bundle(content: str) -> VisualizationBundle:
    try:
        return bundle_from_dict(json.loads(content))
    except json.JSONDecodeError as error:
        raise VisualizationSerializationError(f"Invalid visualization bundle JSON: {error}") from error


def save_bundle(bundle: VisualizationBundle, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(dumps_bundle(bundle), encoding="utf-8")
    os.replace(temporary, destination)
    return destination


def load_bundle(path: str | Path) -> VisualizationBundle:
    source = Path(path)
    try:
        return loads_bundle(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read visualization bundle at {source}: {error}") from error


def _safe_json_script(data: dict[str, Any]) -> str:
    # Prevent data from terminating the script element or becoming HTML markup.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render_html(bundle: VisualizationBundle) -> str:
    """Render a self-contained dashboard. No CDN, network request or Python server is used."""
    if fingerprint_bundle(bundle) != bundle.bundle_fingerprint:
        raise VisualizationSerializationError("Visualization bundle fingerprint does not match its content")
    payload = _safe_json_script(bundle_to_dict(bundle))
    return _HTML.replace("__DASHBOARD_DATA__", payload)


def save_html(bundle: VisualizationBundle, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = render_html(bundle)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, destination)
    return destination


_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Offline simulation results dashboard generated by the AI-Assisted Simulation System.">
<title>Simulation dashboard</title>
<style>
:root{color-scheme:light;--ink:#17212b;--muted:#5d6b78;--line:#dce3e9;--panel:#fff;--bg:#f4f7fa;--accent:#2563eb;--soft:#eaf1ff;--good:#18794e;--warn:#9a5b00;--bad:#b42318}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}.wrap{max-width:1240px;margin:auto;padding:28px 22px 56px}header{margin-bottom:22px}h1{font-size:clamp(25px,4vw,36px);line-height:1.12;margin:0 0 8px}.subtitle{color:var(--muted);margin:0}.meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.chip{background:var(--soft);color:#244b91;padding:5px 10px;border-radius:999px;font-size:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:20px 0}.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:17px;box-shadow:0 1px 2px #17212b08}.kpi .value{font-size:26px;font-weight:700;margin-top:4px}.muted{color:var(--muted);font-size:13px}.panel{margin:16px 0}.panel h2{font-size:19px;margin:0 0 5px}.panel h3{font-size:15px;margin:16px 0 8px}.toolbar{display:flex;flex-wrap:wrap;align-items:end;gap:12px;margin:14px 0}.field{display:grid;gap:5px;font-size:13px;color:var(--muted)}select{min-width:220px;padding:9px 11px;border:1px solid var(--line);border-radius:8px;background:white;color:var(--ink);font:inherit}.chart{width:100%;min-height:220px;overflow:visible}.chart svg{display:block;width:100%;height:auto;min-height:220px}.chart text{font-size:11px;fill:var(--muted)}.legend{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:12px}.legend span{display:inline-flex;align-items:center;gap:6px}.swatch{width:10px;height:10px;border-radius:50%;display:inline-block}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:8px 9px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}td.num{text-align:right;font-variant-numeric:tabular-nums}.scroll{overflow:auto}button{border:1px solid var(--line);border-radius:8px;padding:8px 12px;background:white;color:var(--ink);cursor:pointer}button:hover{border-color:var(--accent)}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}.tabs button.active{background:var(--accent);border-color:var(--accent);color:white}.tab-content[hidden]{display:none}.note{border-left:3px solid var(--warn);padding:8px 12px;background:#fff8e8;color:#674300;border-radius:4px;margin:8px 0;font-size:13px}.ok{color:var(--good)}.error{color:var(--bad)}.empty{padding:18px;color:var(--muted);background:var(--bg);border-radius:8px}.footer{margin-top:26px;color:var(--muted);font-size:12px;overflow-wrap:anywhere}.range-row{display:grid;grid-template-columns:minmax(120px,1fr) 3fr;gap:12px;align-items:center;margin:10px 0;font-size:13px}.range{height:13px;background:#e8edf3;border-radius:99px;position:relative}.range .band{position:absolute;height:100%;background:#b8cdfb;border-radius:99px}.range .mean{position:absolute;height:19px;width:3px;top:-3px;background:#1d4ed8;border-radius:3px}
@media(max-width:640px){.wrap{padding:18px 12px 38px}.range-row{grid-template-columns:1fr}.card,.panel{padding:13px}}
@media print{body{background:white}.wrap{max-width:none;padding:0}.panel,.card{box-shadow:none;break-inside:avoid}.tabs,.toolbar button{display:none}select{border:0;padding:0}}
</style></head>
<body><main class="wrap"><header><h1 id="title">Simulation dashboard</h1><p class="subtitle" id="subtitle"></p><div class="meta" id="meta"></div></header>
<section class="grid" id="kpis"></section>
<nav class="tabs" aria-label="Dashboard sections"><button class="active" data-tab="overview">Overview</button><button data-tab="trace">Execution trace</button><button data-tab="experiments">Experiments</button><button data-tab="uncertainty">Uncertainty</button></nav>
<section class="tab-content" id="tab-overview"><article class="panel"><h2>Metric trends across executions</h2><p class="muted">Each point is a completed M9 run. Values are descriptive; they are not forecasts.</p><div class="toolbar"><label class="field">Numeric metric<select id="metric-select"></select></label></div><div class="chart" id="metric-chart"></div></article><article class="panel"><h2>Run outcomes</h2><div class="scroll" id="run-table"></div></article></section>
<section class="tab-content" id="tab-trace" hidden><article class="panel"><h2>Paradigm-specific trace</h2><p class="muted">Select an execution to inspect its captured trace.</p><div class="toolbar"><label class="field">Execution run<select id="run-select"></select></label></div><div id="trace-content"></div></article></section>
<section class="tab-content" id="tab-experiments" hidden><article class="panel"><h2>M10 parameter comparison</h2><div id="m10-content"></div></article></section>
<section class="tab-content" id="tab-uncertainty" hidden><article class="panel"><h2>M11 uncertainty and sensitivity</h2><div id="m11-content"></div></article></section>
<footer class="footer" id="footer"></footer></main>
<script id="dashboard-data" type="application/json">__DASHBOARD_DATA__</script>
<script>
(()=>{'use strict';
const B=JSON.parse(document.getElementById('dashboard-data').textContent),D=B.data;
const $=id=>document.getElementById(id),fmt=(v,d=3)=>typeof v==='number'?(Number.isInteger(v)?String(v):Number(v).toFixed(d)):String(v??'—');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const colors=['#2563eb','#0f766e','#b45309','#7c3aed','#be123c','#0891b2','#4d7c0f','#9333ea'];
function node(tag,attrs={},parent){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));if(parent)parent.appendChild(n);return n}
function svgBase(w=900,h=280){const s=node('svg',{viewBox:`0 0 ${w} ${h}`,role:'img','aria-label':'Data chart'});return s}
function renderLine(container,series,title){container.replaceChildren();if(!series.length){container.innerHTML='<div class="empty">No numeric observations are available for this chart.</div>';return}
const points=series.flatMap(x=>x.points.map(p=>p.value)).filter(Number.isFinite);if(!points.length){container.innerHTML='<div class="empty">No finite numeric observations are available.</div>';return}
const svg=svgBase(),w=900,h=280,L=58,R=20,T=18,BT=42,lo=Math.min(...points),hi=Math.max(...points),span=hi-lo||1;
for(let i=0;i<=4;i++){const y=T+(h-T-BT)*i/4,val=hi-(hi-lo)*i/4;node('line',{x1:L,y1:y,x2:w-R,y2:y,stroke:'#e5eaf0'},svg);const t=node('text',{x:L-9,y:y+4,'text-anchor':'end'},svg);t.textContent=fmt(val,2)}
const maxX=Math.max(1,...series.flatMap(x=>x.points.map(p=>p.run_index))),x=v=>L+(w-L-R)*(v-1)/Math.max(1,maxX-1),y=v=>T+(h-T-BT)*(hi-v)/span;
series.forEach((s,i)=>{const sorted=s.points.slice().sort((a,b)=>a.run_index-b.run_index);if(sorted.length>1){node('polyline',{points:sorted.map(p=>`${x(p.run_index)},${y(p.value)}`).join(' '),fill:'none',stroke:colors[i%colors.length],'stroke-width':2.5},svg)}sorted.forEach(p=>node('circle',{cx:x(p.run_index),cy:y(p.value),r:4,fill:colors[i%colors.length]},svg))});
for(let i=0;i<=4;i++){const t=node('text',{x:L+(w-L-R)*i/4,y:h-14,'text-anchor':'middle'},svg);t.textContent=fmt(1+(maxX-1)*i/4,0)}
container.appendChild(svg);const legend=document.createElement('div');legend.className='legend';series.forEach((s,i)=>{const item=document.createElement('span'),dot=document.createElement('i');dot.className='swatch';dot.style.background=colors[i%colors.length];item.append(dot,document.createTextNode(s.name));legend.appendChild(item)});container.appendChild(legend)}
function table(headers,rows){if(!rows.length)return '<div class="empty">No records available.</div>';return '<div class="scroll"><table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map((c,i)=>'<td class="'+(i>0?'num':'')+'">'+esc(c)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>'}
function renderMetric(){const name=$('metric-select').value,s=D.metric_series.filter(x=>x.name===name);renderLine($('metric-chart'),s.map(x=>({name:x.unit?`${x.name} (${x.unit})`:x.name,points:x.points})));}
function renderRuns(){const rows=D.runs.map(r=>[r.run_index,r.status,r.seed??'—',r.parameter_set,Object.keys(r.metrics||{}).length]);$('run-table').innerHTML=table(['Run','Status','Seed','Variant','Metrics'],rows)}
function drawDES(view){const wrap=$('trace-content');wrap.replaceChildren();const ev=view.events||[];if(!ev.length){wrap.innerHTML='<div class="empty">This execution has no DES event records.</div>';return}
const types=[...new Set(ev.map(e=>e.event_type))],maxT=Math.max(1,...ev.map(e=>Number(e.time)||0)),svg=svgBase(1000,Math.max(220,types.length*54+65)),L=150,R=25,T=22,BT=38,w=1000,h=Math.max(220,types.length*54+65);
types.forEach((type,i)=>{const yy=T+i*54+18;node('line',{x1:L,y1:yy,x2:w-R,y2:yy,stroke:'#e8edf2'},svg);const lab=node('text',{x:L-12,y:yy+4,'text-anchor':'end'},svg);lab.textContent=type});
ev.forEach(e=>{const i=types.indexOf(e.event_type),xx=L+(w-L-R)*(Number(e.time)||0)/maxT,yy=T+i*54+18;node('circle',{cx:xx,cy:yy,r:5,fill:colors[i%colors.length],opacity:.85},svg)});
for(let i=0;i<=5;i++){const xx=L+(w-L-R)*i/5;node('line',{x1:xx,y1:T-5,x2:xx,y2:h-BT,stroke:'#f0f2f5'},svg);const lab=node('text',{x:xx,y:h-12,'text-anchor':'middle'},svg);lab.textContent=fmt(maxT*i/5,2)}wrap.appendChild(svg);const sub=document.createElement('p');sub.className='muted';sub.textContent=`${ev.length} captured events · horizontal position represents simulation time · rows represent event types`;wrap.appendChild(sub);
if(view.resources?.length){const h3=document.createElement('h3');h3.textContent='Resource utilization';wrap.appendChild(h3);wrap.insertAdjacentHTML('beforeend',table(['Resource','Completed','Avg. wait','Avg. service','Utilization'],view.resources.map(r=>[r.resource_name,r.completed_services,fmt(r.average_waiting_time),fmt(r.average_service_time),`${fmt(r.utilization,1)}%`])))}
if(view.entities?.length){const h3=document.createElement('h3');h3.textContent='Entity outcomes';wrap.appendChild(h3);wrap.insertAdjacentHTML('beforeend',table(['Entity','Arrival','Completion','Waiting','Service','Time in system'],view.entities.map(r=>[r.entity_id,fmt(r.arrival_time),fmt(r.completion_time),fmt(r.waiting_time),fmt(r.service_time),fmt(r.time_in_system)])))}
}
function drawABM(view){const wrap=$('trace-content');wrap.replaceChildren();const steps=view.steps||[];if(!steps.length){wrap.innerHTML='<div class="empty">This execution has no ABM history snapshots.</div>';return}
const states=[...new Set(steps.flatMap(s=>Object.keys(s.state_counts||{})))];const series=states.map(state=>({name:state,points:steps.map(s=>({run_index:Number(s.step)+1,value:Number((s.state_counts||{})[state]||0)}))}));const h3=document.createElement('h3');h3.textContent='Population by agent state over simulation steps';wrap.appendChild(h3);const chart=document.createElement('div');chart.className='chart';wrap.appendChild(chart);renderLine(chart,series);
const typeRows=steps.length?Object.keys(steps[steps.length-1].type_counts||{}).map(k=>[k,steps[steps.length-1].type_counts[k]]):[];const h4=document.createElement('h3');h4.textContent='Final population by agent type';wrap.appendChild(h4);wrap.insertAdjacentHTML('beforeend',table(['Agent type','Count'],typeRows));
const rules=steps.map(s=>Object.values(s.rule_counts||{}).reduce((a,b)=>a+b,0));const total=rules.reduce((a,b)=>a+b,0);const p=document.createElement('p');p.className='muted';p.textContent=`${steps.length} snapshots · ${total} recorded rule evaluations across the captured trace`;wrap.appendChild(p);
const attrNames=[...new Set(steps.flatMap(s=>Object.keys(s.attribute_means||{})))];if(attrNames.length){const box=document.createElement('div');box.className='toolbar';const label=document.createElement('label');label.className='field';label.textContent='Numeric agent attribute';const select=document.createElement('select');attrNames.forEach(a=>{const o=document.createElement('option');o.value=a;o.textContent=a;select.appendChild(o)});label.appendChild(select);box.appendChild(label);wrap.appendChild(box);const attrChart=document.createElement('div');attrChart.className='chart';wrap.appendChild(attrChart);const draw=()=>renderLine(attrChart,[{name:select.value,points:steps.filter(s=>Number.isFinite(s.attribute_means?.[select.value])).map(s=>({run_index:Number(s.step)+1,value:s.attribute_means[select.value]}))}]);select.addEventListener('change',draw);draw()}}
function renderTrace(){const ix=Number($('run-select').value),view=D.trace_views.find(v=>v.run_index===ix);if(!view){$('trace-content').innerHTML='<div class="empty">No visual trace was retained for this run.</div>';return}view.kind==='des'?drawDES(view):drawABM(view)}
function renderM10(){const el=$('m10-content'),m=D.m10;if(!m){el.innerHTML='<div class="empty">No matching M10 comparative analysis was attached to this dashboard.</div>';return}const rows=(m.variants||[]).map(v=>[(v.parameter_set||'—'),v.successful_runs??'—',v.failed_runs??'—',Object.keys(v.parameters||{}).map(k=>`${k}=${v.parameters[k]}`).join(', ')||'baseline']);el.innerHTML=table(['Variant','Successful','Failed','Parameters'],rows);(m.warnings||[]).forEach(w=>{const n=document.createElement('div');n.className='note';n.textContent=w;el.appendChild(n)});(m.metrics||[]).forEach(metric=>{const h=document.createElement('h3');h.textContent=metric.metric_name;el.appendChild(h);const chart=document.createElement('div');chart.className='chart';el.appendChild(chart);renderLine(chart,[{name:metric.metric_name,points:metric.values.map((v,i)=>({run_index:i+1,value:v}))}])})}
function renderM11(){const el=$('m11-content'),m=D.m11;if(!m){el.innerHTML='<div class="empty">No matching M11 uncertainty analysis was attached to this dashboard.</div>';return}const d=m.distributions||[];d.forEach(item=>{const title=document.createElement('h3');title.textContent=item.metric_name+(item.unit?` (${item.unit})`:'');el.appendChild(title);const row=document.createElement('div');row.className='range-row';const label=document.createElement('div');label.textContent=`P05 ${fmt(item.percentile_05)} · Mean ${fmt(item.mean)} · P95 ${fmt(item.percentile_95)}`;const range=document.createElement('div');range.className='range';const span=item.maximum-item.minimum||1;const band=document.createElement('i');band.className='band';band.style.left=`${100*(item.percentile_05-item.minimum)/span}%`;band.style.width=`${100*(item.percentile_95-item.percentile_05)/span}%`;const mean=document.createElement('i');mean.className='mean';mean.style.left=`${100*(item.mean-item.minimum)/span}%`;range.append(band,mean);row.append(label,range);el.appendChild(row)});
const scores=m.sensitivity||[];if(scores.length){const h=document.createElement('h3');h.textContent='Exploratory sensitivity ranking (Spearman ρ)';el.appendChild(h);el.insertAdjacentHTML('beforeend',table(['Parameter','Metric','ρ','Rank'],scores.map(s=>[s.parameter_path,s.metric_name,s.spearman_rho==null?'not estimable':fmt(s.spearman_rho,3),s.rank??'—'])))}
const r=m.robustness||{};if((r.criteria||[]).length){const h=document.createElement('h3');h.textContent='User-defined robustness criteria';el.appendChild(h);el.insertAdjacentHTML('beforeend',table(['Metric','Criterion','Pass fraction'],r.criteria.map(c=>[c.metric_name,`${c.operator} ${c.threshold}${c.upper_threshold==null?'':` to ${c.upper_threshold}`}`,c.observed_fraction==null?'not evaluated':`${(100*c.observed_fraction).toFixed(1)}%`])))}
(m.warnings||[]).forEach(w=>{const n=document.createElement('div');n.className='note';n.textContent=w;el.appendChild(n)})}
$('title').textContent=B.project_title;$('subtitle').textContent=`${B.paradigm} · ${B.backend_name} · revision ${B.revision_id} (v${B.revision_version})`;
[B.artifact_id,B.experiment_id,`Created ${B.created_at}`].forEach(x=>{const s=document.createElement('span');s.className='chip';s.textContent=x;$('meta').appendChild(s)});
const completed=D.runs.filter(r=>r.status==='completed').length,failed=D.runs.length-completed;
[["Executions",D.runs.length],["Completed",completed],["Failed",failed],["Trace views",D.trace_views.length]].forEach(([label,value])=>{const c=document.createElement('article');c.className='card kpi';const l=document.createElement('div');l.className='muted';l.textContent=label;const v=document.createElement('div');v.className='value';v.textContent=value;c.append(l,v);$('kpis').appendChild(c)});
const names=D.metric_series.map(x=>x.name);if(names.length){names.forEach(n=>{const o=document.createElement('option');o.value=n;o.textContent=n;$('metric-select').appendChild(o)});$('metric-select').addEventListener('change',renderMetric);renderMetric()}else $('metric-chart').innerHTML='<div class="empty">No numeric run metrics were found.</div>';
const traces=D.trace_views;$('run-select').replaceChildren();traces.forEach(v=>{const o=document.createElement('option');o.value=v.run_index;o.textContent=`Run ${v.run_index} · ${v.kind.toUpperCase()}`;$('run-select').appendChild(o)});$('run-select').addEventListener('change',renderTrace);renderTrace();renderRuns();renderM10();renderM11();
$('footer').textContent=`M12 dashboard · Bundle ${B.bundle_id} · SHA-256 ${B.bundle_fingerprint} · Original M8 artifact fingerprint ${B.artifact_fingerprint}`;
B.warnings.forEach(w=>{const n=document.createElement('div');n.className='note';n.textContent=w;$('footer').prepend(n)});
document.querySelectorAll('[data-tab]').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b===btn));document.querySelectorAll('.tab-content').forEach(s=>s.hidden=s.id!==`tab-${btn.dataset.tab}`)}));
})();
</script></body></html>'''
