"""Análisis de una campaña: tasas, diferencias pareadas, bootstrap por familia y coste.

Python puro (sin numpy). Genera `summary.md` y tablas CSV listas para pgfplots
en la memoria. Uso: python -m citalab.evaluation.analysis --campaign final
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

from citalab.config import OUTPUT

ARCHS = ("M5", "S1", "H")
BLOCKS = ("primary", "repeat-2", "counterfactual", "persona", "supplement")


def _dependency_groups(campaign: str | None = None) -> dict[str, list[str]]:
    from citalab.evaluation.fixtures import load_scenarios
    snapshot = OUTPUT / "evaluation" / campaign / "scenarios.json" if campaign else None
    if snapshot and snapshot.exists():
        return load_scenarios(snapshot).get("dependency_groups", {})
    return load_scenarios().get("dependency_groups", {})
CHECKS = ("goal", "confirmation", "third_party", "preservation", "fidelity", "response")


def load(campaign: str) -> list[dict]:
    path = OUTPUT / "evaluation" / campaign / "results.jsonl"
    latest: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["cell_id"]] = row  # el último registro de una celda (reintento) prevalece
    return list(latest.values())


def rate(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def paired_bootstrap(rows: list[dict], a: str, b: str, provider: str, iterations: int = 5000,
                     seed: int = 20261029) -> dict:
    """Diferencia de éxito A−B emparejada por familia; IC95 % por remuestreo de familias."""
    pairs: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["provider"] == provider and row["status"] == "completed" and row["architecture"] in (a, b):
            pairs[row["unit_id"] + ":" + row["block"]][row["architecture"]].append(int(row["success"]))
    units = [u for u, v in pairs.items() if v[a] and v[b]]
    diffs = [statistics.mean(pairs[u][a]) - statistics.mean(pairs[u][b]) for u in units]
    if not diffs:
        return {"n_units": 0}
    rng = random.Random(seed)
    boots = sorted(statistics.mean(rng.choices(diffs, k=len(diffs))) for _ in range(iterations))
    # p-valor bilateral por bootstrap centrado (aproximación).
    observed = statistics.mean(diffs)
    centred = [x - observed for x in boots]
    p_value = sum(abs(x) >= abs(observed) for x in centred) / iterations
    discordant = sum(1 for d in diffs if d != 0)
    return {"n_units": len(diffs), "diff": observed, "ci_low": boots[int(0.025 * iterations)],
            "ci_high": boots[int(0.975 * iterations) - 1], "p_value": p_value, "discordant_units": discordant}


def grouped_sign_flip(rows: list[dict], a: str, b: str, provider: str, groups: dict[str, list[str]],
                      iterations: int = 5000, seed: int = 20261029) -> dict:
    """Sensibilidad conservadora: las familias del mismo grupo cambian de signo juntas.

    Solo se usan las unidades derivadas de las 25 familias (primarias, repeticiones y
    contrastes heredan el grupo de su familia); el suplemento se informa aparte.
    Con G grupos se enumeran las 2^G combinaciones: con G = 5 el p bilateral mínimo es 0,0625.
    """
    group_of = {family: name for name, members in groups.items() for family in members}
    per_group: dict[str, list[float]] = defaultdict(list)
    pairs: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if (row["provider"] == provider and row["status"] == "completed" and row["architecture"] in (a, b)
                and row.get("family_id") in group_of):
            pairs[row["unit_id"] + ":" + row["block"]][row["architecture"]].append(int(row["success"]))
            pairs[row["unit_id"] + ":" + row["block"]]["_group"] = [group_of[row["family_id"]]]
    for unit, values in pairs.items():
        if values[a] and values[b]:
            per_group[values["_group"][0]].append(statistics.mean(values[a]) - statistics.mean(values[b]))
    means = [statistics.mean(v) for v in per_group.values() if v]
    if not means:
        return {"n_groups": 0}
    observed = statistics.mean(means)
    count = 0
    total = 2 ** len(means)
    for mask in range(total):
        flipped = statistics.mean(m if not (mask >> i) & 1 else -m for i, m in enumerate(means))
        count += abs(flipped) >= abs(observed) - 1e-12
    rng = random.Random(seed)
    boots = sorted(statistics.mean(rng.choices(means, k=len(means))) for _ in range(iterations))
    return {"n_groups": len(means), "diff": observed, "p_value": count / total,
            "ci_low": boots[int(0.025 * iterations)], "ci_high": boots[int(0.975 * iterations) - 1]}


def holm(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    adjusted, running = {}, 0.0
    for index, (key, value) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - index) * value))
        adjusted[key] = running
    return adjusted


def summarize(rows: list[dict], groups: dict[str, list[str]] | None = None) -> dict:
    completed = [r for r in rows if r["status"] == "completed"]
    configs = sorted({(r["provider"], r["architecture"]) for r in rows},
                     key=lambda pa: (pa[0], ARCHS.index(pa[1]) if pa[1] in ARCHS else 9))
    table = []
    for provider, arch in configs:
        group = [r for r in completed if r["provider"] == provider and r["architecture"] == arch]
        primary = [r for r in group if r["block"] == "primary"]
        incidents = [r for r in rows if r["provider"] == provider and r["architecture"] == arch
                     and r["status"] != "completed"]
        successes = sum(r["success"] for r in group)
        low, high = wilson(successes, len(group))
        entry = {
            "provider": provider, "architecture": arch, "episodes": len(group), "incidents": len(incidents),
            "success": rate([r["success"] for r in group]), "success_ci": [low, high],
            "success_primary": rate([r["success"] for r in primary]),
            "goal": rate([r["goal"] for r in group]), "safety": rate([r["safety"] for r in group]),
            "safety_violations": sum(1 for r in group if not r["safety"]),
            "preference": rate([r["preference_adherence"] for r in group if r["preference_adherence"] is not None]),
            "calls": statistics.mean(r["assistant_calls"] for r in group) if group else None,
            "tokens": statistics.mean(r["input_tokens"] + r["output_tokens"] for r in group) if group else None,
            "llm_latency_s": statistics.mean(r["llm_latency_s"] for r in group) if group else None,
            "turns": statistics.mean(r["user_turns"] for r in group) if group else None,
            "fallbacks_per_episode": statistics.mean(r["fallback_count"] for r in group) if group else None,
            "infra_degraded": sum(1 for r in group if r.get("infra_degraded")),
            "simulator_valid": rate([r["simulator_valid"] for r in group if "simulator_valid" in r]),
        }
        for check in CHECKS:
            values = [r["checks"][check]["pass"] for r in group if check in r["checks"]]
            entry[f"check_{check}"] = rate(values)
        by_op = defaultdict(list)
        for r in group:
            by_op[r["operation"]].append(r["success"])
        entry["by_operation"] = {op: rate(v) for op, v in sorted(by_op.items())}
        table.append(entry)
    contrasts = {}
    for provider in sorted({r["provider"] for r in rows}):
        tests = {f"{a}-{b}": paired_bootstrap(rows, a, b, provider) for a, b in (("M5", "S1"), ("M5", "H"), ("S1", "H"))}
        adjusted = holm({k: v["p_value"] for k, v in tests.items() if v.get("n_units")})
        for key, value in tests.items():
            value["p_holm"] = adjusted.get(key)
        contrasts[provider] = tests
    groups = _dependency_groups() if groups is None else groups
    grouped = {}
    for provider in sorted({r["provider"] for r in rows}):
        tests = {f"{a}-{b}": grouped_sign_flip(rows, a, b, provider, groups)
                 for a, b in (("M5", "S1"), ("M5", "H"), ("S1", "H"))}
        adjusted = holm({k: v["p_value"] for k, v in tests.items() if v.get("n_groups")})
        for key, value in tests.items():
            value["p_holm"] = adjusted.get(key)
        grouped[provider] = tests
    by_block = defaultdict(lambda: defaultdict(list))
    for r in completed:
        by_block[f"{r['provider']}:{r['architecture']}"][r["block"]].append(r["success"])
    failures = defaultdict(list)
    for r in completed:
        if not r["success"]:
            failed = [k for k, v in r["checks"].items() if not v["pass"]]
            failures[r["unit_id"]].append(f"{r['provider']}:{r['architecture']}:{'+'.join(failed)}")
    fallback_reasons = defaultdict(int)
    for r in completed:
        for item in r.get("fallbacks", []):
            fallback_reasons[item.split(":")[0]] += 1
    return {"episodes": len(rows), "completed": len(completed), "table": table, "contrasts": contrasts,
            "grouped_contrasts": grouped,
            "by_block": {k: {b: rate(v) for b, v in blocks.items()} for k, blocks in by_block.items()},
            "failures": dict(sorted(failures.items())), "fallback_reasons": dict(fallback_reasons)}


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.0f} %"


def markdown(summary: dict, campaign: str) -> str:
    lines = [f"# Resultados de la campaña `{campaign}`", "",
             f"Episodios registrados: {summary['episodes']} · completados: {summary['completed']}", "",
             "| Proveedor | Arq. | N | Éxito (IC95 %) | Objetivo | Seguridad | Preferencia | Llamadas | Tokens | Latencia LLM (s) | Fallbacks/ep | Incid. |",
             "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for e in summary["table"]:
        lines.append(f"| {e['provider']} | {e['architecture']} | {e['episodes']} | {_pct(e['success'])} "
                     f"({_pct(e['success_ci'][0])}–{_pct(e['success_ci'][1])}) | {_pct(e['goal'])} | {_pct(e['safety'])} | "
                     f"{_pct(e['preference'])} | {e['calls']:.1f} | {e['tokens']:.0f} | {e['llm_latency_s']:.1f} | "
                     f"{e['fallbacks_per_episode']:.2f} | {e['incidents']} |" if e["episodes"] else
                     f"| {e['provider']} | {e['architecture']} | 0 | — | | | | | | | | {e['incidents']} |")
    lines += ["", "## Éxito por gestión", "", "| Proveedor | Arq. | " + " | ".join(
        ("book", "query", "reschedule", "cancel", "reminder")) + " |", "|---|---|" + "---:|" * 5]
    for e in summary["table"]:
        lines.append(f"| {e['provider']} | {e['architecture']} | " + " | ".join(
            _pct(e["by_operation"].get(op)) for op in ("book", "query", "reschedule", "cancel", "reminder")) + " |")
    lines += ["", "## Contrastes pareados (diferencia de éxito, bootstrap por familia, Holm)", "",
              "| Proveedor | Contraste | Unidades | Diferencia | IC95 % | p | p Holm |", "|---|---|---:|---:|---|---:|---:|"]
    for provider, tests in summary["contrasts"].items():
        for key, t in tests.items():
            if t.get("n_units"):
                lines.append(f"| {provider} | {key} | {t['n_units']} | {100 * t['diff']:+.1f} pp | "
                             f"[{100 * t['ci_low']:+.1f}, {100 * t['ci_high']:+.1f}] | {t['p_value']:.3f} | {t['p_holm']:.3f} |")
    lines += ["", "## Sensibilidad: contraste agrupado por los cinco grupos aprobados (cambio de signo exacto)", "",
              "| Proveedor | Contraste | Grupos | Diferencia | IC95 % | p | p Holm |", "|---|---|---:|---:|---|---:|---:|"]
    for provider, tests in summary.get("grouped_contrasts", {}).items():
        for key, t in tests.items():
            if t.get("n_groups"):
                lines.append(f"| {provider} | {key} | {t['n_groups']} | {100 * t['diff']:+.1f} pp | "
                             f"[{100 * t['ci_low']:+.1f}, {100 * t['ci_high']:+.1f}] | {t['p_value']:.4f} | {t['p_holm']:.4f} |")
    lines += ["", "## Éxito por bloque", "", "| Configuración | " + " | ".join(BLOCKS) + " |",
              "|---|" + "---:|" * len(BLOCKS)]
    for key, blocks in summary.get("by_block", {}).items():
        lines.append(f"| {key} | " + " | ".join(_pct(blocks.get(b)) for b in BLOCKS) + " |")
    lines += ["", "## Episodios no satisfactorios", ""]
    for unit, items in summary["failures"].items():
        lines.append(f"- **{unit}**: " + ", ".join(items))
    lines += ["", f"Motivos de fallback: {summary['fallback_reasons']}", "",
              "Validez del usuario simulado por configuración: " + ", ".join(
                  f"{e['provider']}:{e['architecture']} {_pct(e.get('simulator_valid'))}" for e in summary["table"]), ""]
    return "\n".join(lines)


def write_csv(summary: dict, folder: Path) -> None:
    with (folder / "configurations.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["provider", "architecture", "episodes", "success", "ci_low", "ci_high", "goal", "safety",
                         "calls", "tokens", "latency", "fallbacks"])
        for e in summary["table"]:
            if e["episodes"]:
                writer.writerow([e["provider"], e["architecture"], e["episodes"], f"{e['success']:.4f}",
                                 f"{e['success_ci'][0]:.4f}", f"{e['success_ci'][1]:.4f}", f"{e['goal']:.4f}",
                                 f"{e['safety']:.4f}", f"{e['calls']:.2f}", f"{e['tokens']:.0f}",
                                 f"{e['llm_latency_s']:.2f}", f"{e['fallbacks_per_episode']:.3f}"])


def _tex_pct(value: float | None) -> str:
    return "---" if value is None else f"{100 * value:.0f}\\,\\%"


PROVIDER_LABEL = {"groq": "GPT-OSS 20B (Groq)", "google": "Gemini 3.5 Flash-Lite"}


def latex(summary: dict, campaign: str, review: dict | None = None) -> str:
    """Tablas LaTeX listas para \\input en la memoria (se regeneran con cada análisis)."""
    out = [f"% Generado automáticamente por citalab.evaluation.analysis (campaña {campaign}). No editar a mano.",
           "\\begin{table}[htbp]\\centering\\small",
           f"\\caption{{Resultados por configuración (campaña \\texttt{{{campaign}}}).}}\\label{{tab:resultados-config}}",
           "\\resizebox{\\textwidth}{!}{\\begin{tabular}{llrrrrrrr}\\toprule",
           "Modelo & Arq. & N & Éxito (IC95\\,\\%) & Objetivo & Seguridad & Llamadas & Tokens & Fallbacks/ep \\\\ \\midrule"]
    for e in summary["table"]:
        if not e["episodes"]:
            continue
        out.append(f"{PROVIDER_LABEL.get(e['provider'], e['provider'])} & {e['architecture']} & {e['episodes']} & "
                   f"{_tex_pct(e['success'])} ({_tex_pct(e['success_ci'][0])}--{_tex_pct(e['success_ci'][1])}) & "
                   f"{_tex_pct(e['goal'])} & {_tex_pct(e['safety'])} & {e['calls']:.1f} & {e['tokens']:.0f} & "
                   f"{e['fallbacks_per_episode']:.2f} \\\\")
    out += ["\\bottomrule\\end{tabular}}\\end{table}", "",
            "\\begin{table}[htbp]\\centering\\small",
            "\\caption{Éxito integral por gestión.}\\label{tab:resultados-gestion}",
            "\\resizebox{\\textwidth}{!}{\\begin{tabular}{llrrrrr}\\toprule",
            "Modelo & Arq. & Reserva & Consulta & Reprogramación & Cancelación & Recordatorio \\\\ \\midrule"]
    for e in summary["table"]:
        if e["episodes"]:
            ops = " & ".join(_tex_pct(e["by_operation"].get(op))
                             for op in ("book", "query", "reschedule", "cancel", "reminder"))
            out.append(f"{PROVIDER_LABEL.get(e['provider'], e['provider'])} & {e['architecture']} & {ops} \\\\")
    out += ["\\bottomrule\\end{tabular}}\\end{table}", "",
            "\\begin{table}[htbp]\\centering\\small",
            "\\caption{Contrastes pareados por familia: diferencia de éxito, IC95\\,\\% bootstrap y $p$ de Holm.}",
            "\\label{tab:resultados-contrastes}",
            "\\resizebox{\\textwidth}{!}{\\begin{tabular}{llrrcr}\\toprule",
            "Modelo & Contraste & Unidades & Diferencia & IC95\\,\\% & $p$ Holm \\\\ \\midrule"]
    for provider, tests in summary["contrasts"].items():
        for key, t in tests.items():
            if t.get("n_units"):
                out.append(f"{PROVIDER_LABEL.get(provider, provider)} & {key.replace('-', '--')} & {t['n_units']} & "
                           f"{100 * t['diff']:+.1f}\\,pp & [{100 * t['ci_low']:+.1f}, {100 * t['ci_high']:+.1f}] & "
                           f"{t['p_holm']:.3f} \\\\")
    out += ["\\bottomrule\\end{tabular}}\\end{table}", "",
            "\\begin{table}[htbp]\\centering\\small",
            "\\caption{Sensibilidad: contraste agrupado por los cinco grupos de dependencia (cambio de signo exacto, Holm).}",
            "\\label{tab:resultados-agrupados}",
            "\\resizebox{\\textwidth}{!}{\\begin{tabular}{llrrcrr}\\toprule",
            "Modelo & Contraste & Grupos & Diferencia & IC95\\,\\% & $p$ & $p$ Holm \\\\ \\midrule"]
    for provider, tests in summary.get("grouped_contrasts", {}).items():
        for key, t in tests.items():
            if t.get("n_groups"):
                out.append(f"{PROVIDER_LABEL.get(provider, provider)} & {key.replace('-', '--')} & {t['n_groups']} & "
                           f"{100 * t['diff']:+.1f}\\,pp & [{100 * t['ci_low']:+.1f}, {100 * t['ci_high']:+.1f}] & "
                           f"{t['p_value']:.4f} & {t['p_holm']:.4f} \\\\")
    out += ["\\bottomrule\\end{tabular}}\\end{table}", "",
            "\\begin{table}[htbp]\\centering\\small",
            "\\caption{Éxito integral por bloque de la campaña.}\\label{tab:resultados-bloques}",
            "\\resizebox{\\textwidth}{!}{\\begin{tabular}{lrrrrr}\\toprule",
            "Configuración & Primarios & Repetición & Preferencias & Persona & Casos nuevos \\\\ \\midrule"]
    for key, blocks in sorted(summary.get("by_block", {}).items()):
        out.append(f"{key} & " + " & ".join(_tex_pct(blocks.get(b)) for b in BLOCKS) + " \\\\")
    out += ["\\bottomrule\\end{tabular}}\\end{table}", ""]
    if review and review.get("by_configuration"):
        out += ["\\begin{table}[htbp]\\centering\\small",
                "\\caption{Revisión humana ciega (media 0--3) y fidelidad material.}\\label{tab:resultados-revision}",
                "\\resizebox{\\textwidth}{!}{\\begin{tabular}{lrrrrrrrr}\\toprule",
                "Configuración & N & Admin. & Continuidad & Claridad & Redundancia & Perfil & Fidelidad & Simulador \\\\ \\midrule"]
        for key, v in sorted(review["by_configuration"].items()):
            sim = [v.get(k) for k in v if k.startswith("simulator_") and v.get(k) is not None]
            cells = [v.get(d) for d in ("administrative", "continuity", "clarity", "redundancy", "profile_fit",
                                        "material_fidelity")]
            values = " & ".join("---" if c is None else f"{c:.2f}" for c in cells)
            sim_text = f"{sum(sim) / len(sim):.2f}" if sim else "---"
            out.append(f"{key} & {v['n']} & {values} & {sim_text} \\\\")
        out += ["\\bottomrule\\end{tabular}}\\end{table}", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--latex", default="", help="ruta del .tex a generar para la memoria")
    args = parser.parse_args(argv)
    rows = load(args.campaign)
    summary = summarize(rows, _dependency_groups(args.campaign))
    folder = OUTPUT / "evaluation" / args.campaign
    (folder / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    text = markdown(summary, args.campaign)
    (folder / "summary.md").write_text(text, encoding="utf-8")
    write_csv(summary, folder)
    if args.latex:
        from citalab.evaluation.review import agreement, scores_by_configuration
        review = {"by_configuration": scores_by_configuration(args.campaign), "agreement": agreement(args.campaign)}
        target = Path(args.latex)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(latex(summary, args.campaign, review), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
