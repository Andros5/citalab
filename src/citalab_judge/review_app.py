"""Revisión humana ciega de la muestra fijada, en 127.0.0.1:8766.

- Muestra la misma vista que recibe el jurado y la rúbrica del Apéndice B con NA.
- Orden aleatorio con semilla e identificadores ciegos; sin arquitectura, proveedor ni notas del jurado
  (las notas del jurado no se muestran nunca aquí, para no anclar las revisiones siguientes).
- Segunda pasada: 12 episodios, en otro orden, disponibles 48 h después de su primera revisión.
- Las notas las introduce solo el autor; se guardan append-only en `judge/reviews-v1.jsonl`.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta

# A nivel de módulo: con `from __future__ import annotations`, FastAPI resuelve la anotación
# en los globales; importado dentro de create_app, `request` se tomaba como parámetro de consulta (422).
from starlette.requests import Request

from citalab.evaluation.review import DIMENSIONS, SIMULATOR_DIMENSIONS, _scores
from citalab_judge import sample as sample_module
from citalab_judge.agreement import human, reviews_path
from citalab_judge.episode import build, campaign_rows, scenarios_for
from citalab_judge.judge import ANCHORS, SIMULATOR_BEHAVIOUR

SECOND_PASS_DELAY = timedelta(hours=48)
PORT = 8766
# El portal CitaLab (8765, o Vite en 5173) usa esta API desde Evaluación → Revisión ciega.
# Solo esos orígenes locales; las peticiones JSON exigen preflight, así que otra web no puede guardar notas.
PORTAL_ORIGINS = [f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in (8765, 5173)]


def queue(campaign: str, review_pass: int) -> list[str]:
    manifest = sample_module.load(campaign)
    if manifest is None:
        raise RuntimeError("Primero fija la muestra: python -m citalab_judge sample --campaign " + campaign)
    cells = list(manifest["cells"] if review_pass == 1 else manifest["second_pass"])
    random.Random(sample_module.SEED + 10 + review_pass).shuffle(cells)
    return cells


def state(campaign: str) -> dict:
    rows = {r["cell_id"]: r for r in campaign_rows(campaign)}
    done = human(campaign)
    now = datetime.now(UTC)
    result = {}
    for review_pass in (1, 2):
        cells = queue(campaign, review_pass)
        reviewed = [c for c in cells if (c, review_pass) in done]
        available = [c for c in cells if c in rows and (c, review_pass) not in done]
        if review_pass == 2:
            available = [c for c in available if (c, 1) in done
                         and now - datetime.fromisoformat(done[(c, 1)]["at"]) >= SECOND_PASS_DELAY]
        result[review_pass] = {"total": len(cells), "done": len(reviewed), "available": available,
                               "pending_results": sum(1 for c in cells if c not in rows)}
    return result


def next_item(campaign: str, review_pass: int) -> dict:
    info = state(campaign)
    progress = {p: {k: v for k, v in s.items() if k != "available"} for p, s in info.items()}
    available = info[review_pass]["available"]
    if not available:
        return {"done": True, "progress": progress}
    rows = {r["cell_id"]: r for r in campaign_rows(campaign)}
    view = build(rows[available[0]], scenarios_for(campaign))
    return {"done": False, "pass": review_pass, "view": view, "progress": progress}


def save(campaign: str, data: dict) -> dict:
    review_pass = int(data.get("pass", 1))
    allowed = {build_id: cell for cell, build_id in _blind_ids(campaign, review_pass).items()}
    cell = allowed.get(str(data.get("sample_id")))
    if cell is None:
        raise ValueError("episodio fuera de la muestra o de esta pasada")
    assistant = data.get("scores") or {}
    simulator = data.get("simulator_scores") or {}
    missing = [k for k in DIMENSIONS if k not in assistant] + [k for k in SIMULATOR_DIMENSIONS if k not in simulator]
    if missing:
        raise ValueError("faltan dimensiones: " + ", ".join(missing))
    item = {"cell_id": cell, "sample_id": data["sample_id"], "pass": review_pass,
            "scores": _scores(assistant, DIMENSIONS), "simulator_scores": _scores(simulator, SIMULATOR_DIMENSIONS),
            "evidence": str(data.get("evidence", ""))[:200], "notes": str(data.get("notes", ""))[:2000],
            "reviewer": "autor", "at": datetime.now(UTC).isoformat()}
    with reviews_path(campaign).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    return {"saved": True}


def _blind_ids(campaign: str, review_pass: int) -> dict[str, str]:
    from citalab.evaluation.review import blind_id
    return {cell: blind_id(cell) for cell in queue(campaign, review_pass)}


def rubric() -> dict:
    return {"assistant": {k: {"label": DIMENSIONS[k], "anchors": ANCHORS[k]} for k in DIMENSIONS},
            "simulator": {k: {"label": SIMULATOR_DIMENSIONS[k], "good": SIMULATOR_BEHAVIOUR[k][0],
                              "bad": SIMULATOR_BEHAVIOUR[k][1]} for k in SIMULATOR_DIMENSIONS}}


def create_app(campaign: str):
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="Revisión ciega")
    app.add_middleware(CORSMiddleware, allow_origins=PORTAL_ORIGINS, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"])

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.replace("__RUBRIC__", json.dumps(rubric(), ensure_ascii=False))

    @app.get("/api/status")
    def api_status() -> dict:
        info = state(campaign)
        progress = {p: {k: v for k, v in s.items() if k != "available"} | {"available": len(s["available"])}
                    for p, s in info.items()}
        return {"campaign": campaign, "progress": progress, "rubric": rubric(),
                "second_pass_delay_hours": SECOND_PASS_DELAY.total_seconds() / 3600}

    @app.get("/api/next")
    def api_next(review_pass: int = 1) -> dict:
        return next_item(campaign, review_pass)

    @app.post("/api/save")
    async def api_save(request: Request) -> dict:
        if not request.headers.get("content-type", "").startswith("application/json"):
            raise HTTPException(415, "se espera JSON")
        try:
            return save(campaign, await request.json())
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    return app


def serve(campaign: str, port: int = PORT) -> None:
    import uvicorn
    print(f"Revisión ciega en http://127.0.0.1:{port}  (Ctrl+C para salir)")
    uvicorn.run(create_app(campaign), host="127.0.0.1", port=port, log_level="warning")


PAGE = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Revisión ciega</title>
<style>
body{font:15px/1.45 system-ui,sans-serif;margin:0;background:#f6f6f4;color:#222}
main{max-width:1200px;margin:auto;padding:16px;display:grid;grid-template-columns:1.1fr 1fr;gap:16px}
section{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px}
h1{font-size:18px;margin:12px 16px} h2{font-size:15px;margin:8px 0}
.msg{margin:6px 0;padding:6px 8px;border-radius:6px;white-space:pre-wrap}
.usuario{background:#eef3fb}.asistente{background:#f3f1ea}.n{font-weight:600;margin-right:6px}
.dim{border-top:1px solid #eee;padding:8px 0}.dim small{color:#555;display:block}
.opts label{margin-right:10px;white-space:nowrap} ul{margin:4px 0 8px 18px;padding:0}
button{font-size:15px;padding:8px 16px} .bar{margin:0 16px;color:#444}
textarea,input[type=text]{width:100%;box-sizing:border-box}
@media(max-width:800px){main{grid-template-columns:1fr}}
</style></head><body>
<h1>Revisión ciega <select id="pass"><option value="1">Primera pasada</option>
<option value="2">Segunda pasada</option></select></h1><div class="bar" id="bar"></div>
<main><section id="episode"></section><section><form id="form"></form></section></main>
<script>
const RUBRIC=__RUBRIC__; let current=null;
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function list(items){return '<ul>'+items.map(i=>'<li>'+esc(i)+'</li>').join('')+'</ul>'}
function radios(group,key){return '<div class="opts">'+['0','1','2','3','NA'].map(v=>
 `<label><input type="radio" name="${group}.${key}" value="${v}" required> ${v}</label>`).join('')+'</div>'}
async function load(){
 const p=document.getElementById('pass').value; const r=await (await fetch('/api/next?review_pass='+p)).json();
 const g=r.progress; document.getElementById('bar').textContent=
  `Pasada 1: ${g[1].done}/${g[1].total} (sin resultado aún: ${g[1].pending_results}) · Pasada 2: ${g[2].done}/${g[2].total}`;
 const ep=document.getElementById('episode'), form=document.getElementById('form');
 if(r.done){current=null;ep.innerHTML='<p>No hay episodios disponibles en esta pasada ahora mismo.</p>';form.innerHTML='';return}
 current=r; const v=r.view;
 ep.innerHTML=`<h2>${esc(v.sample_id)}</h2><p>${esc(v.reference_time)} · idioma ${esc(v.conversation_language)}</p>
 <h2>Usuario simulado</h2><p><b>Objetivo:</b> ${esc(v.user.goal)}<br><b>Estilo:</b> ${esc(v.user.style)}</p>
 ${list(v.user.instructions)}<p><small>${esc(v.user.confirm_button)}</small></p>
 <h2>Perfil vigente</h2>${list(v.profile)}
 <h2>Agenda inicial</h2><b>Citas propias</b>${list(v.agenda.own_appointments_before)}
 <b>Huecos libres</b>${list(v.agenda.free_slots_before)}
 <h2>Efectos observados</h2>${list(v.agenda.observed_effects)}
 <h2>Transcripción</h2>`+v.messages.map(m=>`<div class="msg ${m.role}"><span class="n">[${m.n}] ${m.role}</span>${esc(m.text)}</div>`).join('');
 let h='<h2>Asistente</h2>';
 for(const [k,d] of Object.entries(RUBRIC.assistant)) h+=`<div class="dim"><b>${esc(d.label)}</b>
  <small>${d.anchors.map((a,i)=>i+' = '+esc(a)).join('<br>')}</small>${radios('assistant',k)}</div>`;
 h+='<h2>Usuario simulado</h2>';
 for(const [k,d] of Object.entries(RUBRIC.simulator)) h+=`<div class="dim"><b>${esc(d.label)}</b>
  <small>Adecuado: ${esc(d.good)}<br>Incumplimiento: ${esc(d.bad)}</small>${radios('simulator',k)}</div>`;
 h+=`<p><label>Mensajes de evidencia (p. ej. 2, 4)<input type="text" name="evidence"></label></p>
 <p><label>Notas<textarea name="notes" rows="3"></textarea></label></p><button>Guardar y siguiente</button>`;
 form.innerHTML=h; window.scrollTo(0,0);
}
document.getElementById('form').addEventListener('submit',async e=>{
 e.preventDefault(); const f=new FormData(e.target), scores={}, sim={};
 for(const [k,val] of f.entries()){ if(k.startsWith('assistant.')) scores[k.slice(10)]=val;
  if(k.startsWith('simulator.')) sim[k.slice(10)]=val; }
 const body={sample_id:current.view.sample_id,pass:current.pass,scores,simulator_scores:sim,
  evidence:f.get('evidence'),notes:f.get('notes')};
 const res=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!res.ok){alert((await res.json()).detail);return} load();
});
document.getElementById('pass').addEventListener('change',load); load();
</script></body></html>"""
