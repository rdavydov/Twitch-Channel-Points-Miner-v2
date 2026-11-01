import { useEffect, useState } from "react";

export const number = (v: unknown) =>
  typeof v === "number" && Number.isFinite(v)
    ? new Intl.NumberFormat("en-US").format(v)
    : "Unknown";
export const signed = (v: number | null | undefined) =>
  typeof v === "number" ? (v > 0 ? "+" : "") + number(v) : "Unknown";
export function date(
  v: number | string | null | undefined,
  timezone = "Europe/Budapest",
) {
  if (!v) return "Not available";
  const value = new Date(typeof v === "number" ? v * 1000 : v);
  return Number.isNaN(value.getTime())
    ? "Not available"
    : new Intl.DateTimeFormat("en-GB", {
        timeZone: timezone,
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
      }).format(value);
}
export function duration(seconds: number) {
  seconds = Math.max(0, Math.floor(seconds));
  if (seconds < 60) return seconds + "s";
  if (seconds < 3600)
    return Math.floor(seconds / 60) + "m " + (seconds % 60) + "s";
  if (seconds < 86400)
    return (
      Math.floor(seconds / 3600) +
      "h " +
      Math.floor((seconds % 3600) / 60) +
      "m"
    );
  return (
    Math.floor(seconds / 86400) +
    "d " +
    Math.floor((seconds % 86400) / 3600) +
    "h"
  );
}
export const label = (value: string) =>
  value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (c) => c.toUpperCase());
export function inputDate(epoch: number, timezone = "Europe/Budapest") {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(epoch * 1000));
  const value = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  return `${value.year}-${value.month}-${value.day}`;
}
export function dayBoundary(
  value: string,
  timezone = "Europe/Budapest",
  end = false,
) {
  const [year, month, day] = value.split("-").map(Number);
  const wanted = Date.UTC(year, month - 1, day + (end ? 1 : 0));
  let guess = wanted;
  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  for (let i = 0; i < 3; i++) {
    const p = Object.fromEntries(
      formatter
        .formatToParts(new Date(guess))
        .map((p) => [p.type, Number(p.value)]),
    );
    guess +=
      wanted - Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  }
  return guess / 1000 - (end ? 1 : 0);
}
export function csvCell(v: unknown): string {
  let text =
    v == null ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
  if (typeof v === "string" && /^[\s]*[=+@-]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"', '""') + '"';
}
export function downloadCSV(
  name: string,
  headers: string[],
  rows: unknown[][],
) {
  const content =
    "\uFEFF" +
    [headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(
    new Blob([content], { type: "text/csv;charset=utf-8" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api/v1/" + path, {
    ...init,
    cache: "no-store",
  });
  if (!response.ok)
    throw new Error(
      response.status === 403
        ? "Session expired. Reload this page."
        : `Request failed (${response.status})`,
    );
  return response.json();
}
export function usePreference<T>(key: string, initial: T) {
  const [value, set] = useState<T>(() => {
    try {
      return JSON.parse(localStorage.getItem(key) || "null") ?? initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* Private storage can be unavailable. */
    }
  }, [key, value]);
  return [value, set] as const;
}
export function useNow() {
  const [now, set] = useState(Date.now() / 1000);
  useEffect(() => {
    const id = setInterval(() => set(Date.now() / 1000), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}
