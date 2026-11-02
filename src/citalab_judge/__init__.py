"""Evaluación mixta de conversaciones: jurado LLM sobre todos los episodios y muestra humana ciega.

Paquete separado de `citalab` a propósito: la campaña congelada fija el hash de
`src/citalab/**`, así que esta evaluación importa CitaLab sin modificarlo.
"""

from citalab.config import OUTPUT


def judge_folder(campaign: str):
    folder = OUTPUT / "evaluation" / campaign / "judge"
    folder.mkdir(parents=True, exist_ok=True)
    return folder
