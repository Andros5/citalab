"""Concordancia juez-humano y estimación principal por PPI++.

- Por dimensión: pares comparables (ambos con nota, NA excluidos), acuerdo exacto y a ±1,
  kappa ponderada cuadrática, sesgo medio (juez − humano) y error absoluto medio.
- Comparaciones: humano-cada juez, humano-media del jurado, juez-juez, humano pasada 1-2 y
  autoconsistencia de cada juez. Se informan por separado.
- Media por configuración con inferencia potenciada por predicción (Angelopoulos et al., 2023;
  PPI++ con λ ajustado): la muestra humana corrige el sesgo del jurado medido en el 100 %.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from math import sqrt

from citalab.evaluation.review import DIMENSIONS, SIMULATOR_DIMENSIONS, _quadratic_kappa
from citalab_judge import judge_folder
from citalab_judge import sample as sample_module
from citalab_judge.judge import JUDGES, latest_valid, read_judgments

Z = 1.959964
LABELS = {"groq": "GPT-OSS 20B", "google": "Gemini 3.5 Flash-Lite"}


def configuration(cell_id: str) -> str:
    provider, architecture = cell_id.split(":")[:2]
    return f"{provider}:{architecture}"


def reviews_path(campaign: str):
    return judge_folder(campaign) / "reviews-v1.jsonl"


def human(campaign: str) -> dict[tuple[str, int], dict]:
    path = reviews_path(campaign)
    latest: dict[tuple[str, int], dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                latest[(item["cell_id"], item["pass"])] = item
    return latest


def _flat_human(item: dict) -> dict:
    return {**item.get("scores", {}), **{f"sim.{k}": v for k, v in (item.get("simulator_scores") or {}).items()}}


def _flat_judge(item: dict) -> dict:
    scores = item["scores"]
    return {**{k: v["score"] for k, v in scores["assistant"].items()},
            **{f"sim.{k}": v["score"] for k, v in scores["simulator"].items()}}


DIMS = list(DIMENSIONS) + [f"sim.{k}" for k in SIMULATOR_DIMENSIONS]


def judge_scores(campaign: str, name: str, repetition: int = 0) -> dict[str, dict]:
    return {cell: _flat_judge(item) for cell, item in latest_valid(campaign, name, repetition).items()}


def jury_scores(campaign: str) -> dict[str, dict]:
    """Media de los jueces por celda y dimensión; solo si todos los jueces dieron nota."""
    per_judge = [judge_scores(campaign, name) for name in JUDGES]
    cells = set.intersection(*(set(scores) for scores in per_judge)) if per_judge else set()
    result = {}
    for cell in cells:
        values = {}
        for dim in DIMS:
            notes = [scores[cell].get(dim) for scores in per_judge]
            values[dim] = None if any(n is None for n in notes) else sum(notes) / len(notes)
        result[cell] = values
    return result


def compare(a: dict[str, dict], b: dict[str, dict], integer: bool = True) -> dict:
    """Estadísticos por dimensión entre dos evaluadores (b − a para el sesgo)."""
    result = {}
    for dim in DIMS:
        pairs = [(a[c][dim], b[c][dim]) for c in a.keys() & b.keys()
                 if a[c].get(dim) is not None and b[c].get(dim) is not None]
        if not pairs:
            result[dim] = {"n": 0}
            continue
        diffs = [y - x for x, y in pairs]
        entry = {"n": len(pairs), "exact": sum(abs(d) < 0.25 for d in diffs) / len(pairs),
                 "within_one": sum(abs(d) <= 1 for d in diffs) / len(pairs),
                 "bias": sum(diffs) / len(diffs), "mae": sum(abs(d) for d in diffs) / len(diffs)}
        if integer:
            entry["kappa"] = _quadratic_kappa([int(x) for x, _ in pairs], [int(y) for _, y in pairs], 4)
        result[dim] = entry
    return result


def ppi_mean(labeled: list[tuple[float, float]], unlabeled: list[float]) -> dict:
    """PPI++ para una media: θ = mean(Y) + λ·(mean(f_u) − mean(f_l)), λ óptimo recortado a [0, 1]."""
    n, big_n = len(labeled), len(unlabeled)
    if n < 2:
        return {"n": n, "N": big_n, "estimate": None}
    y = [h for h, _ in labeled]
    f_l = [f for _, f in labeled]
    mean_y, mean_fl = statistics.fmean(y), statistics.fmean(f_l)
    if big_n < 2:
        sd = statistics.stdev(y)
        return {"n": n, "N": big_n, "lambda": 0.0, "estimate": mean_y,
                "ci": (mean_y - Z * sd / sqrt(n), mean_y + Z * sd / sqrt(n))}
    mean_fu = statistics.fmean(unlabeled)
    var_fl = statistics.variance(f_l)
    cov = sum((a - mean_y) * (b - mean_fl) for a, b in labeled) / (n - 1)
    lam = 0.0 if var_fl == 0 else max(0.0, min(1.0, cov / ((1 + n / big_n) * var_fl)))
    estimate = mean_y + lam * (mean_fu - mean_fl)
    residual = [h - lam * f for h, f in labeled]
    variance = statistics.variance(residual) / n + lam ** 2 * statistics.variance(unlabeled) / big_n
    half = Z * sqrt(variance)
    return {"n": n, "N": big_n, "lambda": lam, "estimate": estimate, "ci": (estimate - half, estimate + half),
            "human_only": mean_y, "judge_only": statistics.fmean([*f_l, *unlabeled])}


def ppi_by(campaign: str, key=configuration) -> dict:
    jury = jury_scores(campaign)
    reviewed = {cell: _flat_human(item) for (cell, review_pass), item in human(campaign).items() if review_pass == 1}
    groups: dict[str, list[str]] = defaultdict(list)
    for cell in jury:
        groups[key(cell)].append(cell)
    result = {}
    for group, cells in sorted(groups.items()):
        result[group] = {}
        for dim in DIMS:
            labeled = [(reviewed[c][dim], jury[c][dim]) for c in cells
                       if c in reviewed and reviewed[c].get(dim) is not None and jury[c][dim] is not None]
            unlabeled = [jury[c][dim] for c in cells if c not in reviewed and jury[c][dim] is not None]
            result[group][dim] = ppi_mean(labeled, unlabeled)
    return result


def incidents(campaign: str) -> dict:
    result = {}
    for name in JUDGES:
        items = read_judgments(campaign, name)
        valid = {(i["cell_id"], i["repetition"]) for i in items if i["status"] == "valid"}
        failed = {(i["cell_id"], i["repetition"]) for i in items if i["status"] != "valid"} - valid
        result[name] = {"valid": len(valid), "unresolved": len(failed),
                        "attempts_over_one": sum(1 for i in items if i.get("attempts", 1) > 1),
                        "models": sorted({i.get("model") for i in items}),
                        "cli_versions": sorted({str(i.get("cli_version")) for i in items})}
    return result


def summary(campaign: str) -> dict:
    reviews = human(campaign)
    first = {c: _flat_human(i) for (c, p), i in reviews.items() if p == 1}
    second = {c: _flat_human(i) for (c, p), i in reviews.items() if p == 2}
    judges = {name: judge_scores(campaign, name) for name in JUDGES}
    names = list(JUDGES)
    manifest = sample_module.load(campaign) or {}
    return {
        "campaign": campaign,
        "sample": {"cells": len(manifest.get("cells", [])), "reviewed_pass_1": len(first),
                   "reviewed_pass_2": len(second)},
        "incidents": incidents(campaign),
        "human_vs_judge": {name: compare(first, scores) for name, scores in judges.items()},
        "human_vs_jury": compare(first, jury_scores(campaign), integer=False),
        "judge_vs_judge": compare(judges[names[0]], judges[names[1]]) if len(names) == 2 else {},
        "human_intra": compare(first, second),
        "judge_self": {name: compare(scores, judge_scores(campaign, name, 1)) for name, scores in judges.items()},
        "ppi_by_configuration": ppi_by(campaign),
        "ppi_by_architecture": ppi_by(campaign, key=lambda cell: cell.split(":")[1]),
    }


def _fmt(value, digits: int = 2) -> str:
    return "n/d" if value is None else f"{value:.{digits}f}"


def markdown(data: dict) -> str:
    out = [f"# Evaluación mixta: {data['campaign']}", "",
           "Resultados deterministas (oráculo), juez, humano e incidentes se informan por separado.", "",
           (f"Muestra humana: {data['sample']['reviewed_pass_1']}/{data['sample']['cells']} revisados "
           f"(segunda pasada: {data['sample']['reviewed_pass_2']})."), "", "## Incidentes del jurado", ""]
    for name, info in data["incidents"].items():
        out.append(f"- {name}: {info['valid']} válidas, {info['unresolved']} sin resolver, "
                   f"{info['attempts_over_one']} con reparación; modelos {info['models']}; CLI {info['cli_versions']}")

    def table(title: str, stats: dict, kappa: bool = True) -> None:
        out.extend(["", f"## {title}", "", "| Dimensión | n | Exacto | ±1 | κ | Sesgo | EAM |",
                    "|---|---:|---:|---:|---:|---:|---:|"])
        for dim in DIMS:
            s = stats.get(dim, {"n": 0})
            if not s["n"]:
                out.append(f"| {dim} | 0 | | | | | |")
                continue
            out.append(f"| {dim} | {s['n']} | {_fmt(s['exact'])} | {_fmt(s['within_one'])} | "
                       f"{_fmt(s.get('kappa')) if kappa else 'n/d'} | {s['bias']:+.2f} | {_fmt(s['mae'])} |")

    for name, stats in data["human_vs_judge"].items():
        table(f"Humano frente a {name}", stats)
    table("Humano frente a la media del jurado", data["human_vs_jury"], kappa=False)
    if data["judge_vs_judge"]:
        table("Juez frente a juez", data["judge_vs_judge"])
    table("Humano: primera frente a segunda pasada", data["human_intra"])
    for name, stats in data["judge_self"].items():
        table(f"Autoconsistencia de {name}", stats)
    for title, block in (("PPI por configuración", data["ppi_by_configuration"]),
                         ("PPI por arquitectura", data["ppi_by_architecture"])):
        out.extend(["", f"## {title}", "", ("| Grupo | Dimensión | n | N | λ | Estimación | IC95 % | Solo humano "
                    "| Solo jurado |"), "|---|---|---:|---:|---:|---:|---|---:|---:|"])
        for group, dims in block.items():
            for dim, r in dims.items():
                ci = r.get("ci")
                out.append(f"| {group} | {dim} | {r['n']} | {r['N']} | {_fmt(r.get('lambda'))} | "
                           f"{_fmt(r.get('estimate'))} | {f'[{ci[0]:.2f}, {ci[1]:.2f}]' if ci else 'n/d'} | "
                           f"{_fmt(r.get('human_only'))} | {_fmt(r.get('judge_only'))} |")
    return "\n".join(out) + "\n"


SHORT = {"administrative": "Administrativa", "continuity": "Continuidad", "clarity": "Claridad",
         "redundancy": "Sin repetición", "profile_fit": "Perfil", "material_fidelity": "Fidelidad"}


def latex(data: dict) -> str:
    names = list(data["human_vs_judge"])
    out = [f"% Generado por citalab_judge.agreement (campaña {data['campaign']}). No editar a mano.",
           "\\begin{table}[!htbp]\\centering\\small",
           ("\\caption{Concordancia con la revisión humana por dimensión del asistente: kappa ponderada "
           "cuadrática de cada juez y sesgo medio del jurado (jurado menos humano).}"),
           "\\label{tab:juez-concordancia}",
           "\\begin{tabular}{l" + "r" * (len(names) + 3) + "}\\toprule",
           "Dimensión & n & " + " & ".join(f"$\\kappa$ {n.capitalize()}" for n in names)
           + " & $\\pm 1$ jurado & Sesgo jurado \\\\ \\midrule"]
    for dim in DIMENSIONS:
        jury = data["human_vs_jury"].get(dim, {"n": 0})
        kappas = " & ".join(_fmt(data["human_vs_judge"][n].get(dim, {}).get("kappa")) for n in names)
        bias = f"{jury['bias']:+.2f}" if jury["n"] else "n/d"
        out.append(f"{SHORT[dim]} & {jury['n']} & {kappas} & {_fmt(jury.get('within_one'))} & {bias} \\\\")
    out += ["\\bottomrule\\end{tabular}\\end{table}", "",
            "\\begin{table}[!htbp]\\centering\\small",
            ("\\caption{Nota media por configuración estimada con PPI++ (jurado en todos los episodios y "
            "muestra humana), con IC95\\,\\%.}"),
            "\\label{tab:juez-ppi}",
            "\\resizebox{\\textwidth}{!}{\\begin{tabular}{ll" + "c" * len(DIMENSIONS) + "}\\toprule",
            "Modelo & Arq. & " + " & ".join(SHORT[d] for d in DIMENSIONS) + " \\\\ \\midrule"]
    for group, dims in data["ppi_by_configuration"].items():
        provider, architecture = group.split(":")
        cells = []
        for dim in DIMENSIONS:
            r = dims.get(dim, {})
            ci = r.get("ci")
            cells.append("n/d" if r.get("estimate") is None
                         else f"{r['estimate']:.2f} [{ci[0]:.2f}, {ci[1]:.2f}]")
        out.append(f"{LABELS.get(provider, provider)} & {architecture} & " + " & ".join(cells) + " \\\\")
    out += ["\\bottomrule\\end{tabular}}\\end{table}"]
    return "\n".join(out) + "\n"


def write_report(campaign: str) -> dict:
    data = summary(campaign)
    folder = judge_folder(campaign)
    (folder / "report.json").write_text(json.dumps(data, indent=2, ensure_ascii=False, default=list),
                                        encoding="utf-8")
    (folder / "report.md").write_text(markdown(data), encoding="utf-8")
    (folder / "tables.tex").write_text(latex(data), encoding="utf-8")
    return data
