import { describe, expect, it } from "vitest";
import { agendaDate } from "./api";

describe("Fecha civil de la agenda sanitaria", () => {
  it.each([
    ["2026-09-05T23:30:00Z", "2026-09-06"],
    ["2026-09-06T00:30:00+03:00", "2026-09-05"],
    ["2026-01-05T23:30:00Z", "2026-01-06"],
    ["2026-03-29T01:30:00Z", "2026-03-29"],
  ])("agrupa %s por su día en Madrid", (instant, day) => {
    expect(agendaDate(instant)).toBe(day);
  });
});
