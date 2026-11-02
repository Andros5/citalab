# Memoria

[memoria-tfm.pdf](memoria-tfm.pdf) es la memoria entregada. Esta carpeta contiene también sus
fuentes LaTeX.

| Carpeta | Contenido |
|---|---|
| `main.tex` | Documento principal |
| `config/` | Paquetes, metadatos de la portada y estilo |
| `frontmatter/` | Portada, resumen, abstract, declaración de uso de IA generativa y acrónimos |
| `chapters/` | Los diez capítulos |
| `appendices/` | Apéndices A y B |
| `generated/` | Tablas y figuras de los capítulos 8 y 9, generadas desde los resultados de la campaña |
| `bibliography/` | Referencias (estilo APA 7) |

Para regenerar las tablas y compilar:

```bash
python scripts/reproduce.py      # regenera memoria/generated y comprueba que no cambia nada
python scripts/build_thesis.py   # memoria/build/main.pdf
```

Licencia: [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/deed.es). El
logotipo de la Universidad de Sevilla (`assets/logos/`) pertenece a la universidad y no está
incluido en esta licencia.
