import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, date, number } from "./lib";
import { Empty, SectionHeading, TimeRange } from "./components";
import type { Sample } from "./types";

export function BalanceChart({
  channel,
  timezone,
}: {
  channel: string;
  timezone: string;
}) {
  const [range, setRange] = useState({
    start: Date.now() / 1000 - 7 * 86400,
    end: Date.now() / 1000,
    preset: "7",
  });
  const [rows, setRows] = useState<Sample[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    api<Sample[]>(
      `history/${encodeURIComponent(channel)}?start=${range.start}&end=${range.end}`,
      { signal: controller.signal },
    )
      .then(setRows)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [channel, range]);
  // Break lines across missing observation windows rather than imply continuous collection.
  const chartRows: {
    at: number;
    balance: number | null;
    low?: number;
    high?: number;
  }[] = [];
  rows.forEach((row, i) => {
    if (i && row.start - rows[i - 1].at > 7200)
      chartRows.push({ at: rows[i - 1].at + 1, balance: null });
    chartRows.push(row);
  });
  return (
    <section className="chart-panel">
      <SectionHeading
        title="Channel balance"
        caption="Observed balances. Prediction payouts and spending also change the balance."
      />
      <TimeRange value={range} onChange={setRange} timezone={timezone} />
      {loading ? (
        <div className="loading-block">Loading balance history...</div>
      ) : error ? (
        <Empty title="History unavailable">{error}</Empty>
      ) : !rows.length ? (
        <Empty title="No observations in this period">
          History starts when the dashboard captures data. Try a different date
          range.
        </Empty>
      ) : (
        <div className="chart">
          <ResponsiveContainer width="100%" height={230}>
            <AreaChart
              data={chartRows}
              margin={{ left: 6, right: 16, top: 14, bottom: 0 }}
            >
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="at"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(v) => date(v, timezone).split(",")[0]}
                minTickGap={65}
                tick={{ fontSize: 10, fill: "var(--muted)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                width={65}
                tickFormatter={(v) =>
                  Intl.NumberFormat("en", { notation: "compact" }).format(v)
                }
                domain={["auto", "auto"]}
                tick={{ fontSize: 10, fill: "var(--muted)" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                labelFormatter={(v) => date(Number(v), timezone)}
                formatter={(v) => [number(Number(v)), "Observed balance"]}
                contentStyle={{
                  background: "var(--panel)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 12,
                }}
              />
              <Area
                type="linear"
                dataKey="balance"
                stroke="var(--accent)"
                fill="var(--accent-faint)"
                strokeWidth={2}
                connectNulls={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
