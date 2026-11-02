import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  Flame,
  Gift,
  LayoutDashboard,
  Monitor,
  Moon,
  Radio,
  RefreshCw,
  ShieldCheck,
  Sun,
  Target,
  Users,
  WifiOff,
} from "lucide-react";
import { api, date, duration, label, useNow, usePreference } from "./lib";
import { Badge, Empty } from "./components";
import { ChannelDetails } from "./Details";
import { Channels } from "./Channels";
import {
  ActivityLogs,
  Drops,
  Overview,
  Predictions,
  Streaks,
  System,
} from "./Views";
import type { Snapshot } from "./types";

const pages = [
  { name: "Overview", icon: LayoutDashboard },
  { name: "Channels", icon: Users },
  { name: "Streaks & recovery", icon: Flame },
  { name: "Drops & rewards", icon: Gift },
  { name: "Predictions", icon: Target },
  { name: "Activity & logs", icon: Activity },
  { name: "System", icon: Monitor },
];

export default function App() {
  const [data, setData] = useState<Snapshot | null>(null),
    [error, setError] = useState("");
  const token = useRef(""),
    [ready, setReady] = useState(false);
  useEffect(() => {
    let alive = true,
      timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    let busy = false;
    async function poll() {
      if (busy) return;
      busy = true;
      try {
        if (!token.current) {
          const result = await api<{ csrf_token: string; snapshot: Snapshot }>(
            "bootstrap",
            { signal: controller.signal },
          );
          token.current = result.csrf_token;
          if (alive) {
            setData(result.snapshot);
            setReady(true);
          }
        } else {
          const result = await api<Snapshot>("snapshot", {
            signal: controller.signal,
          });
          if (alive) setData(result);
        }
        if (alive) setError("");
      } catch (e) {
        if (alive) {
          setError((e as Error).message);
          token.current = "";
        }
      } finally {
        busy = false;
        if (alive) timer = setTimeout(poll, document.hidden ? 30000 : 5000);
      }
    }
    void poll();
    const visibility = () => {
      clearTimeout(timer);
      if (!busy) void poll();
    };
    document.addEventListener("visibilitychange", visibility);
    return () => {
      alive = false;
      clearTimeout(timer);
      controller.abort();
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  if (!ready || !data?.channels)
    return (
      <div className="boot-screen">
        <div className="brand-mark">
          <Radio size={25} />
        </div>
        <h1>Twitch Miner Dashboard</h1>
        <p>{error || "Connecting to the local miner..."}</p>
        {error && (
          <small>
            Keep the background miner running. This page reconnects
            automatically.
          </small>
        )}
      </div>
    );
  return (
    <Dashboard
      data={data}
      error={error}
      onRefresh={async () => {
        try {
          await api("refresh", {
            method: "POST",
            headers: { "X-CSRF-Token": token.current },
          });
          setData(await api<Snapshot>("snapshot"));
        } catch (e) {
          setError((e as Error).message);
          token.current = "";
        }
      }}
    />
  );
}

function Dashboard({
  data,
  error,
  onRefresh,
}: {
  data: Snapshot;
  error: string;
  onRefresh: () => Promise<void>;
}) {
  const key = "miner:" + data.account;
  const [page, setPage] = usePreference(key + ":page", "Overview");
  const [theme, setTheme] = usePreference(key + ":theme", "dark"),
    [density, setDensity] = usePreference(key + ":density", "compact");
  const [selected, setSelected] = useState<string | null>(null),
    [sending, setSending] = useState(false),
    [refreshDetails, setRefreshDetails] = useState(false);
  const close = useCallback(() => setSelected(null), []),
    select = useCallback((name: string) => setSelected(name), []);
  const now = useNow(),
    refresh = data.refresh;
  const busy = ["queued", "running"].includes(refresh.state),
    backoff = refresh.backoff_until > now;
  const remaining = Math.max(0, refresh.next_manual_at - now),
    percent = refresh.total
      ? Math.round(((refresh.completed ?? 0) / refresh.total) * 100)
      : 0;
  const stale = now - data.generated_at > 20;
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.density = density;
  }, [theme, density]);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          href="#"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            setPage("Overview");
          }}
        >
          <span className="brand-mark">
            <Radio size={21} />
          </span>
          <span>Twitch Miner</span>
        </a>
        <nav aria-label="Main navigation">
          {pages.map(({ name, icon: Icon }) => (
            <button
              key={name}
              title={name}
              aria-label={name}
              className={page === name ? "active" : ""}
              aria-current={page === name ? "page" : undefined}
              onClick={() => setPage(name)}
            >
              <Icon size={17} />
              <span>{name}</span>
              {name === "Streaks & recovery" &&
                data.summary.recoverable > 0 && (
                  <b>{data.summary.recoverable}</b>
                )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-health">
            <span
              className={
                "status-dot " + (!data.running || error ? "offline" : "")
              }
            />
            <span>
              {error
                ? "Connection lost"
                : data.running
                  ? "Miner running"
                  : "Miner starting"}
              <small>{duration(data.uptime)} uptime</small>
            </span>
          </div>
          <a
            href="https://github.com/Armi1014/Twitch-Channel-Points-Miner-v2"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
            <ArrowUpRight size={13} />
          </a>
          <div className="profile">
            <span>{data.account.slice(0, 2).toUpperCase()}</span>
            <div>
              <strong>{data.account}</strong>
            </div>
            <ShieldCheck size={15} />
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <h1>{page}</h1>
          </div>
          <div className="topbar-actions">
            <button
              className="icon-button"
              aria-label={
                theme === "dark"
                  ? "Switch to light theme"
                  : "Switch to dark theme"
              }
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <select
              aria-label="Table density"
              value={density}
              onChange={(e) => setDensity(e.target.value)}
            >
              <option value="compact">Compact</option>
              <option value="comfortable">Comfortable</option>
            </select>
            <button
              className="button primary refresh-button"
              disabled={
                busy ||
                remaining > 0 ||
                backoff ||
                sending ||
                !!error ||
                !data.running
              }
              onClick={async () => {
                setSending(true);
                await onRefresh();
                setSending(false);
              }}
            >
              <RefreshCw size={15} className={busy || sending ? "spin" : ""} />
              {busy
                ? `Refreshing ${percent}%`
                : backoff
                  ? "Twitch cooldown " + duration(refresh.backoff_until - now)
                  : remaining > 0
                    ? "Refresh in " + duration(remaining)
                    : sending
                      ? "Starting refresh..."
                      : "Refresh all"}
            </button>
          </div>
        </header>
        <div className="freshness-bar">
          <span
            className="freshness-status"
            title={"Page updated " + date(data.generated_at, data.timezone)}
          >
            <span
              className={"status-dot " + (error || stale ? "offline" : "")}
            />
            {error
              ? "Disconnected"
              : stale
                ? "Waiting for a new snapshot"
                : "Connected"}
          </span>
          <span className="freshness-divider" />
          <span>
            {busy
              ? `${refresh.completed ?? 0} / ${refresh.total ?? 0} data groups`
              : "Twitch checked " + date(refresh.completed_at, data.timezone)}
          </span>
          <button
            className="text-button"
            onClick={() => setRefreshDetails(!refreshDetails)}
            aria-expanded={refreshDetails}
          >
            {busy
              ? refresh.current?.channel === "_account"
                ? "Account inventory"
                : refresh.current?.channel || "Preparing"
              : refresh.state === "partial"
                ? "Partial update"
                : "Refresh details"}
            <ChevronDown size={12} />
          </button>
        </div>
        {busy && (
          <div
            className="refresh-progress"
            role="progressbar"
            aria-label="Full Twitch refresh"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <i style={{ width: percent + "%" }} />
          </div>
        )}
        <main>
          {error && (
            <div className="connection-alert" role="alert">
              <WifiOff size={18} />
              <div>
                <strong>Connection to the miner was lost</strong>
                <p>
                  Showing the last received data. Reconnecting automatically.{" "}
                  {error}
                </p>
              </div>
            </div>
          )}
          {data.system.history_error && (
            <p className="notice warning-text">
              {data.system.history_error}. Live observation remains available.
            </p>
          )}
          {refreshDetails && (
            <section className="panel refresh-details">
              <div>
                <CheckCircle2 size={18} />
                <strong>{label(refresh.state)} refresh</strong>
                <Badge>
                  {refresh.completed ?? 0} / {refresh.total ?? 0} groups
                </Badge>
              </div>
              <dl className="config-list">
                <div>
                  <dt>Automatic refresh</dt>
                  <dd>
                    {duration(data.system.refresh_seconds)} after completion
                  </dd>
                </div>
                <div>
                  <dt>Manual cooldown</dt>
                  <dd>{duration(data.system.cooldown_seconds)}</dd>
                </div>
              </dl>
              <p>
                Next automatic refresh:{" "}
                {date(refresh.next_auto_at, data.timezone)}
                {backoff && (
                  <span className="warning-text">
                    {" "}
                    · Twitch rate limit: waiting until{" "}
                    {date(refresh.backoff_until, data.timezone)}
                  </span>
                )}
              </p>
              {refresh.errors?.length ? (
                <details>
                  <summary>
                    {refresh.errors.length} groups could not be refreshed.
                    Previous values are retained.
                  </summary>
                  <ul>
                    {refresh.errors.map((e, i) => (
                      <li key={i}>
                        {e.channel}: {e.group}, {e.message}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </section>
          )}
          {page === "Overview" ? (
            <Overview data={data} now={now} onSelect={select} />
          ) : page === "Channels" ? (
            <Channels data={data} now={now} onSelect={select} />
          ) : page === "Streaks & recovery" ? (
            <Streaks data={data} now={now} onSelect={select} />
          ) : page === "Drops & rewards" ? (
            <Drops data={data} now={now} />
          ) : page === "Predictions" ? (
            <Predictions data={data} />
          ) : page === "Activity & logs" ? (
            <ActivityLogs data={data} />
          ) : page === "System" ? (
            <System data={data} now={now} />
          ) : (
            <Empty title="Choose a view">
              Select a page from the navigation.
            </Empty>
          )}
        </main>
      </div>
      {selected && (
        <ChannelDetails
          channel={selected}
          data={data}
          now={now}
          onClose={close}
        />
      )}
    </div>
  );
}
