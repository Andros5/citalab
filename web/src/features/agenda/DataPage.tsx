import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Database,
  Plus,
  Search,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  agendaDate,
  agendaDateLabel,
  dateTime,
  type Catalog,
  type Resource,
  type Resources,
} from "../../api";
import {
  Empty,
  ErrorState,
  JsonBlock,
  PageHeader,
  Skeleton,
  Status,
  Tabs,
} from "../../components";
import { useApp } from "../../context";
import { formatDate, formatNumber, tx, weekdayLabels } from "../../i18n";
import { useResource } from "../../shared/hooks/useResource";
import {
  agendaTime,
  serviceLabel,
} from "../../shared/lib/resourceLabels";
import { ExportButton } from "../../shared/ui/ExportButton";
import { ProfilePanel } from "../profiles/ProfilePanel";
import {
  indexSlotsByDay,
  selectActiveSlots,
  selectAppointments,
  selectSlots,
  selectVisibleSlots,
} from "./agendaSelectors";
import { AppointmentDialog } from "./AppointmentDialog";
import { SlotDialog } from "./SlotDialog";

function isResources(value: unknown): value is Resources {
  return (
    !!value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.values(value).every(
      (collection) =>
        !!collection &&
        typeof collection === "object" &&
        !Array.isArray(collection) &&
        Object.values(collection).every(
          (resource) =>
            !!resource && typeof (resource as Resource).id === "string",
        ),
    )
  );
}

export function DataPage() {
  const { bootstrap, notify } = useApp();
  const admin = bootstrap.user.role === "admin";
  const staff = bootstrap.user.role !== "patient";
  const [tab, setTab] = useState("calendar");
  // La agenda completa solo es legible para el equipo; un paciente ve su propia vista.
  const resourceQuery = useResource<Resources>(staff ? "/resources" : null, isResources);
  const catalogQuery = useResource<Catalog>(staff ? "/catalog" : null);
  const catalog = catalogQuery.data;
  const resources = resourceQuery.data;
  const refresh = resourceQuery.retry;
  const [month, setMonth] = useState("");
  const [day, setDay] = useState("");
  const [availability, setAvailability] = useState("");
  const [service, setService] = useState("");
  const [schedule, setSchedule] = useState("");
  const [slotDialog, setSlotDialog] = useState<Resource | null | undefined>(
    undefined,
  );
  const [appointment, setAppointment] = useState<Resource | null>(null);
  const [resourceType, setResourceType] = useState("Slot");
  const [resourceId, setResourceId] = useState("");
  const [search, setSearch] = useState("");
  // El primer mes disponible solo inicializa la vista; no pisa la navegación del usuario.
  useEffect(() => {
    if (resources)
      setMonth(
        (current) =>
          current ||
          agendaDate(
            Object.values(resources.Slot || {})[0]?.start ||
              new Date().toISOString(),
          ).slice(0, 7),
      );
  }, [resources]);
  const allSlots = useMemo(() => selectActiveSlots(resources), [resources]);
  const slots = useMemo(
    () =>
      selectSlots(allSlots, {
        service,
        schedule,
        availability,
      }),
    [allSlots, service, schedule, availability],
  );
  const slotsByDay = useMemo(() => indexSlotsByDay(slots), [slots]);
  const visibleSlots = useMemo(
    () => selectVisibleSlots(slots, day || month, availability),
    [slots, day, month, availability],
  );
  const appointments = useMemo(
    () => selectAppointments(resources, service, schedule),
    [resources, service, schedule],
  );
  const firstDate = new Date(`${month || "2026-09"}-01T12:00:00`);
  const monthDays = new Date(
    firstDate.getFullYear(),
    firstDate.getMonth() + 1,
    0,
  ).getDate();
  const offset = (firstDate.getDay() + 6) % 7;
  const moveMonth = (step: number) => {
    const next = new Date(
      firstDate.getFullYear(),
      firstDate.getMonth() + step,
      1,
      12,
    );
    setMonth(
      `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`,
    );
    setDay("");
  };
  if (!staff) return <PatientAgenda />;
  return (
    <>
      <PageHeader
        eyebrow="FUENTE DE VERDAD / SIMULADOR"
        title={staff ? "Agenda y datos" : "Mi agenda"}
        description="Disponibilidad, citas y preferencias sintéticas. Las modificaciones se validan y quedan registradas."
        actions={
          staff && (
            <ExportButton
              path="/fhir/export"
              filename="citalab-fhir.json"
              label="Exportar FHIR"
            />
          )
        }
      />
      <Tabs
        label="Vistas de agenda y datos"
        value={tab}
        onChange={setTab}
        items={[
          { value: "calendar", label: "Calendario y citas" },
          {
            value: "profiles",
            label: staff ? "Perfiles sintéticos" : "Mis preferencias",
          },
          ...(staff ? [{ value: "fhir", label: "Explorador FHIR" }] : []),
        ]}
      >
        {!resources ? (
          resourceQuery.error ? (
            <ErrorState
              message={resourceQuery.error}
              retry={resourceQuery.retry}
            />
          ) : (
            <Skeleton label="Cargando agenda" />
          )
        ) : tab === "calendar" ? (
          <>
            {catalogQuery.error && (
              <ErrorState
                message={catalogQuery.error}
                retry={catalogQuery.retry}
              />
            )}
            <section
              className="panel agenda-filters"
              aria-label="Selección de agenda"
            >
              <label>
                Servicio
                <select
                  value={service}
                  disabled={!catalog}
                  onChange={(e) => {
                    setService(e.target.value);
                    setSchedule("");
                    setDay("");
                  }}
                >
                  <option value="">Todos los servicios</option>
                  {catalog?.services.map((item) => (
                    <option key={item.code} value={item.code}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Agenda
                <select
                  value={schedule}
                  disabled={!catalog}
                  onChange={(e) => {
                    setSchedule(e.target.value);
                    setDay("");
                  }}
                >
                  <option value="">Todas las agendas</option>
                  {catalog?.schedules
                    .filter((item) => !service || item.service_code === service)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                        {item.active ? "" : " · Inactiva"}
                      </option>
                    ))}
                </select>
              </label>
              <p className="muted">
                {catalog
                  ? `Escenario ${catalog.scenario.id} · v${catalog.scenario.version}`
                  : "Cargando catálogo…"}
                . Estos filtros no cambian la petición del chatbot.
              </p>
            </section>
            <div className="calendar-layout">
              <section className="calendar panel">
                <header>
                  <button
                    className="icon-button"
                    aria-label="Mes anterior"
                    onClick={() => moveMonth(-1)}
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <h2>
                    {formatDate(firstDate, { month: "long", year: "numeric" })}
                  </h2>
                  <button
                    className="icon-button"
                    aria-label="Mes siguiente"
                    onClick={() => moveMonth(1)}
                  >
                    <ChevronRight size={18} />
                  </button>
                </header>
                <div className="weekdays" aria-hidden="true">
                  {weekdayLabels().map((value) => (
                    <span key={value}>{value}</span>
                  ))}
                </div>
                <div className="calendar-grid">
                  {Array.from({ length: offset }, (_, i) => (
                    <span key={`empty-${i}`} />
                  ))}
                  {Array.from({ length: monthDays }, (_, i) => {
                    const date = `${month}-${String(i + 1).padStart(2, "0")}`;
                    const count = slotsByDay.get(date) || 0;
                    return (
                      <button
                        key={date}
                        className={`${day === date ? "selected" : ""} ${count ? "has-slots" : ""}`}
                        aria-pressed={day === date}
                        aria-label={`${date}: ${formatNumber(count)} ${count === 1 ? tx("hueco") : tx("huecos")}`}
                        disabled={!count}
                        onClick={() => setDay(day === date ? "" : date)}
                      >
                        {i + 1}
                        {count > 0 && <span aria-hidden="true" />}
                      </button>
                    );
                  })}
                </div>
                <p className="calendar-legend">
                  <i /> Hay huecos en el simulador
                </p>
                <button className="text-button" onClick={() => setDay("")}>
                  Ver todo el mes
                </button>
                <div className="calendar-summary">
                  <CalendarDays size={22} />
                  <div>
                    <strong>
                      {formatNumber(
                        visibleSlots.filter((slot) => slot.status === "free")
                          .length,
                      )}{" "}
                        {visibleSlots.filter((slot) => slot.status === "free")
                          .length === 1
                        ? tx("hueco disponible")
                        : tx("huecos disponibles")}
                    </strong>
                    <small>
                      {formatNumber(
                        appointments.filter((item) => item.status === "booked")
                          .length,
                      )}{" "}
                      {appointments.filter((item) => item.status === "booked")
                        .length === 1
                        ? tx("cita reservada")
                        : tx("citas reservadas")}{" "}
                      · citas del servicio/agenda; huecos de la selección
                      visible
                    </small>
                  </div>
                </div>
              </section>
              <section className="panel slot-panel">
                <div className="section-heading">
                  <h2>
                    {day ? `${tx("Huecos del")} ${day}` : tx("Disponibilidad del mes")}
                  </h2>
                  {admin && (
                    <button onClick={() => setSlotDialog(null)}>
                      <Plus size={16} /> Añadir hueco
                    </button>
                  )}
                </div>
                <div className="toolbar">
                  <select
                    aria-label="Filtrar disponibilidad"
                    value={availability}
                    onChange={(e) => {
                      setAvailability(e.target.value);
                      setDay("");
                    }}
                  >
                    <option value="">Todos los estados</option>
                    <option value="free">Disponibles</option>
                    <option value="busy">Reservados</option>
                    <option value="busy-unavailable">No disponibles</option>
                  </select>
                  <span className="muted">
                    {formatNumber(visibleSlots.length)}{" "}
                    {visibleSlots.length === 1 ? "resultado" : "resultados"} ·
                    Europe/Madrid
                  </span>
                </div>
                {!visibleSlots.length ? (
                  <Empty title="Sin huecos en esta selección">
                    Prueba otro servicio, agenda, día o estado. No se genera
                    disponibilidad ficticia.
                  </Empty>
                ) : (
                  <div className="slot-list">
                    {visibleSlots.map((slot) => (
                      <div key={slot.id} className="slot-row">
                        <div className="slot-time">
                          <strong>
                            {agendaTime(new Date(slot.start!))}
                          </strong>
                          <span>{agendaDateLabel(slot.start!)}</span>
                        </div>
                        <div>
                          <strong>{serviceLabel(slot)}</strong>
                          {staff && (
                            <small>
                              {slot.id} · {slot.schedule?.reference}
                            </small>
                          )}
                        </div>
                        <Status value={slot.status || ""} />
                        {admin && (
                          <button
                            aria-label={`Editar hueco de ${serviceLabel(slot)} · ${slot.schedule?.reference} · ${dateTime(slot.start)}`}
                            disabled={slot.status === "busy"}
                            onClick={() => setSlotDialog(slot)}
                          >
                            Editar
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
            <section className="panel appointments">
              <div className="section-heading">
                <h2>Citas registradas</h2>
                <span className="muted">
                  {staff
                    ? `${appointments.length} ${appointments.length === 1 ? "recurso" : "recursos"} Appointment`
                    : `${appointments.length} ${appointments.length === 1 ? "cita propia" : "citas propias"}`}
                </span>
              </div>
              {!appointments.length ? (
                <Empty title="Aún no hay citas reservadas">
                  Completa una propuesta y confírmala desde el asistente. La
                  cita aparecerá aquí.
                </Empty>
              ) : (
                <div className="table-scroll responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Cita</th>
                        <th>Fecha</th>
                        <th>{staff ? "Paciente sintético" : "Paciente"}</th>
                        <th>Estado</th>
                        <th>Gestión</th>
                      </tr>
                    </thead>
                    <tbody>
                      {appointments.map((item) => (
                        <tr key={item.id}>
                          <td data-label="Cita">
                            <strong>{serviceLabel(item)}</strong>
                            {staff && (
                              <small>
                                {item.id} · versión {item.meta?.versionId}
                              </small>
                            )}
                          </td>
                          <td data-label="Fecha">{dateTime(item.start)}</td>
                          <td
                            data-label={
                              staff ? "Paciente sintético" : "Paciente"
                            }
                          >
                            {staff
                              ? item.participant
                                  ?.find((part) =>
                                    part.actor.reference.startsWith("Patient/"),
                                  )
                                  ?.actor.reference.replace("Patient/", "")
                              : bootstrap.user.display_name}
                          </td>
                          <td data-label="Estado">
                            <Status value={item.status || ""} />
                          </td>
                          <td data-label="Gestión">
                            <button
                              aria-label={`Cambiar o cancelar cita de ${serviceLabel(item)} del ${dateTime(item.start)} · ${item.id}`}
                              disabled={
                                item.status !== "booked" ||
                                bootstrap.user.role === "researcher"
                              }
                              onClick={() => setAppointment(item)}
                            >
                              Cambiar / cancelar
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        ) : tab === "profiles" ? (
          <ProfilePanel />
        ) : (
          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>Explorador de recursos FHIR</h2>
                <p className="muted">
                  Lectura estructurada del simulador. No es una conexión a un
                  HIS real.
                </p>
              </div>
            </div>
            <div className="toolbar">
              <select
                aria-label="Tipo de recurso FHIR"
                value={resourceType}
                onChange={(e) => {
                  setResourceType(e.target.value);
                  setResourceId("");
                }}
              >
                {Object.keys(resources).map((key) => (
                  <option key={key}>{key}</option>
                ))}
              </select>
              <label className="search">
                <Search size={17} />
                <input
                  aria-label="Buscar recurso"
                  placeholder="Buscar identificador…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
            </div>
            <div className="fhir-layout">
              <div className="resource-list">
                {Object.values(resources[resourceType] || {})
                  .filter((item) => item.id.includes(search))
                  .map((item) => (
                    <button
                      className={item.id === resourceId ? "selected" : ""}
                      key={item.id}
                      onClick={() => setResourceId(item.id)}
                    >
                      <Database size={16} />
                      {item.id}
                      <ChevronRight size={16} />
                    </button>
                  ))}
              </div>
              {resourceId && resources[resourceType]?.[resourceId] ? (
                <JsonBlock data={resources[resourceType][resourceId]} />
              ) : (
                <Empty title="Selecciona un recurso">
                  Podrás consultar su estructura, referencias y versión sin
                  editar JSON arbitrario.
                </Empty>
              )}
            </div>
          </section>
        )}
      </Tabs>
      {slotDialog !== undefined && resources && (
        <SlotDialog
          slot={slotDialog}
          resources={resources}
          catalog={catalog}
          initialSchedule={
            schedule ||
            catalog?.schedules.find(
              (item) => item.active && item.service_code === service,
            )?.id
          }
          close={() => setSlotDialog(undefined)}
          saved={() => {
            refresh();
            notify("Agenda sintética actualizada.");
          }}
        />
      )}
      {appointment && resources && (
        <AppointmentDialog
          appointment={appointment}
          resources={resources}
          close={() => setAppointment(null)}
          saved={() => {
            refresh();
            notify("Operación confirmada y registrada.");
          }}
        />
      )}
    </>
  );
}

function PatientAgenda() {
  const [tab, setTab] = useState("appointments");
  return (
    <>
      <PageHeader
        eyebrow="MI ESPACIO"
        title="Mi agenda"
        description="Tus citas y preferencias sintéticas. Las citas se consultan y se cambian siempre a través del asistente."
      />
      <Tabs
        label="Vistas de mi agenda"
        value={tab}
        onChange={setTab}
        items={[
          { value: "appointments", label: "Mis citas" },
          { value: "profiles", label: "Mis preferencias" },
        ]}
      >
        {tab === "appointments" ? (
          <section className="panel">
            <Empty title="Consulta tus citas con el asistente">
              Escribe «¿Qué citas tengo?» en una conversación. El asistente lee
              la agenda en ese momento y cualquier cambio te pide confirmación
              antes de aplicarse.
            </Empty>
            <p>
              <Link className="button primary" to="/asistente">
                <CalendarDays size={16} aria-hidden="true" /> Ir al asistente
              </Link>
            </p>
          </section>
        ) : (
          <ProfilePanel />
        )}
      </Tabs>
    </>
  );
}
