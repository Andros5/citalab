# Evaluación mixta: final-independent-v1

Resultados deterministas (oráculo), juez, humano e incidentes se informan por separado.

Muestra humana: 60/60 revisados (segunda pasada: 12).

## Incidentes del jurado

- claude: 304 válidas, 0 sin resolver, 11 con reparación; modelos ['claude-sonnet-5-5']; CLI ['2.1.309 (Claude Code)']
- codex: 304 válidas, 0 sin resolver, 2 con reparación; modelos ['gpt-6.1-terra']; CLI ['codex-cli 0.166.0-alpha.5.1']

## Humano frente a claude

| Dimensión | n | Exacto | ±1 | κ | Sesgo | EAM |
|---|---:|---:|---:|---:|---:|---:|
| administrative | 60 | 0.82 | 1.00 | 0.73 | -0.08 | 0.18 |
| continuity | 53 | 0.87 | 0.98 | 0.59 | -0.15 | 0.15 |
| clarity | 60 | 0.87 | 1.00 | 0.70 | -0.10 | 0.13 |
| redundancy | 60 | 0.93 | 1.00 | 0.71 | +0.00 | 0.07 |
| profile_fit | 60 | 0.72 | 1.00 | 0.64 | -0.25 | 0.28 |
| material_fidelity | 60 | 0.88 | 0.97 | 0.58 | -0.05 | 0.15 |
| sim.goal_fidelity | 60 | 0.97 | 0.97 | 0.00 | -0.07 | 0.07 |
| sim.coherence | 60 | 0.97 | 1.00 | 0.00 | -0.03 | 0.03 |
| sim.allowed_information | 60 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.no_invention | 60 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.correct_confirmations | 47 | 0.98 | 1.00 | 0.00 | -0.02 | 0.02 |

## Humano frente a codex

| Dimensión | n | Exacto | ±1 | κ | Sesgo | EAM |
|---|---:|---:|---:|---:|---:|---:|
| administrative | 60 | 0.80 | 0.95 | 0.59 | -0.15 | 0.25 |
| continuity | 53 | 0.94 | 0.98 | 0.54 | -0.04 | 0.08 |
| clarity | 60 | 0.95 | 1.00 | 0.80 | +0.05 | 0.05 |
| redundancy | 60 | 0.87 | 1.00 | 0.59 | -0.13 | 0.13 |
| profile_fit | 60 | 0.73 | 0.98 | 0.51 | -0.15 | 0.28 |
| material_fidelity | 60 | 0.85 | 0.93 | 0.51 | -0.15 | 0.22 |
| sim.goal_fidelity | 60 | 0.97 | 1.00 | 0.00 | -0.03 | 0.03 |
| sim.coherence | 60 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.allowed_information | 60 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.no_invention | 60 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.correct_confirmations | 47 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |

## Humano frente a la media del jurado

| Dimensión | n | Exacto | ±1 | κ | Sesgo | EAM |
|---|---:|---:|---:|---:|---:|---:|
| administrative | 60 | 0.77 | 0.98 | n/d | -0.12 | 0.22 |
| continuity | 53 | 0.89 | 0.98 | n/d | -0.09 | 0.09 |
| clarity | 60 | 0.83 | 1.00 | n/d | -0.03 | 0.09 |
| redundancy | 60 | 0.83 | 1.00 | n/d | -0.07 | 0.10 |
| profile_fit | 60 | 0.62 | 0.98 | n/d | -0.20 | 0.28 |
| material_fidelity | 60 | 0.87 | 0.95 | n/d | -0.10 | 0.17 |
| sim.goal_fidelity | 60 | 0.95 | 0.98 | n/d | -0.05 | 0.05 |
| sim.coherence | 60 | 0.97 | 1.00 | n/d | -0.02 | 0.02 |
| sim.allowed_information | 60 | 1.00 | 1.00 | n/d | +0.00 | 0.00 |
| sim.no_invention | 60 | 1.00 | 1.00 | n/d | +0.00 | 0.00 |
| sim.correct_confirmations | 47 | 0.98 | 1.00 | n/d | -0.01 | 0.01 |

## Juez frente a juez

| Dimensión | n | Exacto | ±1 | κ | Sesgo | EAM |
|---|---:|---:|---:|---:|---:|---:|
| administrative | 276 | 0.87 | 0.99 | 0.87 | -0.05 | 0.14 |
| continuity | 246 | 0.83 | 0.99 | 0.74 | +0.14 | 0.18 |
| clarity | 276 | 0.86 | 1.00 | 0.67 | +0.10 | 0.14 |
| redundancy | 276 | 0.92 | 1.00 | 0.83 | -0.05 | 0.08 |
| profile_fit | 276 | 0.76 | 1.00 | 0.68 | +0.07 | 0.24 |
| material_fidelity | 276 | 0.86 | 0.97 | 0.78 | -0.12 | 0.17 |
| sim.goal_fidelity | 276 | 0.96 | 0.99 | 0.59 | +0.03 | 0.05 |
| sim.coherence | 276 | 0.99 | 1.00 | 0.00 | +0.01 | 0.01 |
| sim.allowed_information | 276 | 0.99 | 1.00 | 0.00 | +0.01 | 0.01 |
| sim.no_invention | 276 | 1.00 | 1.00 | 0.00 | +0.00 | 0.00 |
| sim.correct_confirmations | 196 | 0.99 | 1.00 | 0.95 | +0.01 | 0.01 |

## Humano: primera frente a segunda pasada

| Dimensión | n | Exacto | ±1 | κ | Sesgo | EAM |
|---|---:|---:|---:|---:|---:|---:|
| administrative | 12 | 0.92 | 1.00 | 0.83 | +0.08 | 0.08 |
| continuity | 12 | 0.83 | 1.00 | 0.00 | +0.17 | 0.17 |
| clarity | 12 | 0.92 | 1.00 | 0.82 | +0.08 | 0.08 |
| redundancy | 12 | 0.92 | 1.00 | 0.80 | -0.08 | 0.08 |
| profile_fit | 12 | 0.92 | 1.00 | 0.82 | -0.08 | 0.08 |
| material_fidelity | 12 | 0.92 | 1.00 | 0.82 | +0.08 | 0.08 |
| sim.goal_fidelity | 12 | 0.92 | 1.00 | 0.00 | -0.08 | 0.08 |
| sim.coherence | 12 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.allowed_information | 12 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.no_invention | 12 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.correct_confirmations | 10 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |

## Autoconsistencia de claude

| Dimensión | n | Exacto | ±1 | κ | Sesgo | EAM |
|---|---:|---:|---:|---:|---:|---:|
| administrative | 28 | 0.93 | 1.00 | 0.94 | -0.07 | 0.07 |
| continuity | 25 | 0.96 | 1.00 | 0.96 | -0.04 | 0.04 |
| clarity | 28 | 0.93 | 1.00 | 0.88 | +0.00 | 0.07 |
| redundancy | 28 | 0.96 | 1.00 | 0.92 | +0.04 | 0.04 |
| profile_fit | 28 | 0.86 | 1.00 | 0.74 | +0.00 | 0.14 |
| material_fidelity | 28 | 0.93 | 1.00 | 0.92 | -0.07 | 0.07 |
| sim.goal_fidelity | 28 | 0.96 | 1.00 | -0.00 | +0.04 | 0.04 |
| sim.coherence | 28 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.allowed_information | 28 | 0.96 | 1.00 | 0.65 | +0.04 | 0.04 |
| sim.no_invention | 28 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.correct_confirmations | 19 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |

## Autoconsistencia de codex

| Dimensión | n | Exacto | ±1 | κ | Sesgo | EAM |
|---|---:|---:|---:|---:|---:|---:|
| administrative | 28 | 0.96 | 0.96 | 0.84 | -0.11 | 0.11 |
| continuity | 24 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| clarity | 28 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| redundancy | 28 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| profile_fit | 28 | 0.96 | 1.00 | 0.92 | +0.04 | 0.04 |
| material_fidelity | 28 | 0.96 | 0.96 | 0.80 | -0.11 | 0.11 |
| sim.goal_fidelity | 28 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.coherence | 28 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.allowed_information | 28 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.no_invention | 28 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |
| sim.correct_confirmations | 19 | 1.00 | 1.00 | 1.00 | +0.00 | 0.00 |

## PPI por configuración

| Grupo | Dimensión | n | N | λ | Estimación | IC95 % | Solo humano | Solo jurado |
|---|---|---:|---:|---:|---:|---|---:|---:|
| google:H | administrative | 10 | 36 | 0.65 | 2.79 | [2.60, 2.98] | 2.90 | 2.72 |
| google:H | continuity | 9 | 32 | 0.78 | 2.84 | [2.69, 3.00] | 2.89 | 2.84 |
| google:H | clarity | 10 | 36 | 0.52 | 2.93 | [2.87, 2.99] | 2.90 | 2.89 |
| google:H | redundancy | 10 | 36 | 0.57 | 2.86 | [2.71, 3.01] | 2.90 | 2.75 |
| google:H | profile_fit | 10 | 36 | 0.15 | 2.77 | [2.51, 3.02] | 2.80 | 2.52 |
| google:H | material_fidelity | 10 | 36 | 0.65 | 2.85 | [2.69, 3.02] | 2.90 | 2.79 |
| google:H | sim.goal_fidelity | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:H | sim.coherence | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:H | sim.allowed_information | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:H | sim.no_invention | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:H | sim.correct_confirmations | 8 | 25 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:M5 | administrative | 10 | 36 | 0.36 | 2.81 | [2.68, 2.94] | 2.80 | 2.62 |
| google:M5 | continuity | 9 | 31 | 0.52 | 2.82 | [2.68, 2.97] | 2.89 | 2.74 |
| google:M5 | clarity | 10 | 36 | 0.48 | 2.90 | [2.79, 3.00] | 2.90 | 2.79 |
| google:M5 | redundancy | 10 | 36 | 0.78 | 2.70 | [2.54, 2.86] | 2.90 | 2.70 |
| google:M5 | profile_fit | 10 | 36 | 0.39 | 2.82 | [2.59, 3.04] | 2.80 | 2.53 |
| google:M5 | material_fidelity | 10 | 36 | 0.13 | 2.90 | [2.72, 3.09] | 2.90 | 2.71 |
| google:M5 | sim.goal_fidelity | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.97 |
| google:M5 | sim.coherence | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| google:M5 | sim.allowed_information | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| google:M5 | sim.no_invention | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:M5 | sim.correct_confirmations | 7 | 25 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:S1 | administrative | 10 | 36 | 0.32 | 2.97 | [2.86, 3.07] | 2.90 | 2.86 |
| google:S1 | continuity | 8 | 32 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.91 |
| google:S1 | clarity | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.92 |
| google:S1 | redundancy | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.90 |
| google:S1 | profile_fit | 10 | 36 | 0.58 | 2.56 | [2.38, 2.74] | 2.50 | 2.53 |
| google:S1 | material_fidelity | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.96 |
| google:S1 | sim.goal_fidelity | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:S1 | sim.coherence | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:S1 | sim.allowed_information | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:S1 | sim.no_invention | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| google:S1 | sim.correct_confirmations | 9 | 25 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| groq:H | administrative | 10 | 36 | 0.52 | 2.68 | [2.47, 2.90] | 2.80 | 2.52 |
| groq:H | continuity | 9 | 32 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.74 |
| groq:H | clarity | 10 | 36 | 0.78 | 2.78 | [2.66, 2.91] | 2.90 | 2.78 |
| groq:H | redundancy | 10 | 36 | 0.52 | 2.84 | [2.64, 3.04] | 2.90 | 2.76 |
| groq:H | profile_fit | 10 | 36 | 0.57 | 2.48 | [2.25, 2.70] | 2.60 | 2.23 |
| groq:H | material_fidelity | 10 | 36 | 0.39 | 2.80 | [2.63, 2.98] | 2.90 | 2.61 |
| groq:H | sim.goal_fidelity | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.89 |
| groq:H | sim.coherence | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| groq:H | sim.allowed_information | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| groq:H | sim.no_invention | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| groq:H | sim.correct_confirmations | 8 | 25 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| groq:M5 | administrative | 10 | 36 | 0.40 | 2.39 | [2.14, 2.64] | 2.40 | 2.34 |
| groq:M5 | continuity | 9 | 33 | 0.43 | 2.81 | [2.66, 2.95] | 2.78 | 2.61 |
| groq:M5 | clarity | 10 | 36 | 0.63 | 2.66 | [2.44, 2.87] | 2.60 | 2.62 |
| groq:M5 | redundancy | 10 | 36 | 0.79 | 2.56 | [2.36, 2.76] | 2.50 | 2.61 |
| groq:M5 | profile_fit | 10 | 36 | 0.54 | 2.48 | [2.23, 2.73] | 2.50 | 2.12 |
| groq:M5 | material_fidelity | 10 | 36 | 0.14 | 2.68 | [2.38, 2.97] | 2.70 | 2.47 |
| groq:M5 | sim.goal_fidelity | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.92 |
| groq:M5 | sim.coherence | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.98 |
| groq:M5 | sim.allowed_information | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| groq:M5 | sim.no_invention | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| groq:M5 | sim.correct_confirmations | 7 | 24 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.98 |
| groq:S1 | administrative | 10 | 36 | 0.27 | 2.45 | [2.19, 2.71] | 2.40 | 2.45 |
| groq:S1 | continuity | 9 | 32 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.82 |
| groq:S1 | clarity | 10 | 36 | 0.80 | 2.64 | [2.40, 2.88] | 2.70 | 2.79 |
| groq:S1 | redundancy | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.90 |
| groq:S1 | profile_fit | 10 | 36 | 0.18 | 2.14 | [1.96, 2.31] | 2.10 | 2.07 |
| groq:S1 | material_fidelity | 10 | 36 | 0.45 | 2.44 | [2.13, 2.74] | 2.40 | 2.41 |
| groq:S1 | sim.goal_fidelity | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.90 |
| groq:S1 | sim.coherence | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| groq:S1 | sim.allowed_information | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| groq:S1 | sim.no_invention | 10 | 36 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| groq:S1 | sim.correct_confirmations | 8 | 25 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.91 |

## PPI por arquitectura

| Grupo | Dimensión | n | N | λ | Estimación | IC95 % | Solo humano | Solo jurado |
|---|---|---:|---:|---:|---:|---|---:|---:|
| H | administrative | 20 | 72 | 0.56 | 2.74 | [2.60, 2.88] | 2.85 | 2.62 |
| H | continuity | 18 | 64 | 0.64 | 2.84 | [2.74, 2.95] | 2.94 | 2.79 |
| H | clarity | 20 | 72 | 0.60 | 2.87 | [2.81, 2.94] | 2.90 | 2.84 |
| H | redundancy | 20 | 72 | 0.55 | 2.85 | [2.73, 2.97] | 2.90 | 2.76 |
| H | profile_fit | 20 | 72 | 0.40 | 2.61 | [2.43, 2.79] | 2.70 | 2.38 |
| H | material_fidelity | 20 | 72 | 0.49 | 2.82 | [2.70, 2.94] | 2.90 | 2.70 |
| H | sim.goal_fidelity | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.95 |
| H | sim.coherence | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| H | sim.allowed_information | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| H | sim.no_invention | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| H | sim.correct_confirmations | 16 | 50 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| M5 | administrative | 20 | 72 | 0.40 | 2.60 | [2.45, 2.76] | 2.60 | 2.48 |
| M5 | continuity | 18 | 64 | 0.45 | 2.82 | [2.72, 2.92] | 2.83 | 2.67 |
| M5 | clarity | 20 | 72 | 0.59 | 2.77 | [2.65, 2.90] | 2.75 | 2.71 |
| M5 | redundancy | 20 | 72 | 0.81 | 2.62 | [2.49, 2.76] | 2.70 | 2.65 |
| M5 | profile_fit | 20 | 72 | 0.50 | 2.65 | [2.48, 2.82] | 2.65 | 2.33 |
| M5 | material_fidelity | 20 | 72 | 0.15 | 2.79 | [2.61, 2.96] | 2.80 | 2.59 |
| M5 | sim.goal_fidelity | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.95 |
| M5 | sim.coherence | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.98 |
| M5 | sim.allowed_information | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| M5 | sim.no_invention | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| M5 | sim.correct_confirmations | 14 | 49 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.99 |
| S1 | administrative | 20 | 72 | 0.33 | 2.71 | [2.55, 2.88] | 2.65 | 2.65 |
| S1 | continuity | 17 | 64 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.86 |
| S1 | clarity | 20 | 72 | 0.61 | 2.84 | [2.70, 2.98] | 2.85 | 2.86 |
| S1 | redundancy | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.90 |
| S1 | profile_fit | 20 | 72 | 0.38 | 2.36 | [2.21, 2.51] | 2.30 | 2.30 |
| S1 | material_fidelity | 20 | 72 | 0.47 | 2.74 | [2.56, 2.91] | 2.70 | 2.68 |
| S1 | sim.goal_fidelity | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.95 |
| S1 | sim.coherence | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| S1 | sim.allowed_information | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| S1 | sim.no_invention | 20 | 72 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 3.00 |
| S1 | sim.correct_confirmations | 17 | 50 | 0.00 | 3.00 | [3.00, 3.00] | 3.00 | 2.96 |
