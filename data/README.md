# Datos

Todos los datos son sintéticos. No proceden de registros sanitarios ni describen a personas
reales.

| Fichero | Contenido |
|---|---|
| `evaluation/independent-final-v1.json` | Corpus de la campaña final: agenda, perfiles de persona, 46 condiciones y contrastes. Lo genera `scripts/prepare_independent_corpus.py` |
| `evaluation/scenarios.json` | Corpus de desarrollo, con el que se ajustó el asistente. Las pruebas automáticas lo usan por defecto |
| `synthetic/profiles/sprint3_profiles.json` | 50 perfiles sintéticos de preferencias (franja horaria, modalidad, centro, idioma, nivel de detalle, tratamiento y canal de recordatorio), con procedencia y finalidad de cada atributo |

El corpus final y el fichero de perfiles se publican byte a byte, porque el manifiesto de la
campaña fija su hash.

Licencia: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.es).
