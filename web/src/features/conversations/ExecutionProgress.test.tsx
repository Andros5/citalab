import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Call, Job } from "../../api";
import { ExecutionProgress } from "./ExecutionProgress";

afterEach(() => vi.useRealTimers());

it("conserva el fallo y muestra la espera hasta que empieza el intento siguiente", () => {
  const first = {id: "first", agent: "context", status: "error", latency_ms: 100,
    started_at: new Date().toISOString(), logical_inference_id: "same", attempt_index: 1,
    max_attempts: 3, retry_scheduled: true, retry_delay_seconds: 0.5} as Call;
  const {rerender} = render(<ExecutionProgress calls={[first]} job={null} />);
  expect(screen.getByText("Intento 1/3")).toBeInTheDocument();
  expect(screen.getByText("Esperando antes de reintentar: 0.5 s")).toBeInTheDocument();
  rerender(<ExecutionProgress calls={[first, {...first, id: "second", status: "success",
    attempt_index: 2, retry_scheduled: false}]} job={null} />);
  expect(screen.getByText("Error")).toBeInTheDocument();
  expect(screen.getByText("Intento 2/3")).toBeInTheDocument();
  expect(screen.queryByText(/Esperando antes/)).not.toBeInTheDocument();
});

it("actualiza el tiempo local y conserva llamadas completadas mientras empieza otra", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-13T10:00:10Z"));
  const base = { id: "a", agent: "context", status: "running", started_at: "2026-10-13T10:00:00Z" } as Call;
  const job = { at: "2026-10-13T10:00:00Z" } as Job;
  const { rerender, unmount } = render(<ExecutionProgress calls={[base]} job={job} />);
  expect(screen.getByText("10.0 s")).toBeInTheDocument();
  act(() => vi.advanceTimersByTime(3000));
  expect(screen.getByText("13.0 s")).toBeInTheDocument();
  rerender(<ExecutionProgress calls={[
    { ...base, status: "success", latency_ms: 12000 },
    { ...base, id: "b", agent: "personalization", started_at: "2026-10-13T10:00:12Z" },
  ]} job={job} />);
  expect(screen.getByText("12.0 s")).toBeInTheDocument();
  expect(screen.getByText("1.0 s")).toBeInTheDocument();
  expect(screen.getByText("Contexto")).toBeInTheDocument();
  expect(screen.getByText("Personalización")).toBeInTheDocument();
  rerender(<ExecutionProgress calls={[
    { ...base, status: "success", latency_ms: 12000 },
    { ...base, id: "b", agent: "personalization", status: "error", latency_ms: 1000 },
    { ...base, id: "c", agent: "orchestration", status: "queued", started_at: "" },
  ]} job={job} />);
  expect(screen.getByText("Error")).toBeInTheDocument();
  expect(screen.getByText("En cola")).toBeInTheDocument();
  expect(screen.getByText("Latencia n/d")).toBeInTheDocument();
  expect(screen.getByText("12.0 s")).toBeInTheDocument();
  unmount();
  expect(vi.getTimerCount()).toBe(0);
});
