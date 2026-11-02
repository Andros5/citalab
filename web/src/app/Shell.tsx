import {
  CalendarDays,
  ChevronRight,
  FlaskConical,
  History,
  LifeBuoy,
  LogOut,
  Menu,
  MessageSquare,
  Settings2,
  X,
} from "lucide-react";
import React, { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import type { Bootstrap } from "../api";
import { Modal, Skeleton } from "../components";
import { AppContext } from "../context";
import {
  SessionDraftProvider,
  useConfirmSessionExit,
} from "../shared/hooks/sessionDrafts";
import { useAnnouncement } from "../shared/hooks/useAnnouncement";
import { Brand } from "../shared/ui/Brand";
import { ThemeToggle } from "../shared/ui/ThemeToggle";
import { ErrorBoundary } from "./ErrorBoundary";
import { LanguageSelect, tx } from "../i18n";

// Las áreas pesadas se descargan al entrar; Suspense conserva un estado de carga
// común y ErrorBoundary aísla el fallo de una sección del resto del portal.
const ChatPage = lazy(() =>
  import("../features/conversations/ChatPage").then((m) => ({
    default: m.ChatPage,
  })),
);
const HistoryPage = lazy(() =>
  import("../features/conversations/HistoryPage").then((m) => ({
    default: m.HistoryPage,
  })),
);
const DataPage = lazy(() =>
  import("../pages/data").then((m) => ({ default: m.DataPage })),
);
const AdminPage = lazy(() =>
  import("../features/administration/AdminPage").then((m) => ({
    default: m.AdminPage,
  })),
);
const ExperimentPage = lazy(() =>
  import("../features/experiments/EvaluationPage").then((m) => ({
    default: m.EvaluationPage,
  })),
);
const HelpPage = lazy(() =>
  import("../features/help/HelpPage").then((m) => ({ default: m.HelpPage })),
);

export function Shell({
  bootstrap,
  refresh,
  logout,
}: {
  bootstrap: Bootstrap;
  refresh: () => Promise<void>;
  logout: () => void;
}) {
  return (
    <SessionDraftProvider>
      <ShellContent bootstrap={bootstrap} refresh={refresh} logout={logout} />
    </SessionDraftProvider>
  );
}

function ShellContent({
  bootstrap,
  refresh,
  logout,
}: {
  bootstrap: Bootstrap;
  refresh: () => Promise<void>;
  logout: () => void;
}) {
  const [menu, setMenu] = useState(false);
  const confirmExit = useConfirmSessionExit();
  const { message, notify, dismiss, setPaused } = useAnnouncement();
  const location = useLocation();
  const staff = bootstrap.user.role !== "patient";
  useEffect(() => {
    setMenu(false);
    document
      .querySelector<HTMLElement>("#main")
      ?.focus({ preventScroll: true });
  }, [location.pathname]);
  useEffect(() => {
    const wide = window.matchMedia("(min-width: 48rem)");
    const closeOnWide = () => {
      if (wide.matches) setMenu(false);
    };
    wide.addEventListener("change", closeOnWide);
    return () => wide.removeEventListener("change", closeOnWide);
  }, []);
  const links = [
    {
      to: "/asistente",
      label: tx("Asistente"),
      icon: MessageSquare,
      group: "TRABAJO DIARIO",
    },
    { to: "/conversaciones", label: tx("Conversaciones"), icon: History },
    {
      to: "/datos",
      label: staff ? tx("Agenda y datos") : tx("Mi agenda"),
      icon: CalendarDays,
    },
    ...(staff
      ? [
          {
            to: "/experimentos",
            label: tx("Evaluación"),
            icon: FlaskConical,
            group: "LABORATORIO",
          },
          { to: "/administracion", label: tx("Administración"), icon: Settings2 },
        ]
      : []),
    {
      to: "/ayuda",
      label: tx("Guía del entorno"),
      icon: LifeBuoy,
      group: "RECURSOS",
    },
  ];
  const context = useMemo(
    () => ({ bootstrap, refresh, notify }),
    [bootstrap, refresh, notify],
  );
  const navigation = (
    <>
      <nav aria-label="Navegación principal">
        {links.map(({ to, label, icon: Icon, group }) => (
          <React.Fragment key={to}>
              {group && <p className="nav-group">{tx(group)}</p>}
            <NavLink to={to}>
              <Icon size={19} />
              <span>{tx(label)}</span>
            </NavLink>
          </React.Fragment>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="user-card">
          <span className="avatar">
            {bootstrap.user.display_name.slice(0, 2).toUpperCase()}
          </span>
          <span>
            <strong>{bootstrap.user.display_name}</strong>
            <small>
              {bootstrap.user.role === "admin"
                ? tx("Administración e investigación")
                : bootstrap.user.role === "researcher"
                  ? tx("Revisión e investigación")
                  : tx("Paciente sintético")}
            </small>
          </span>
        </div>
        <button
          className="text-button"
          onClick={() => {
            if (confirmExit()) logout();
          }}
        >
          <LogOut size={16} /> Cerrar sesión
        </button>
        <p>Sin afiliación al SAS o a la Junta de Andalucía.</p>
      </div>
    </>
  );
  return (
    <AppContext.Provider value={context}>
      <a className="skip-link" href="#main">
        Saltar al contenido
      </a>
      <div className="shell">
        <header className="topbar">
          <div className="mobile-brand">
            <Brand />
          </div>
          <button
            className="icon-button menu-toggle"
            aria-label={menu ? "Cerrar navegación" : "Abrir navegación"}
            aria-expanded={menu}
            aria-controls={menu ? "mobile-navigation" : undefined}
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X /> : <Menu />}
          </button>
          <div className="breadcrumb">
            CitaLab <ChevronRight size={14} />{" "}
            <strong>
              {tx(links.find((link) => location.pathname.startsWith(link.to))
                ?.label || "Laboratorio")}
            </strong>
          </div>
          <div className="topbar-right">
            <ThemeToggle />
            <LanguageSelect />
            <span className="academic-label">PROTOTIPO ACADÉMICO</span>
            <span className="environment">
              <i />
              Local · Sintético
            </span>
            <span className="avatar" title={bootstrap.user.display_name}>
              {bootstrap.user.display_name.slice(0, 2).toUpperCase()}
            </span>
          </div>
        </header>
        <aside className="sidebar">
          <Brand />
          {navigation}
        </aside>
        {menu && (
          <Modal
            title="Navegación"
            dialogId="mobile-navigation"
            className="navigation-dialog"
            close={() => setMenu(false)}
          >
            {navigation}
          </Modal>
        )}
        <main id="main" className="workspace" tabIndex={-1}>
          <div
            className="sr-only"
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            {tx(message)}
          </div>
          {message && (
            <div
              className="toast"
              onMouseEnter={() => setPaused(true)}
              onMouseLeave={() => setPaused(false)}
              onFocus={() => setPaused(true)}
              onBlur={() => setPaused(false)}
            >
              {tx(message)}
              <button aria-label="Cerrar aviso" onClick={dismiss}>
                <X size={16} />
              </button>
            </div>
          )}
          <ErrorBoundary key={location.pathname}>
            <Suspense fallback={<Skeleton label="Abriendo sección…" />}>
              <Routes>
                <Route path="/asistente" element={<ChatPage />} />
                <Route path="/asistente/:id" element={<ChatPage />} />
                <Route path="/conversaciones" element={<HistoryPage />} />
                <Route path="/datos" element={<DataPage />} />
                <Route
                  path="/experimentos"
                  element={
                    staff ? <ExperimentPage /> : <Navigate to="/asistente" />
                  }
                />
                <Route
                  path="/administracion"
                  element={staff ? <AdminPage /> : <Navigate to="/asistente" />}
                />
                <Route path="/ayuda" element={<HelpPage />} />
                <Route
                  path="*"
                  element={<Navigate to="/asistente" replace />}
                />
              </Routes>
            </Suspense>
          </ErrorBoundary>
          <footer className="workspace-footer">
            <span>CitaLab · TFM</span>
            <span>
              Solo gestión administrativa · Sin triaje · Sin citas reales
            </span>
          </footer>
        </main>
      </div>
    </AppContext.Provider>
  );
}
