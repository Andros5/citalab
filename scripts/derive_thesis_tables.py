"""Cifras y tablas derivadas de la campaña final para los capítulos 8 y 9 de la memoria.

Lee resultados, trazas, evaluaciones del jurado y revisión humana sin modificarlos. Escribe
las tablas LaTeX en `memoria/generated/campana-*.tex` y todas las cifras en
`output/evaluation/<campaña>/derived/resumen-derivado.json`.

    PYTHONPATH=src python scripts/derive_thesis_tables.py
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import datetime
from math import comb
from pathlib import Path

from citalab.evaluation.analysis import _dependency_groups, load, summarize, wilson
from citalab_judge.agreement import compare, human, jury_scores, judge_scores, ppi_by

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = "final-independent-v1"
CONFIGS = [(p, a) for p in ("groq", "google") for a in ("M5", "S1", "H")]
ARCHS = ("M5", "S1", "H")
MODEL = {"groq": "Groq", "google": "Gemini"}
ASSISTANT = ["administrative", "continuity", "clarity", "redundancy", "profile_fit", "material_fidelity"]
SHORT = {"administrative": "Admin.", "continuity": "Contin.", "clarity": "Claridad",
         "redundancy": "Repet.", "profile_fit": "Perfil", "material_fidelity": "Fidelidad"}
OPERATIONS = [("book", "Reserva"), ("query", "Consulta"), ("reschedule", "Reprogramación"),
              ("cancel", "Cancelación"), ("reminder", "Recordatorio")]
BLOCKS = [("primary", "Primera ejecución"), ("repeat-2", "Repetición"), ("counterfactual", "Contraste de preferencias"),
          ("persona", "Contraste de persona"), ("supplement", "Casos nuevos")]
PHASES = [("unsupported-success-claim", "Posible anuncio de un efecto (detección léxica)"),
          ("missing-anchor", "Falta una hora o un dato del plan"),
          ("missing-question", "Falta la pregunta del plan"),
          ("unknown-time", "Hora que no procede del plan"),
          ("confirm", "Confirmación rechazada por el programa")]
SEED = 20261029


# ---------------------------------------------------------------- formato
def num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def thousands(value: float) -> str:
    text = f"{round(value):d}"
    return re.sub(r"(\d)(?=(\d{3})+$)", r"\1\\,", text) if len(text) > 4 else text


def pct(part: int, whole: int, digits: int = 1) -> str:
    return num(100 * part / whole, digits) + "\\,\\%"


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def mcnemar_exact(better: int, worse: int) -> float:
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def part_of_day(iso: str) -> str:
    return "morning" if datetime.fromisoformat(iso).hour < 14 else "afternoon"


# ---------------------------------------------------------------- datos
def attempts(folder: Path) -> list[dict]:
    lines = (folder / "results.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def trace(folder: Path, row: dict) -> list[dict]:
    return json.loads((folder / row["traces_file"].replace("\\", "/")).read_text(encoding="utf-8"))


def events(row: dict, kind: str | None = None) -> list[dict]:
    return [e for t in row["turns"] for e in t.get("events", []) if kind is None or e.get("kind") == kind]


# ---------------------------------------------------------------- análisis
def coverage(folder: Path, all_attempts: list[dict]) -> dict:
    roles: dict[str, Counter] = defaultdict(Counter)
    errors = Counter()
    for row in all_attempts:
        for call in trace(folder, row):
            role = "simulator" if call["agent"] == "user-simulator" else "assistant"
            key = f"{role}:{row['provider']}"
            roles[key]["submissions"] += 1
            if call["status"] == "error":
                roles[key]["failed"] += 1
                errors[(role, call.get("error_code") or call.get("error_type"))] += 1
            if call.get("input_tokens") is not None:
                roles[key]["known"] += 1
                roles[key]["input_tokens"] += call["input_tokens"]
                roles[key]["output_tokens"] += call["output_tokens"]
                roles[key]["cached_input_tokens"] += call.get("cached_input_tokens") or 0
            roles[key]["inference_ms"] += call.get("latency_ms") or 0
            if row["status"] != "completed":
                roles[key]["interrupted_submissions"] += 1
                roles[key]["interrupted_tokens"] += (call.get("input_tokens") or 0) + (call.get("output_tokens") or 0)
    return {"attempts": len(all_attempts),
            "completed": sum(r["status"] == "completed" for r in all_attempts),
            "interrupted": [r["cell_id"] for r in all_attempts if r["status"] != "completed"],
            "roles": {k: dict(v) for k, v in sorted(roles.items())},
            "failed_by_type": {f"{r}:{c}": n for (r, c), n in errors.most_common()}}


def jury_usage(folder: Path) -> dict:
    result = {}
    for name in ("claude", "codex"):
        items = [json.loads(line) for line in (folder / f"judge/judgments-{name}-v1.jsonl")
                 .read_text(encoding="utf-8").splitlines() if line.strip()]
        tokens_in = tokens_out = invocations = 0
        cost = 0.0
        for item in items:
            for usage in item.get("usage") or []:
                invocations += 1
                # Claude informa la caché aparte de `input_tokens`. En Codex, `cached_input_tokens`
                # es una parte de `input_tokens` y no se suma de nuevo.
                tokens_in += sum(usage.get(k, 0) or 0 for k in ("input_tokens", "cache_read_input_tokens",
                                                                 "cache_creation_input_tokens"))
                tokens_out += usage.get("output_tokens", 0) or 0
                cost += usage.get("reported_cost_usd", 0) or 0
        seconds = [item["seconds"] for item in items]
        result[name] = {"evaluations": len(items), "invocations": invocations,
                        "valid": sum(i["status"] == "valid" for i in items),
                        "repaired": sum(1 for i in items if i.get("attempts", 1) > 1),
                        "input_tokens": tokens_in, "output_tokens": tokens_out,
                        "reported_cost_usd": round(cost, 2), "median_seconds": st.median(seconds),
                        "total_hours": round(sum(seconds) / 3600, 2)}
    return result


def success_tables(rows: list[dict]) -> dict:
    by = {}
    for key, labels in (("operation", OPERATIONS), ("block", BLOCKS)):
        for code, _ in labels:
            cells = {}
            for provider, arch in CONFIGS:
                group = [r for r in rows if r["provider"] == provider and r["architecture"] == arch and r[key] == code]
                cells[f"{provider}:{arch}"] = [sum(r["success"] for r in group), len(group)]
            total = [sum(v[0] for v in cells.values()), sum(v[1] for v in cells.values())]
            by[f"{key}:{code}"] = {"configs": cells, "total": total}
    return by


def contrasts(rows: list[dict], campaign: str) -> dict:
    # Los grupos de dependencia salen del corpus congelado de la campaña, no del de desarrollo.
    summary = summarize(rows, _dependency_groups(campaign))
    result = {}
    for provider in ("groq", "google"):
        outcome = {(r["unit_id"], r["architecture"]): r["success"] for r in rows if r["provider"] == provider}
        units = sorted({u for u, _ in outcome})
        for a, b in (("M5", "S1"), ("M5", "H"), ("S1", "H")):
            better = sum(1 for u in units if outcome[(u, a)] and not outcome[(u, b)])
            worse = sum(1 for u in units if not outcome[(u, a)] and outcome[(u, b)])
            boot = summary["contrasts"][provider][f"{a}-{b}"]
            grouped = summary["grouped_contrasts"][provider][f"{a}-{b}"]
            result[f"{provider}:{a}-{b}"] = {"a_only": better, "b_only": worse,
                                             "mcnemar_p": mcnemar_exact(better, worse),
                                             "bootstrap": boot, "grouped": grouped}
    return result


def resources(rows: list[dict]) -> dict:
    result = {}
    for provider, arch in CONFIGS:
        group = [r for r in rows if r["provider"] == provider and r["architecture"] == arch]
        tokens = [r["input_tokens"] + r["output_tokens"] for r in group]
        calls = [r["assistant_calls"] for r in group]
        inference = [r["llm_latency_s"] for r in group]
        wall = [r["active_seconds"] for r in group]
        successes = sum(r["success"] for r in group)
        result[f"{provider}:{arch}"] = {
            "calls_mean": st.fmean(calls), "calls_median": st.median(calls), "calls_p90": quantile(calls, .9),
            "tokens_mean": st.fmean(tokens), "tokens_median": st.median(tokens), "tokens_p90": quantile(tokens, .9),
            "tokens_total": sum(tokens), "tokens_per_success": sum(tokens) / successes,
            "tokens_in_failures": sum(t for t, r in zip(tokens, group) if not r["success"]),
            "inference_median": st.median(inference), "inference_p90": quantile(inference, .9),
            "wall_median": st.median(wall), "turns_median": st.median(r["user_turns"] for r in group),
            "turns_p90": quantile([r["user_turns"] for r in group], .9)}
    return result


def first_offer(row: dict) -> tuple[str, list[str], bool]:
    """Primera oferta del asistente: tipo, franjas en orden y si explica el orden por el perfil."""
    for turn in row["turns"]:
        for event in turn.get("events", []):
            if event.get("kind") == "proposal" and event["proposal"].get("slot_id"):
                slot = row["initial_state"]["Slot"].get(event["proposal"]["slot_id"])
                if slot:
                    return "proposal", [part_of_day(slot["start"])], False
        text = turn.get("assistant") or ""
        hours = re.findall(r"(?:a las|at) (\d{1,2}):\d\d", text)
        if len(hours) >= 2 and re.search(r"(^|\s)1\.", text):
            parts = ["morning" if int(h) < 14 else "afternoon" for h in hours]
            explained = bool(re.search(r"preferen|tardes|mañanas", text, re.I))
            return "list", parts, explained
    return "none", [], False


def preferences(rows: list[dict]) -> dict:
    by_cell = {r["cell_id"]: r for r in rows}
    slot_units = [("N-B02", "primary"), ("N-CF-B02", "counterfactual"), ("N-UC-B02", "persona"),
                  ("N-R02", "primary"), ("N-CF-R02", "counterfactual")]
    episodes = []
    for unit, block in slot_units:
        for provider, arch in CONFIGS:
            row = by_cell[f"{provider}:{arch}:{unit}:{block}"]
            want = row["scenario"]["preference_target"]["part_of_day"]
            appointments = row["final_state"]["Appointment"]
            chosen = [part_of_day(appointments[i]["start"]) for i in row["effects"]["created"] + row["effects"]["moved"]]
            kind, offered, explained = first_offer(row)
            pick = None
            if kind == "list" and len(row["turns"]) > 1:
                reply = row["turns"][1]["user"] or ""
                hours = re.findall(r"(?:a las|at) (\d{1,2}:\d\d)", row["turns"][0]["assistant"] or "")
                picked = [h for h in hours if h in reply]
                if len(set(picked)) == 1:
                    pick = "first" if picked[0] == hours[0] else "other"
            episodes.append({"cell": row["cell_id"], "unit": unit, "provider": provider, "architecture": arch,
                             "wanted": want, "retrieved": any(e.get("name") == "get_preferences" for e in events(row, "tool")),
                             "offer": kind, "offer_first_matches": bool(offered) and offered[0] == want,
                             "explained": explained, "pick": pick,
                             "chosen_matches": chosen[:1] == [want], "adherence": row["preference_adherence"]})
    pairs = []
    for base, counter in (("N-B02", "N-CF-B02"), ("N-R02", "N-CF-R02")):
        for provider, arch in CONFIGS:
            first = by_cell[f"{provider}:{arch}:{base}:primary"]
            second = by_cell[f"{provider}:{arch}:{counter}:counterfactual"]
            parts = []
            for row in (first, second):
                appointments = row["final_state"]["Appointment"]
                ids = row["effects"]["created"] + row["effects"]["moved"]
                parts.append(part_of_day(appointments[ids[0]]["start"]) if ids else None)
            pairs.append({"pair": base, "provider": provider, "architecture": arch,
                          "base": parts[0], "counterfactual": parts[1], "changed": parts[0] != parts[1]})
    channels = []
    for provider, arch in CONFIGS:
        found = []
        for unit, block in (("N-M02", "primary"), ("N-CF-M02", "counterfactual")):
            row = by_cell[f"{provider}:{arch}:{unit}:{block}"]
            requests = row["final_state"]["CommunicationRequest"]
            found.append([requests[i]["medium"][0]["coding"][0]["code"] for i in row["effects"]["reminders"] if i in requests])
        channels.append({"provider": provider, "architecture": arch, "base": found[0], "counterfactual": found[1],
                         "changed": found[0] != found[1]})
    detail = []
    for base in ("N-Q02", "N-C02"):
        counter = base.replace("N-", "N-CF-")
        for provider, arch in CONFIGS:
            words = [len((by_cell[f"{provider}:{arch}:{u}:{b}"]["turns"][0]["assistant"] or "").split())
                     for u, b in ((base, "primary"), (counter, "counterfactual"))]
            detail.append({"pair": base, "provider": provider, "architecture": arch, "words_base": words[0],
                           "words_step_by_step": words[1], "longer_20pct": words[1] >= 1.2 * words[0]})
    # Frase del plan que explica el orden por la preferencia: ¿la conserva la redacción?
    kept = Counter()
    for row in rows:
        for turn in row["turns"]:
            for plan in turn.get("plans") or []:
                if re.search(r"ordenado según (tu|su) preferencia|ordered them by your saved preference", " ".join(plan.get("facts") or [])):
                    keep = bool(re.search(r"preferen", turn.get("assistant") or "", re.I))
                    kept[(row["provider"], "kept" if keep else "dropped")] += 1
    profile_units = sorted({r["unit_id"] for r in rows if r["scenario"].get("profile")})
    ranking_units = ["N-B02", "N-CF-B02", "N-UC-B02", "N-R02", "N-CF-R02", "N-M02", "N-CF-M02"]
    retrieval = {}
    for provider, arch in CONFIGS:
        group = [r for r in rows if r["provider"] == provider and r["architecture"] == arch and r["unit_id"] in ranking_units]
        retrieval[f"{provider}:{arch}"] = [sum(any(e.get("name") == "get_preferences" for e in events(r, "tool")) for r in group), len(group)]
    return {"slot_episodes": episodes, "slot_pairs": pairs, "channel_pairs": channels, "detail_pairs": detail,
            "explanation_in_plan": {f"{p}:{k}": n for (p, k), n in sorted(kept.items())},
            "profile_units": profile_units, "retrieval_ranking_channel": retrieval}


def fallbacks(rows: list[dict]) -> dict:
    by_phase = Counter()
    for row in rows:
        for item in row.get("fallbacks", []):
            parts = item.split(":")
            phase = parts[1] if parts[0] != "orchestration-rejected" else "confirm"
            by_phase[(row["architecture"], phase)] += 1
    with_fb = [r for r in rows if r.get("fallbacks")]
    without = [r for r in rows if not r.get("fallbacks")]
    return {"by_phase": {f"{a}:{p}": n for (a, p), n in sorted(by_phase.items())},
            "messages": sum(len(r.get("fallbacks", [])) for r in rows),
            "episodes": len(with_fb), "episodes_success": sum(r["success"] for r in with_fb),
            "without": len(without), "without_success": sum(r["success"] for r in without),
            "failed_with_fallback": sorted(r["cell_id"] for r in with_fb if not r["success"])}


def auc(lower_is_failure: list[float], others: list[float]) -> float:
    wins = sum(1 if f < o else 0.5 if f == o else 0 for f in lower_is_failure for o in others)
    return wins / (len(lower_is_failure) * len(others))


def quality(rows: list[dict], campaign: str, folder: Path) -> dict:
    by_cell = {r["cell_id"]: r for r in rows}
    jury = jury_scores(campaign)
    first = {c: r for (c, p), r in human(campaign).items() if p == 1}
    sample = set(json.loads((folder / "judge/sample-v1.json").read_text(encoding="utf-8"))["cells"])

    def means(scores: dict, cells: list[str]) -> dict:
        out = {}
        for dim in ASSISTANT:
            values = [scores[c][dim] for c in cells if scores[c].get(dim) is not None]
            out[dim] = {"mean": st.fmean(values) if values else None, "n": len(values)}
        return out

    human_flat = {c: r["scores"] for c, r in first.items()}
    human_cfg, jury_cfg, human_arch, jury_arch = {}, {}, {}, {}
    for provider, arch in CONFIGS:
        key = f"{provider}:{arch}"
        human_cfg[key] = means(human_flat, [c for c in human_flat if c.startswith(key + ":")])
        jury_cfg[key] = means(jury, [c for c in jury if c.startswith(key + ":")])
    for arch in ARCHS:
        human_arch[arch] = means(human_flat, [c for c in human_flat if c.split(":")[1] == arch])
        jury_arch[arch] = means(jury, [c for c in jury if c.split(":")[1] == arch])
    ok = [c for c in jury if by_cell[c]["success"]]
    bad = [c for c in jury if not by_cell[c]["success"]]
    oracle = {}
    for dim in ASSISTANT:
        good = [jury[c][dim] for c in ok if jury[c][dim] is not None]
        poor = [jury[c][dim] for c in bad if jury[c][dim] is not None]
        oracle[dim] = {"success_mean": st.fmean(good), "failure_mean": st.fmean(poor), "auc": auc(poor, good)}
    histogram = {}
    for label, cells in (("success", ok), ("failure", bad)):
        counts = Counter(jury[c]["administrative"] for c in cells)
        histogram[label] = {f"{k:.1f}": counts.get(k, 0) for k in (0, .5, 1, 1.5, 2, 2.5, 3)}
    low = [c for c in ok if jury[c]["administrative"] is not None and jury[c]["administrative"] <= 1.5]
    low_in_sample = [c for c in low if c in sample]
    # Diferencia entre jueces por proveedor evaluado (GPT-6.1-Terra menos Claude). El bootstrap
    # remuestrea unidades y empareja cada episodio de Groq con el de Gemini de la misma condición.
    claude, codex = judge_scores(campaign, "claude"), judge_scores(campaign, "codex")
    gap = {}
    for cell in sorted(claude.keys() & codex.keys()):
        pairs = [(codex[cell][d], claude[cell][d]) for d in ASSISTANT
                 if codex[cell].get(d) is not None and claude[cell].get(d) is not None]
        if pairs:
            gap[cell] = st.fmean(a - b for a, b in pairs)
    by_unit = defaultdict(list)
    for cell, value in gap.items():
        provider, arch, unit, block = cell.split(":")
        twin = f"google:{arch}:{unit}:{block}"
        if provider == "groq" and twin in gap:
            by_unit[(unit, block)].append(value - gap[twin])
    units = sorted(by_unit)
    rng = random.Random(SEED)
    boot = []
    for _ in range(5000):
        sample = [rng.choice(units) for _ in units]
        boot.append(st.fmean(v for u in sample for v in by_unit[u]))
    boot.sort()
    groq_gap = st.fmean(v for c, v in gap.items() if c.startswith("groq:"))
    google_gap = st.fmean(v for c, v in gap.items() if c.startswith("google:"))
    judge_gap = {"groq": groq_gap, "google": google_gap, "difference": groq_gap - google_gap,
                 "units": len(units), "ci": [boot[int(.025 * len(boot))], boot[int(.975 * len(boot)) - 1]]}
    concord = {"claude": compare(human_flat_all(first), claude), "codex": compare(human_flat_all(first), codex),
               "jury": compare(human_flat_all(first), jury, integer=False), "judges": compare(claude, codex)}
    return {"human_by_config": human_cfg, "jury_by_config": jury_cfg, "human_by_arch": human_arch,
            "jury_by_arch": jury_arch, "oracle_vs_jury": oracle, "administrative_histogram": histogram,
            "successes_low_admin": sorted(low), "low_admin_in_sample": len(low_in_sample),
            "low_admin_in_sample_human": sorted(first[c]["scores"]["administrative"] for c in low_in_sample),
            "judge_gap_by_provider": judge_gap,
            "concordance": {k: {d: v[d] for d in ASSISTANT} for k, v in concord.items()}}


def human_flat_all(first: dict) -> dict:
    return {c: {**r["scores"], **{f"sim.{k}": v for k, v in (r.get("simulator_scores") or {}).items()}}
            for c, r in first.items()}


def failures(rows: list[dict]) -> list[dict]:
    return [{"cell": r["cell_id"], "end": r["end_reason"], "flags": r["simulator_flags"],
             "failed_checks": [k for k, v in r["checks"].items() if not v["pass"]], "effects": r["effects"]}
            for r in sorted(rows, key=lambda x: x["cell_id"]) if not r["success"]]


# ---------------------------------------------------------------- tablas LaTeX
def write(path: Path, lines: list[str]) -> None:
    header = "% Generado por scripts/derive_thesis_tables.py a partir de la campaña final. No editar a mano.\n"
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def table_operations(data: dict, out: Path) -> None:
    lines = ["\\setlength{\\tabcolsep}{4.5pt}\\begin{tabular}{lrrrrrrr}\\toprule",
             "& \\multicolumn{3}{c}{Groq} & \\multicolumn{3}{c}{Gemini} & \\\\ \\cmidrule(lr){2-4}\\cmidrule(lr){5-7}",
             "Unidad & M5 & S1 & H & M5 & S1 & H & Total \\\\ \\midrule"]
    for key, labels in (("operation", OPERATIONS), ("block", BLOCKS)):
        if key == "block":
            lines.append("\\midrule")
        for code, label in labels:
            entry = data[f"{key}:{code}"]
            cells = [f"{s}/{n}" for s, n in (entry["configs"][f"{p}:{a}"] for p, a in CONFIGS)]
            s, n = entry["total"]
            lines.append(f"{label} & " + " & ".join(cells) + f" & {s}/{n} ({num(100 * s / n, 1)}\\,\\%) \\\\")
    lines.append("\\bottomrule\\end{tabular}")
    write(out / "campana-exito-gestion.tex", lines)


def table_contrasts(data: dict, out: Path) -> None:
    lines = ["\\setlength{\\tabcolsep}{4.5pt}\\begin{tabular}{llrcrrr}\\toprule",
             "Modelo & Contraste & Diferencia & IC95\\,\\% & $p$ Holm & Discord. & McNemar \\\\ \\midrule"]
    for provider in ("groq", "google"):
        for a, b in (("M5", "S1"), ("M5", "H"), ("S1", "H")):
            entry = data[f"{provider}:{a}-{b}"]
            boot = entry["bootstrap"]
            diff = 100 * boot["diff"]
            low, high = 100 * boot["ci_low"], 100 * boot["ci_high"]
            sign = lambda v: ("+" if v > 0.05 else "-" if v < -0.05 else "") + num(abs(v), 1)
            lines.append(f"{MODEL[provider]} & {a} $-$ {b} & ${sign(diff)}$ & ${sign(low)}$ a ${sign(high)}$ & "
                         f"{num(boot['p_holm'], 2)} & {entry['a_only']}/{entry['b_only']} & {num(entry['mcnemar_p'], 2)} \\\\")
    lines.append("\\bottomrule\\end{tabular}")
    write(out / "campana-contrastes.tex", lines)


def table_resources(data: dict, out: Path) -> None:
    lines = ["\\begin{tabular}{llrrrrrrr}\\toprule",
             "& & \\multicolumn{2}{c}{Llamadas} & \\multicolumn{3}{c}{Tokens conocidos} & \\multicolumn{2}{c}{Inferencia (s)} \\\\",
             "\\cmidrule(lr){3-4}\\cmidrule(lr){5-7}\\cmidrule(lr){8-9}",
             "Modelo & Arq. & Mediana & P90 & Mediana & P90 & Por éxito & Mediana & P90 \\\\ \\midrule"]
    for provider, arch in CONFIGS:
        r = data[f"{provider}:{arch}"]
        lines.append(f"{MODEL[provider]} & {arch} & {num(r['calls_median'], 1)} & {num(r['calls_p90'], 1)} & "
                     f"{thousands(r['tokens_median'])} & {thousands(r['tokens_p90'])} & {thousands(r['tokens_per_success'])} & "
                     f"{num(r['inference_median'], 1)} & {num(r['inference_p90'], 1)} \\\\")
    lines.append("\\bottomrule\\end{tabular}")
    write(out / "campana-recursos.tex", lines)


def table_roles(cov: dict, jury: dict, out: Path) -> None:
    lines = ["\\begin{tabular}{lrrrrr}\\toprule",
             "Componente & Envíos & Fallidos & Tokens conocidos & Entrada & Salida \\\\ \\midrule"]
    names = {"assistant:groq": "Asistente con Groq", "assistant:google": "Asistente con Gemini",
             "simulator:groq": "Simulador en episodios Groq", "simulator:google": "Simulador en episodios Gemini"}
    for key in ("assistant:groq", "assistant:google", "simulator:groq", "simulator:google"):
        r = cov["roles"][key]
        lines.append(f"{names[key]} & {r['submissions']} & {r.get('failed', 0)} & {pct(r['known'], r['submissions'])} & "
                     f"{thousands(r['input_tokens'])} & {thousands(r['output_tokens'])} \\\\")
    lines.append("\\midrule")
    for name, label in (("claude", "Juez Claude Sonnet 5.5"), ("codex", "Juez GPT-6.1-Terra")):
        r = jury[name]
        lines.append(f"{label} & {r['invocations']} & 0 & 100\\,\\% & {thousands(r['input_tokens'])} & {thousands(r['output_tokens'])} \\\\")
    lines.append("\\bottomrule\\end{tabular}")
    write(out / "campana-componentes.tex", lines)


def table_preferences(prefs: dict, out: Path) -> None:
    lines = ["\\begin{tabular}{llcccc}\\toprule",
             "Modelo & Arq. & \\shortstack{Consulta\\\\el perfil} & \\shortstack{Primera oferta\\\\conforme} & "
             "\\shortstack{Elección final\\\\conforme} & \\shortstack{Cambia en\\\\el contraste} \\\\ \\midrule"]
    for provider, arch in CONFIGS:
        eps = [e for e in prefs["slot_episodes"] if e["provider"] == provider and e["architecture"] == arch]
        pairs = [p for p in prefs["slot_pairs"] if p["provider"] == provider and p["architecture"] == arch]
        lines.append(f"{MODEL[provider]} & {arch} & {sum(e['retrieved'] for e in eps)}/{len(eps)} & "
                     f"{sum(e['offer_first_matches'] for e in eps)}/{len(eps)} & {sum(e['chosen_matches'] for e in eps)}/{len(eps)} & "
                     f"{sum(p['changed'] for p in pairs)}/{len(pairs)} \\\\")
    lines.append("\\bottomrule\\end{tabular}")
    write(out / "campana-preferencias.tex", lines)


def table_fallbacks(fb: dict, out: Path) -> None:
    lines = ["\\begin{tabular}{lrrrr}\\toprule", "Motivo de la sustitución & M5 & S1 & H & Total \\\\ \\midrule"]
    for code, label in PHASES:
        counts = [fb["by_phase"].get(f"{a}:{code}", 0) for a in ARCHS]
        lines.append(f"{label} & " + " & ".join(str(c) for c in counts) + f" & {sum(counts)} \\\\")
    totals = [sum(n for k, n in fb["by_phase"].items() if k.startswith(a + ":")) for a in ARCHS]
    lines.append("\\midrule Total & " + " & ".join(str(t) for t in totals) + f" & {sum(totals)} \\\\")
    lines.append("\\bottomrule\\end{tabular}")
    write(out / "campana-respaldos.tex", lines)


def table_quality(q: dict, out: Path) -> None:
    lines = ["\\begin{tabular}{lll" + "c" * len(ASSISTANT) + "}\\toprule",
             "Fuente & Modelo & Arq. & " + " & ".join(SHORT[d] for d in ASSISTANT) + " \\\\ \\midrule"]
    for source, data, label in (("human_by_config", q["human_by_config"], "Humana (10)"),
                                ("jury_by_config", q["jury_by_config"], "Jurado (46)")):
        for provider, arch in CONFIGS:
            cells = data[f"{provider}:{arch}"]
            values = [num(cells[d]["mean"], 2) if cells[d]["mean"] is not None else "n/d" for d in ASSISTANT]
            lines.append(f"{label} & {MODEL[provider]} & {arch} & " + " & ".join(values) + " \\\\")
        if source == "human_by_config":
            lines.append("\\midrule")
    lines.append("\\bottomrule\\end{tabular}")
    write(out / "campana-calidad.tex", lines)


def table_oracle(q: dict, out: Path) -> None:
    lines = ["\\begin{tabular}{lccc}\\toprule",
             "Dimensión & Éxitos (260) & Fallos (16) & AUC \\\\ \\midrule"]
    names = {"administrative": "Respuesta administrativa", "continuity": "Continuidad", "clarity": "Claridad",
             "redundancy": "Ausencia de repetición", "profile_fit": "Adecuación al perfil",
             "material_fidelity": "Fidelidad material"}
    for dim in ASSISTANT:
        r = q["oracle_vs_jury"][dim]
        lines.append(f"{names[dim]} & {num(r['success_mean'], 2)} & {num(r['failure_mean'], 2)} & {num(r['auc'], 2)} \\\\")
    lines.append("\\bottomrule\\end{tabular}")
    write(out / "campana-jurado-oraculo.tex", lines)


def figure_histogram(q: dict, out: Path) -> None:
    """Series de la figura: porcentaje de episodios por nota media del jurado en respuesta administrativa."""
    h = q["administrative_histogram"]
    lines = []
    for key, style, label in (("success", "tfm exitos", "Éxitos del oráculo"), ("failure", "tfm fallos", "Fallos del oráculo")):
        total = sum(h[key].values())
        coords = " ".join(f"({k},{100 * v / total:.1f})" for k, v in h[key].items())
        lines += [f"\\addplot[{style}] coordinates {{{coords}}};", f"\\addlegendentry{{{label} ({total})}}"]
    write(out / "campana-histograma.tex", lines)


def figure_cost(rows: list[dict], res: dict, out: Path) -> None:
    """Series de la figura: tokens medios del asistente frente a éxito integral por configuración."""
    lines = []
    for provider in ("groq", "google"):
        points = []
        for arch in ARCHS:
            group = [r for r in rows if r["provider"] == provider and r["architecture"] == arch]
            rate = 100 * sum(r["success"] for r in group) / len(group)
            points.append(f"({res[f'{provider}:{arch}']['tokens_mean']:.0f},{rate:.1f})[{arch}]")
        lines += [f"\\addplot[tfm {provider}] coordinates {{{' '.join(points)}}};", f"\\addlegendentry{{{MODEL[provider]}}}"]
    write(out / "campana-coste.tex", lines)


def ppi_estimates(campaign: str) -> dict:
    # Estimación PPI++ por configuración. La memoria no la utiliza (la muestra no representa la
    # campaña), pero se conserva en el resumen derivado para poder consultarla.
    data = ppi_by(campaign)
    flat = {}
    for provider, arch in CONFIGS:
        for dim in ASSISTANT:
            r = data[f"{provider}:{arch}"][dim]
            low, high = max(0.0, r["ci"][0]), min(3.0, r["ci"][1])
            flat[f"{provider}:{arch}:{dim}"] = {"estimate": r["estimate"], "ci": [low, high], "lambda": r["lambda"],
                                                "degenerate": high - low < 1e-9}
    return flat


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", default=CAMPAIGN)
    args = parser.parse_args(argv)
    folder = ROOT / "output" / "evaluation" / args.campaign
    out = ROOT / "memoria" / "generated"
    out.mkdir(parents=True, exist_ok=True)
    rows = load(args.campaign)
    all_attempts = attempts(folder)
    invalid = [r for r in rows if not r.get("simulator_valid", True)]
    valid_rates = {}
    for provider, arch in CONFIGS:
        group = [r for r in rows if r["provider"] == provider and r["architecture"] == arch and r.get("simulator_valid", True)]
        valid_rates[f"{provider}:{arch}"] = [sum(r["success"] for r in group), len(group)]
    result = {
        "campaign": args.campaign,
        "coverage": coverage(folder, all_attempts),
        "jury": jury_usage(folder),
        "success": {f"{p}:{a}": [sum(r["success"] for r in rows if r["provider"] == p and r["architecture"] == a),
                                 sum(1 for r in rows if r["provider"] == p and r["architecture"] == a)] for p, a in CONFIGS},
        "wilson": {f"{p}:{a}": wilson(*[sum(r["success"] for r in rows if r["provider"] == p and r["architecture"] == a),
                                         sum(1 for r in rows if r["provider"] == p and r["architecture"] == a)]) for p, a in CONFIGS},
        "by_unit": success_tables(rows),
        "contrasts": contrasts(rows, args.campaign),
        "simulator_invalid": sorted(r["cell_id"] for r in invalid),
        "success_without_invalid_simulator": valid_rates,
        "believed_achieved_but_failed": sorted(r["cell_id"] for r in rows if "believed-achieved-but-failed" in r["simulator_flags"]),
        "resources": resources(rows),
        "preferences": preferences(rows),
        "fallbacks": fallbacks(rows),
        "quality": quality(rows, args.campaign, folder),
        "failures": failures(rows),
    }
    table_operations(result["by_unit"], out)
    table_contrasts(result["contrasts"], out)
    table_resources(result["resources"], out)
    table_roles(result["coverage"], result["jury"], out)
    table_preferences(result["preferences"], out)
    table_fallbacks(result["fallbacks"], out)
    table_quality(result["quality"], out)
    table_oracle(result["quality"], out)
    figure_histogram(result["quality"], out)
    figure_cost(rows, result["resources"], out)
    result["ppi"] = ppi_estimates(args.campaign)
    target = folder / "derived"
    target.mkdir(exist_ok=True)
    (target / "resumen-derivado.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str),
                                                  encoding="utf-8")
    print(f"Tablas en {out} y cifras en {target / 'resumen-derivado.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
