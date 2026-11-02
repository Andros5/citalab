"""CLI de la evaluación mixta.

    python -m citalab_judge sample  --campaign C          # fija la muestra humana (una vez)
    python -m citalab_judge judge   --judge codex --calibration
    python -m citalab_judge judge   --judge claude --campaign C   # relanzar si se pausa por límite
    python -m citalab_judge review  --campaign C          # revisión humana en 127.0.0.1:8766
    python -m citalab_judge report  --campaign C
    python -m citalab_judge show    --campaign pilot-5 --cell <cell_id>   # vista ciega (depuración)
"""

from __future__ import annotations

import argparse
import sys

FINAL = "final-independent-v1"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="python -m citalab_judge")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sample", "judge", "review", "report", "show"):
        command = sub.add_parser(name)
        command.add_argument("--campaign", default=FINAL)
        if name == "judge":
            command.add_argument("--judge", choices=("claude", "codex"), required=True)
            command.add_argument("--calibration", action="store_true",
                                 help="10 episodios del piloto de desarrollo pilot-5 (nunca la campaña final)")
            command.add_argument("--limit", type=int)
            command.add_argument("--providers", help="p. ej. groq; por defecto todos los completados")
            command.add_argument("--no-repetitions", action="store_true")
        if name == "show":
            command.add_argument("--cell", required=True)
        if name == "review":
            command.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)

    if args.command == "sample":
        from citalab_judge import sample
        manifest = sample.create(args.campaign)
        print(f"Muestra {manifest['version']}: {len(manifest['cells'])} episodios, "
              f"{len(manifest['second_pass'])} en segunda pasada -> {sample.path(args.campaign)}")
    elif args.command == "judge":
        from citalab_judge import judge
        campaign, limit = args.campaign, args.limit
        if args.calibration:
            campaign, limit = judge.CALIBRATION_CAMPAIGN, limit or judge.CALIBRATION_SIZE
        counts = judge.run(campaign, judge.make(args.judge), limit=limit,
                           repetitions=not (args.no_repetitions or args.calibration),
                           providers=args.providers.split(",") if args.providers else None)
        print(f"Resumen: {counts}")
        return 3 if counts["stopped"] == "usage-limit" else 0
    elif args.command == "review":
        from citalab_judge.review_app import serve
        serve(args.campaign, args.port)
    elif args.command == "report":
        from citalab_judge.agreement import write_report
        write_report(args.campaign)
        print(f"Informe en output/evaluation/{args.campaign}/judge/report.md y tables.tex")
    elif args.command == "show":
        from citalab_judge.episode import build, campaign_rows, render, scenarios_for
        row = next(r for r in campaign_rows(args.campaign) if r["cell_id"] == args.cell)
        print(render(build(row, scenarios_for(args.campaign))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
