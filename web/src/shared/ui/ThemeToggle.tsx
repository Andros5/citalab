import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { tx } from "../../i18n";

// Mismo nombre de clave que el script de index.html, que fija el tema antes de
// pintar para evitar un destello claro al abrir el portal en modo oscuro.
const STORAGE_KEY = "citalab.theme";
type Theme = "light" | "dark";

function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(currentTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  const toDark = theme !== "dark";
  const next: Theme = toDark ? "dark" : "light";
  const label = toDark ? tx("Activar tema oscuro") : tx("Activar tema claro");
  return (
    <button
      type="button"
      className="icon-button theme-toggle"
      aria-label={label}
      title={label}
      onClick={() => {
        setTheme(next);
        try {
          localStorage.setItem(STORAGE_KEY, next);
        } catch {
          // Sin almacenamiento (modo privado): el tema solo dura esta visita.
        }
      }}
    >
      {toDark ? <Moon size={17} /> : <Sun size={17} />}
    </button>
  );
}
