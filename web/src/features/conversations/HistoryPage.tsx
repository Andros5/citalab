import { Archive, ArrowRight, Filter, RefreshCw, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, dateTime, statusLabels } from "../../api";
import {
  Empty,
  ErrorState,
  Loading,
  Notice,
  PageHeader,
  Status,
} from "../../components";
import { useApp } from "../../context";
import { formatNumber, tx } from "../../i18n";

import { ExportButton } from "../../shared/ui/ExportButton";
import { useConversationSearch } from "./useConversationSearch";

export function HistoryPage() {
  const { bootstrap, notify } = useApp();
  const staff = bootstrap.user.role !== "patient";
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get("q") || "";
  const architecture = searchParams.get("architecture") || "";
  const status = searchParams.get("status") || "";
  const {
    items,
    setItems,
    total,
    error,
    loading,
    hasMore,
    retry,
    refresh,
    loadMore,
  } = useConversationSearch(q, staff ? architecture : "", status);
  const sentinel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (
      !hasMore ||
      loading ||
      error ||
      !sentinel.current ||
      typeof IntersectionObserver === "undefined"
    )
      return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadMore();
      },
      { rootMargin: "400px 0px" },
    );
    observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [hasMore, loading, error, loadMore]);
  const filter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    next.set(key, value);
    next.delete("page");
    setSearchParams(next, { replace: true });
  };
  const setQ = (value: string) => filter("q", value);
  const setArchitecture = (value: string) => filter("architecture", value);
  const [archiving, setArchiving] = useState<string[]>([]);
  const [actionError, setActionError] = useState("");
  return (
    <div className="history-page">
      <PageHeader
        eyebrow="TRABAJO DIARIO / TRAZABILIDAD"
        title="Historial de conversaciones"
        description="Recupera una sesión, revisa sus decisiones y conserva evidencia de lo que realmente ocurrió."
      />
      {actionError && <Notice tone="error">{actionError}</Notice>}
      <section
        className="panel history-filters"
        aria-label="Filtros de conversaciones"
      >
        <div className="history-filter-heading">
          <h2>
            <Filter size={20} aria-hidden="true" /> Filtros
          </h2>
          <span className="muted">
            {staff
              ? tx("Vista del equipo investigador")
              : tx("Mis conversaciones")}
          </span>
        </div>
        <div className="history-filter-fields">
          <label className="history-search-field">
            <span>Búsqueda</span>
            <span className="search">
              <Search size={17} />
              <input
                aria-label="Buscar conversaciones"
                placeholder="Buscar por petición, perfil o identificador…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </span>
          </label>
          {staff && (
            <label>
              <span>Arquitectura</span>
              <select
                aria-label="Filtrar por arquitectura"
                value={architecture}
                onChange={(e) => setArchitecture(e.target.value)}
              >
                <option value="">Todas las arquitecturas</option>
                {["M5", "S1", "H"].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            <span>Estado</span>
            <select
              aria-label="Filtrar por estado"
              value={status}
              onChange={(e) => filter("status", e.target.value)}
            >
              <option value="">Todos los estados</option>
              {[
                "READY",
                "NEEDS_CONFIRMATION",
                "NEEDS_CLARIFICATION",
                "COMPLETED",
                "BLOCKED",
                "FAILED",
                "ESCALATED",
                "DISCARDED",
                "RESTORED_DATA",
                "SCENARIO_UPDATED",
              ].map((value) => (
                <option key={value} value={value}>
                  {tx(statusLabels[value])}
                </option>
              ))}
            </select>
          </label>
          <button className="secondary" onClick={refresh} disabled={loading}>
            <RefreshCw size={16} aria-hidden="true" /> Actualizar
          </button>
        </div>
      </section>
      <div className="history-summary">
        <span>
          {loading && !items.length
            ? tx("Consultando…")
            : `${formatNumber(total)} ${total === 1 ? tx("conversación") : tx("conversaciones")}`}
        </span>
        <small>
          Más recientes primero · las filas se cargan al desplazarse
        </small>
      </div>
      <section
        className="panel history-results"
        aria-label="Resultados de conversaciones"
        aria-busy={loading}
      >
        {loading && !items.length ? (
          <Loading />
        ) : !items.length && error ? null : !items.length ? (
          <Empty title="No hay conversaciones en esta vista">
            Inicia una sesión en el asistente o cambia los filtros. Aquí no se
            muestran métricas inventadas.
          </Empty>
        ) : (
          <div className="table-scroll responsive-table">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Conversación</th>
                  <th>Perfil</th>
                  <th>Arquitectura</th>
                  <th>Estado</th>
                  <th>Actividad</th>
                  <th>Creación</th>
                  {staff && <th>Consumo</th>}
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td data-label="ID">
                      <code className="history-id" title={item.id}>
                        {item.id.slice(0, 8)}…
                      </code>
                    </td>
                    <td data-label="Conversación">
                      <Link
                        className="table-title"
                        to={`/asistente/${item.id}`}
                      >
                        {item.title}
                      </Link>
                      {item.archived && <small>{tx("Archivada")}</small>}
                    </td>
                    <td data-label="Perfil">{item.subject_name}</td>
                    <td data-label="Arquitectura">
                      <span className="architecture-tag">
                        {item.architecture}
                      </span>
                      <small>{item.provider}</small>
                    </td>
                    <td data-label="Estado">
                      <Status value={item.status} />
                    </td>
                    <td data-label="Actividad">
                      {dateTime(item.updated_at)}
                      <small>
                        {item.turn_count}{" "}
                        {item.turn_count === 1 ? tx("turno") : tx("turnos")}
                      </small>
                    </td>
                    <td data-label="Creación">{dateTime(item.created_at)}</td>
                    {staff && (
                      <td data-label="Consumo">
                        {item.provider === "offline" ||
                        item.architecture === "D0"
                          ? "Sin API remota"
                          : item.total_known_tokens == null ||
                              (!item.tokens_complete &&
                                item.total_known_tokens === 0)
                            ? "No disponible"
                            : formatNumber(item.total_known_tokens)}
                        <small>
                          {item.provider === "offline" ||
                          item.architecture === "D0"
                            ? "No mide consumo de LLM"
                            : item.tokens_complete
                              ? "tokens conocidos"
                              : "tokens · medida parcial"}
                        </small>
                      </td>
                    )}
                    <td data-label="Acciones">
                      <div className="actions">
                        <Link
                          className="icon-button"
                          aria-label={`Abrir ${item.title}`}
                          to={`/asistente/${item.id}`}
                        >
                          <ArrowRight size={17} />
                        </Link>
                        {staff && (
                          <ExportButton
                            path={`/conversations/${item.id}/export`}
                            filename={`conversation-${item.id}.json`}
                            label={`Exportar ${item.title}`}
                            iconOnly
                          />
                        )}
                        <button
                          className="icon-button"
                          aria-label={`Archivar ${item.title}`}
                          title={item.archived ? tx("Archivada") : tx("Archivar")}
                          disabled={
                            archiving.includes(item.id) ||
                            item.archived ||
                            !!item.active_job ||
                            item.read_only
                          }
                          onClick={async () => {
                            setArchiving((current) => [...current, item.id]);
                            setActionError("");
                            try {
                              await api(
                                `/conversations/${item.id}/archive`,
                                "POST",
                              );
                              setItems((current) =>
                                current.map((value) =>
                                  value.id === item.id
                                    ? { ...value, archived: true }
                                    : value,
                                ),
                              );
                              notify(
                                "Conversación archivada; su evidencia se conserva.",
                              );
                            } catch (e) {
                              setActionError((e as Error).message);
                            } finally {
                              setArchiving((current) =>
                                current.filter((id) => id !== item.id),
                              );
                            }
                          }}
                        >
                          <Archive size={17} aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {error && <ErrorState message={error} retry={retry} />}
        <div ref={sentinel} className="history-load-more">
          <span role="status" aria-live="polite">
            {loading
              ? tx("Cargando conversaciones…")
              : `${formatNumber(items.length)} ${tx("de")} ${formatNumber(total)} ${tx("conversaciones cargadas")}`}
          </span>
          {hasMore && !error && (
            <button onClick={loadMore} disabled={loading}>
              Cargar más conversaciones
            </button>
          )}
          {!hasMore && !loading && !error && !!items.length && (
            <small>Has llegado al final de esta vista.</small>
          )}
        </div>
      </section>
      {staff && (
        <p className="muted history-footnote">
          Los tokens ausentes se identifican como medida parcial.
        </p>
      )}
    </div>
  );
}
