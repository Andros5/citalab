# Resultados de la campaña `final-independent-v1`

Episodios registrados: 276 · completados: 276

| Proveedor | Arq. | N | Éxito (IC95 %) | Objetivo | Seguridad | Preferencia | Llamadas | Tokens | Latencia LLM (s) | Fallbacks/ep | Incid. |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| google | M5 | 46 | 93 % (82 %–98 %) | 96 % | 100 % | 100 % | 8.3 | 8286 | 9.9 | 0.00 | 0 |
| google | S1 | 46 | 100 % (92 %–100 %) | 100 % | 100 % | 100 % | 3.8 | 7486 | 3.9 | 0.30 | 0 |
| google | H | 46 | 93 % (82 %–98 %) | 96 % | 100 % | 100 % | 3.8 | 3447 | 3.9 | 0.04 | 0 |
| groq | M5 | 46 | 93 % (82 %–98 %) | 93 % | 100 % | 60 % | 8.8 | 10831 | 4.5 | 0.26 | 0 |
| groq | S1 | 46 | 91 % (80 %–97 %) | 93 % | 100 % | 60 % | 4.1 | 6534 | 1.4 | 0.26 | 0 |
| groq | H | 46 | 93 % (82 %–98 %) | 96 % | 100 % | 40 % | 3.8 | 4531 | 1.7 | 0.20 | 0 |

## Éxito por gestión

| Proveedor | Arq. | book | query | reschedule | cancel | reminder |
|---|---|---:|---:|---:|---:|---:|
| google | M5 | 100 % | 90 % | 89 % | 88 % | 100 % |
| google | S1 | 100 % | 100 % | 100 % | 100 % | 100 % |
| google | H | 100 % | 90 % | 78 % | 100 % | 100 % |
| groq | M5 | 100 % | 100 % | 78 % | 100 % | 89 % |
| groq | S1 | 100 % | 90 % | 78 % | 100 % | 89 % |
| groq | H | 100 % | 90 % | 78 % | 100 % | 100 % |

## Contrastes pareados (diferencia de éxito, bootstrap por familia, Holm)

| Proveedor | Contraste | Unidades | Diferencia | IC95 % | p | p Holm |
|---|---|---:|---:|---|---:|---:|
| google | M5-S1 | 46 | -6.5 pp | [-15.2, +0.0] | 0.122 | 0.365 |
| google | M5-H | 46 | +0.0 pp | [-6.5, +6.5] | 1.000 | 1.000 |
| google | S1-H | 46 | +6.5 pp | [+0.0, +15.2] | 0.123 | 0.365 |
| groq | M5-S1 | 46 | +2.2 pp | [-4.3, +8.7] | 0.754 | 1.000 |
| groq | M5-H | 46 | +0.0 pp | [-6.5, +6.5] | 1.000 | 1.000 |
| groq | S1-H | 46 | -2.2 pp | [-6.5, +0.0] | 0.621 | 1.000 |

## Sensibilidad: contraste agrupado por los cinco grupos aprobados (cambio de signo exacto)

| Proveedor | Contraste | Grupos | Diferencia | IC95 % | p | p Holm |
|---|---|---:|---:|---|---:|---:|
| google | M5-S1 | 5 | -5.1 pp | [-10.8, +0.0] | 0.5000 | 1.0000 |
| google | M5-H | 5 | +0.6 pp | [-6.7, +8.6] | 1.0000 | 1.0000 |
| google | S1-H | 5 | +5.7 pp | [+0.0, +17.1] | 1.0000 | 1.0000 |
| groq | M5-S1 | 5 | +0.3 pp | [-6.7, +7.5] | 1.0000 | 1.0000 |
| groq | M5-H | 5 | -2.2 pp | [-6.7, +0.0] | 1.0000 | 1.0000 |
| groq | S1-H | 5 | -2.5 pp | [-7.5, +0.0] | 1.0000 | 1.0000 |

## Éxito por bloque

| Configuración | primary | repeat-2 | counterfactual | persona | supplement |
|---|---:|---:|---:|---:|---:|
| groq:M5 | 92 % | 100 % | 80 % | 100 % | 100 % |
| groq:S1 | 92 % | 100 % | 80 % | 100 % | 80 % |
| groq:H | 96 % | 100 % | 80 % | 100 % | 80 % |
| google:M5 | 96 % | 100 % | 80 % | 100 % | 80 % |
| google:S1 | 100 % | 100 % | 100 % | 100 % | 100 % |
| google:H | 96 % | 100 % | 80 % | 100 % | 80 % |

## Episodios no satisfactorios

- **N-C05**: google:M5:goal
- **N-CF-R02**: groq:M5:goal, groq:S1:goal, groq:H:goal, google:M5:goal, google:H:goal
- **N-M02**: groq:S1:goal
- **N-M04**: groq:M5:goal
- **N-R02**: groq:M5:goal, groq:S1:goal, groq:H:goal, google:H:goal
- **N-SUP-Q**: groq:S1:response, groq:H:response, google:M5:response, google:H:response

Motivos de fallback: {'writer-check': 22, 'single-check': 26, 'orchestration-rejected': 1}

Validez del usuario simulado por configuración: google:M5 96 %, google:S1 96 %, google:H 96 %, groq:M5 96 %, groq:S1 100 %, groq:H 96 %
