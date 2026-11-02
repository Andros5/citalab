# Interfaz de CitaLab

React y TypeScript con Vite. Estilos propios, sin fuentes remotas ni analítica.

```bash
pnpm install --frozen-lockfile
pnpm test           # pruebas de la interfaz
pnpm build          # genera web/dist, que sirve el portal en http://127.0.0.1:8765
pnpm dev            # desarrollo, con el portal arrancado en el puerto 8765
```

- `src/api.ts` es la única puerta HTTP y gestiona la sesión y los errores.
- `src/features/` agrupa las pantallas: conversación, agenda, perfiles, administración, ayuda,
  inspector de turnos y evaluación.
- `src/i18n.tsx` traduce la interfaz al inglés. `pnpm run i18n:check` comprueba que no falte
  ningún texto.
- `public/architecture/` contiene los diagramas de arquitectura de la ayuda, generados con
  Archify (licencia MIT en `public/architecture/LICENSE.txt`).

El servidor decide siempre los permisos y el estado. La interfaz solo presenta lo que recibe.
