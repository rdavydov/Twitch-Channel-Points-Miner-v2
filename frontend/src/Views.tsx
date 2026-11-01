import { useEffect, useMemo, useRef, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import {
  Activity as ActivityIcon,
  ArrowUpRight,
  CheckCircle2,
  Copy,
  ExternalLink,
  FileSpreadsheet,
  Flame,
  Gift,
  Pause,
  Play,
  Radio,
  ShieldCheck,
} from "lucide-react";
import { Channels } from "./Channels";
import {
  Badge,
  ConfigList,
  Empty,
  Progress,
  Remaining,
  SectionHeading,
  TimeRange,
} from "./components";
import { DataTable } from "./Table";
import { api, date, duration, label, number, signed } from "./lib";
import type { Activity, Drop, LogLine, Prediction, Snapshot } from "./types";

export function Overview({
  data,
  now,
  onSelect,
}: {
  data: Snapshot;
  now: number;
  onSelect: (name: string) => void;
}) {
  const watching = data.channels.filter((c) => c.watching);
  const attention = data.channels
    .filter((c) => c.needs_attention)
    .sort(
      (a, b) =>
        Number(b.recoverable) - Number(a.recoverable) ||
        (a.recovery?.expires_at ?? Infinity) -
          (b.recovery?.expires_at ?? Infinity),
    );
  return (
    <>
      <div className="overview-title">
        <div>
          <span className="eyebrow">YOUR MINER, AT A GLANCE</span>
          <h1>Everything in view.</h1>
          <p>Live channels, protected streaks and every point accounted for.</p>
        </div>
        <Badge>
          <ShieldCheck size={12} />
          Read-only dashboard
        </Badge>
      </div>
      <div className="watch-lanes">
        {[0, 1].map((i) => {
          const channel = watching[i];
          return (
            <div
              className={"watch-lane " + (channel ? "occupied" : "")}
              key={i}
            >
              <div className="lane-label">
                <Radio size={14} />
                <span>WATCH SLOT {i + 1}</span>
                <Badge tone={channel ? "accent" : ""}>
                  {channel ? "Active" : "Available"}
                </Badge>
              </div>
              {channel ? (
                <>
                  <button
                    className="lane-channel"
                    onClick={() => onSelect(channel.channel)}
                  >
                    {channel.channel}
                    <ArrowUpRight size={19} />
                  </button>
                  <p className="lane-reason">{channel.reason}</p>
                  <div className="lane-data">
                    <span>
                      <b className="mono">{number(channel.points)}</b> points
                    </span>
                    <span>
                      <Flame size={13} />
                      <b>{channel.streak ?? "?"}</b> day streak
                    </span>
                    <Badge
                      tone={
                        channel.streak_status === "Confirmed" ? "success" : ""
                      }
                    >
                      {channel.streak_status}
                    </Badge>
                  </div>
                </>
              ) : (
                <>
                  <h3>Waiting for an eligible channel</h3>
                  <p className="muted">
                    The miner assigns this slot using your configured
                    priorities.
                  </p>
                </>
              )}
            </div>
          );
        })}
      </div>
      <div className="stat-strip">
        <div>
          <span>Captured today</span>
          <strong className="success-text mono">
            +{number(data.summary.earned_today)}
          </strong>
          <small>Watch and reward gains since capture began</small>
        </div>
        <div>
          <span>Channels live</span>
          <strong className="mono">
            {data.summary.online}
            <small> / {data.channels.length}</small>
          </strong>
          <small>{data.summary.watching} currently watched</small>
        </div>
        <div>
          <span>Streaks confirmed</span>
          <strong className="mono">{data.summary.confirmed}</strong>
          <small>During the current live broadcasts</small>
        </div>
        <div>
          <span>Recovery available</span>
          <strong
            className={
              "mono " + (data.summary.recoverable ? "warning-text" : "")
            }
          >
            {data.summary.recoverable}
          </strong>
          <small>Twitch-reported recovery windows</small>
        </div>
      </div>
      {attention.length > 0 && (
        <section className="attention-panel">
          <div>
            <Flame size={17} />
            <strong>Needs attention</strong>
            <span className="muted">{attention.length} channels</span>
          </div>
          <div className="attention-items">
            {attention.slice(0, 5).map((c) => (
              <button key={c.channel} onClick={() => onSelect(c.channel)}>
                <span>{c.channel}</span>
                <small>
                  {c.recoverable ? (
                    <Remaining at={c.recovery?.expires_at} now={now} />
                  ) : c.streak_status === "Pending" ||
                    c.streak_status === "In progress" ? (
                    "Streak not yet confirmed"
                  ) : (
                    "Data refresh needs attention"
                  )}
                </small>
                <ArrowUpRight size={13} />
              </button>
            ))}
          </div>
        </section>
      )}
      <Channels data={data} now={now} onSelect={onSelect} />
    </>
  );
}

export function Streaks({
  data,
  now,
  onSelect,
}: {
  data: Snapshot;
  now: number;
  onSelect: (name: string) => void;
}) {
  const jobs = data.channels.filter((c) => c.recovery_job);
  return (
    <>
      <Channels data={data} now={now} onSelect={onSelect} streaks />
      <SectionHeading
        title="Recovery attempts"
        caption="Playback attempts are shown separately from Twitch-confirmed recoveries."
      />
      {!jobs.length ? (
        <Empty title="No recovery attempts recorded">
          When the miner tries a clip or VOD, its method and verified result
          will appear here.
        </Empty>
      ) : (
        <div className="recovery-cards">
          {jobs.map((c) => (
            <article className="panel" key={c.channel}>
              <div className="panel-top">
                <button
                  className="channel-name"
                  onClick={() => onSelect(c.channel)}
                >
                  {c.channel}
                </button>
                <Badge
                  tone={
                    c.recovery_job?.state === "confirmed"
                      ? "success"
                      : c.recovery_job?.state === "failed"
                        ? "danger"
                        : "warning"
                  }
                >
                  {label(c.recovery_job!.state)}
                </Badge>
              </div>
              <dl className="config-list">
                <div>
                  <dt>Method</dt>
                  <dd>{c.recovery_job?.method || "Searching for replay"}</dd>
                </div>
                <div>
                  <dt>Last update</dt>
                  <dd>{date(c.recovery_job?.at, data.timezone)}</dd>
                </div>
                <div>
                  <dt>Next attempt allowed</dt>
                  <dd>{date(c.recovery_job?.next_retry_at, data.timezone)}</dd>
                </div>
              </dl>
              {c.recovery_job?.replay_url && (
                <a
                  href={c.recovery_job.replay_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open replay <ExternalLink size={12} />
                </a>
              )}
            </article>
          ))}
        </div>
      )}
    </>
  );
}

export function Drops({ data, now }: { data: Snapshot; now: number }) {
  const [filter, setFilter] = useState("In progress");
  const rows = data.drops.filter(
    (d) =>
      filter === "All rewards" ||
      (filter === "Claimed" ? d.claimed : !d.claimed),
  );
  const columns = useMemo<ColumnDef<Drop>[]>(
    () => [
      { accessorKey: "name", header: "Drop", size: 260 },
      { accessorKey: "campaign", header: "Campaign", size: 230 },
      { accessorKey: "game", header: "Game", size: 200 },
      {
        id: "progress",
        header: "Watch progress",
        accessorFn: (row) => row.minutes ?? undefined,
        size: 230,
        cell: ({ row }) =>
          row.original.claimed ? (
            <Badge tone="success">
              <CheckCircle2 size={12} />
              Claimed
            </Badge>
          ) : (
            <Progress
              value={row.original.minutes}
              total={row.original.required_minutes}
            />
          ),
      },
      {
        accessorKey: "ends_at",
        header: "Time remaining",
        size: 170,
        cell: ({ row }) =>
          row.original.claimed ? (
            date(row.original.claimed_at, data.timezone)
          ) : (
            <Remaining at={row.original.ends_at} now={now} />
          ),
      },
      { accessorKey: "reward", header: "Reward", size: 280 },
    ],
    [data.timezone, now],
  );
  return (
    <>
      <SectionHeading
        title="Drops & rewards"
        caption="Inventory and progress reported by Twitch."
      >
        <a
          className="button"
          href="https://www.twitch.tv/drops/inventory"
          target="_blank"
          rel="noreferrer"
        >
          <Gift size={15} />
          Twitch inventory
          <ExternalLink size={12} />
        </a>
      </SectionHeading>
      <div className="filter-tabs">
        {["In progress", "Claimed", "All rewards"].map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={filter === t ? "active" : ""}
          >
            {t}
          </button>
        ))}
      </div>
      <DataTable
        rows={rows}
        columns={columns}
        account={data.account}
        name="drops"
      />
      <SectionHeading
        title="Weekly rewards"
        caption="Availability and completion are confirmed by Twitch."
      />
      <div className="recovery-cards">
        {data.channels
          .filter((c) => c.weekly)
          .map((c) => (
            <article className="panel" key={c.channel}>
              <div className="panel-top">
                <strong>{c.channel}</strong>
                <Badge
                  tone={
                    c.weekly?.earned_this_week
                      ? "success"
                      : c.weekly?.visited_today
                        ? "accent"
                        : ""
                  }
                >
                  {c.weekly?.earned_this_week
                    ? "Weekly reward earned"
                    : c.weekly?.visited_today
                      ? "Visited today"
                      : "Visit pending"}
                </Badge>
              </div>
              <dl className="config-list">
                <div>
                  <dt>Visits this week</dt>
                  <dd>{c.weekly?.days_visited}</dd>
                </div>
                <div>
                  <dt>Completed reward tiers</dt>
                  <dd>
                    {c.weekly?.accumulated_weeks} / {c.weekly?.reward_count}
                  </dd>
                </div>
                <div>
                  <dt>Event window</dt>
                  <dd>
                    <Remaining at={c.weekly?.ends_at} now={now} />
                  </dd>
                </div>
              </dl>
            </article>
          ))}
      </div>
      {!data.channels.some((c) => c.weekly) && (
        <Empty title="No active weekly rewards reported">
          Availability depends on your Twitch account and the channel. Check the
          refresh status for unavailable responses.
        </Empty>
      )}
      <SectionHeading title="Available campaigns" />
      <div className="campaign-list">
        {data.campaigns
          .filter((c) => c.status === "ACTIVE")
          .slice(0, 100)
          .map((c) => (
            <div key={c.id}>
              <span>
                <strong>{c.name}</strong>
                <small>{c.game}</small>
              </span>
              <Remaining at={c.ends_at} now={now} />
            </div>
          ))}
      </div>
    </>
  );
}

export function Predictions({ data }: { data: Snapshot }) {
  const [source, setSource] = useState("All sources"),
    [result, setResult] = useState("All results");
  const [range, setRange] = useState({
    start: 0,
    end: Date.now() / 1000,
    preset: "all",
  });
  const rows = data.predictions.filter(
    (p) =>
      (source === "All sources" ||
        (source === "Miner" ? p.source === "Miner" : p.source !== "Miner")) &&
      (result === "All results" || (p.result ?? "PENDING") === result) &&
      (p.resolved_at ?? p.placed_at ?? 0) >= range.start &&
      (p.resolved_at ?? p.placed_at ?? 0) <= range.end,
  );
  const closed = rows.filter((p) => p.result),
    wins = closed.filter((p) => p.result === "WIN").length,
    losses = closed.filter((p) => p.result === "LOSE").length;
  const columns = useMemo<ColumnDef<Prediction>[]>(
    () => [
      { accessorKey: "channel", header: "Channel", size: 160 },
      {
        accessorKey: "prediction",
        header: "Prediction",
        size: 330,
        cell: ({ getValue }) => (
          <span className="cell-wrap">
            {String(getValue() ?? "Unknown prediction")}
          </span>
        ),
      },
      { accessorKey: "outcome", header: "Outcome", size: 200 },
      {
        accessorKey: "stake",
        header: "Stake",
        cell: ({ getValue }) => (
          <span className="mono">{number(getValue())}</span>
        ),
      },
      {
        accessorKey: "result",
        header: "Result",
        cell: ({ getValue }) => (
          <Badge
            tone={
              getValue() === "WIN"
                ? "success"
                : getValue() === "LOSE"
                  ? "danger"
                  : getValue() === "REFUND"
                    ? "warning"
                    : "accent"
            }
          >
            {getValue() ? label(String(getValue())) : "Pending"}
          </Badge>
        ),
      },
      {
        accessorKey: "payout",
        header: "Payout",
        cell: ({ getValue }) => (
          <span className="mono">{number(getValue())}</span>
        ),
      },
      {
        accessorKey: "net",
        header: "Net result",
        cell: ({ getValue }) => (
          <strong
            className={
              "mono " +
              (getValue<number>() > 0
                ? "success-text"
                : getValue<number>() < 0
                  ? "danger-text"
                  : "")
            }
          >
            {signed(getValue<number>())}
          </strong>
        ),
      },
      { accessorKey: "source", header: "Source", size: 210 },
      {
        accessorKey: "placed_at",
        header: "Placed",
        size: 170,
        cell: ({ getValue }) => date(getValue<number>(), data.timezone),
      },
      {
        accessorKey: "resolved_at",
        header: "Settled",
        size: 170,
        cell: ({ getValue }) => date(getValue<number>(), data.timezone),
      },
      {
        accessorKey: "recovered",
        header: "Recovered result",
        cell: ({ getValue }) => (getValue() ? "Yes" : "No"),
      },
    ],
    [data.timezone],
  );
  return (
    <>
      <SectionHeading
        title="Predictions"
        caption="Twitch-confirmed stakes and payouts, including manual bets."
      />
      <div className="stat-strip">
        <div>
          <span>Won / lost</span>
          <strong className="mono">
            {wins}
            <small> / {losses}</small>
          </strong>
          <small>
            {closed.filter((p) => p.result === "REFUND").length} refunds
            excluded from win rate
          </small>
        </div>
        <div>
          <span>Win rate</span>
          <strong className="mono">
            {wins + losses
              ? ((wins / (wins + losses)) * 100).toFixed(1) + "%"
              : "Not available"}
          </strong>
          <small>For the current filters</small>
        </div>
        <div>
          <span>Net result</span>
          <strong
            className={
              "mono " +
              (closed.reduce((a, p) => a + (p.net ?? 0), 0) < 0
                ? "danger-text"
                : "success-text")
            }
          >
            {signed(closed.reduce((a, p) => a + (p.net ?? 0), 0))}
          </strong>
          <small>Payout minus stake</small>
        </div>
        <div>
          <span>Open predictions</span>
          <strong className="mono">
            {rows.filter((p) => !p.result).length}
          </strong>
          <small>Known bets awaiting a result</small>
        </div>
      </div>
      <div className="view-controls">
        <select
          aria-label="Prediction source"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        >
          {["All sources", "Miner", "Manual / external"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          aria-label="Prediction result"
          value={result}
          onChange={(e) => setResult(e.target.value)}
        >
          {["All results", "WIN", "LOSE", "REFUND", "PENDING"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <TimeRange value={range} onChange={setRange} timezone={data.timezone} />
      </div>
      <DataTable
        rows={rows}
        columns={columns}
        account={data.account}
        name="predictions"
        initialSort={[{ id: "placed_at", desc: true }]}
        hidden={["recovered", "resolved_at"]}
      />
    </>
  );
}

export function ActivityLogs({ data }: { data: Snapshot }) {
  const [tab, setTab] = useState("Activity"),
    [search, setSearch] = useState(""),
    [channel, setChannel] = useState("");
  const [events, setEvents] = useState<Activity[]>([]),
    [logs, setLogs] = useState<LogLine[]>([]);
  const [debug, setDebug] = useState(false),
    [following, setFollowing] = useState(true),
    [error, setError] = useState("");
  const followingRef = useRef(following);
  followingRef.current = following;
  const [range, setRange] = useState({
    start: Date.now() / 1000 - 7 * 86400,
    end: Date.now() / 1000,
    preset: "7",
  });
  useEffect(() => {
    if (tab !== "Activity") return;
    const controller = new AbortController(),
      timer = setTimeout(() => {
        api<Activity[]>(
          `activity?search=${encodeURIComponent(search)}&channel=${encodeURIComponent(channel)}&start=${range.start}&end=${range.preset === "custom" ? range.end : Date.now() / 1000}`,
          { signal: controller.signal },
        )
          .then((v) => {
            setEvents(v);
            setError("");
          })
          .catch((e) => {
            if (e.name !== "AbortError") setError(e.message);
          });
      }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [tab, search, channel, range, data.generated_at]);
  useEffect(() => {
    if (tab !== "Logs") return;
    let alive = true,
      timer: ReturnType<typeof setTimeout>,
      cursor = "",
      initial = true;
    const controller = new AbortController();
    setLogs([]);
    async function poll() {
      if (!followingRef.current && !initial) {
        if (alive) timer = setTimeout(poll, document.hidden ? 30000 : 5000);
        return;
      }
      try {
        const result = await api<{ lines: LogLine[]; cursor: string }>(
          `logs?debug=${debug}&cursor=${encodeURIComponent(cursor)}`,
          { signal: controller.signal },
        );
        if (alive && (followingRef.current || initial)) {
          cursor = result.cursor;
          setLogs((v) => [...v, ...result.lines].slice(-1000));
          setError("");
          initial = false;
        }
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
      if (alive) timer = setTimeout(poll, document.hidden ? 30000 : 5000);
    }
    void poll();
    return () => {
      alive = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [tab, debug]);
  const lines = logs.filter((l) =>
    l.message.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <SectionHeading
        title="Activity & logs"
        caption="A searchable timeline and bounded, credential-redacted log viewer."
      />
      <div className="filter-tabs">
        {["Activity", "Logs"].map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setSearch("");
            }}
            className={tab === t ? "active" : ""}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="view-controls">
        <input
          aria-label="Search activity or logs"
          placeholder="Search messages..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {tab === "Activity" ? (
          <>
            <select
              aria-label="Activity channel"
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
            >
              <option value="">All channels</option>
              {data.channels.map((c) => (
                <option key={c.channel}>{c.channel}</option>
              ))}
            </select>
            <TimeRange
              value={range}
              onChange={setRange}
              timezone={data.timezone}
            />
          </>
        ) : (
          <>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={debug}
                onChange={(e) => setDebug(e.target.checked)}
              />
              Include DEBUG
            </label>
            <button className="button" onClick={() => setFollowing(!following)}>
              {following ? <Pause size={14} /> : <Play size={14} />}{" "}
              {following ? "Pause following" : "Resume following"}
            </button>
            <button
              className="button"
              onClick={() =>
                navigator.clipboard
                  .writeText(
                    lines
                      .map((l) => `${l.at || ""} [${l.level}] ${l.message}`)
                      .join("\n"),
                  )
                  .catch(() =>
                    setError(
                      "Clipboard is unavailable. Select and copy the visible text.",
                    ),
                  )
              }
            >
              <Copy size={14} />
              Copy sanitized logs
            </button>
          </>
        )}
      </div>
      {error && (
        <p className="notice warning-text" role="alert">
          {error}
        </p>
      )}
      {tab === "Activity" ? (
        <div className="activity-list">
          {events.length ? (
            events.map((e) => (
              <div className="activity-row" key={e.id}>
                <span
                  className={
                    "event-icon " +
                    (e.kind.includes("confirmed") ? "success-text" : "")
                  }
                >
                  <ActivityIcon size={16} />
                </span>
                <div>
                  <span className="activity-kind">
                    {label(e.kind)}
                    {e.channel && <Badge>{e.channel}</Badge>}
                  </span>
                  <p>{e.message}</p>
                </div>
                <time>{date(e.at, data.timezone)}</time>
              </div>
            ))
          ) : (
            <Empty title="No events in this view">
              Try a different channel, search or date range.
            </Empty>
          )}
        </div>
      ) : (
        <div className="log-box" role="log" aria-label="Miner logs">
          {lines.length ? (
            lines.map((l, i) => (
              <div className={"log-line " + l.level.toLowerCase()} key={i}>
                <time>{l.at}</time>
                <span className="log-level">{l.level}</span>
                <span>{l.message}</span>
              </div>
            ))
          ) : (
            <p className="muted">No matching log records.</p>
          )}
        </div>
      )}
    </>
  );
}

export function System({ data, now }: { data: Snapshot; now: number }) {
  const [reports, setReports] = useState<
    { id: string; name: string; modified_at: number; bytes: number }[]
  >([]);
  useEffect(() => {
    const controller = new AbortController();
    api<typeof reports>("reports", { signal: controller.signal })
      .then(setReports)
      .catch(() => {});
    return () => controller.abort();
  }, []);
  return (
    <>
      <SectionHeading
        title="System"
        caption="Current runtime and configuration. All values are read-only."
      />
      <div className="stat-strip">
        <div>
          <span>Process CPU</span>
          <strong className="mono">
            {data.system.cpu_percent.toFixed(1)}%
          </strong>
          <small>Miner and dashboard together</small>
        </div>
        <div>
          <span>Memory</span>
          <strong className="mono">
            {data.system.memory_mb}
            <small> MB</small>
          </strong>
          <small>Resident process memory</small>
        </div>
        <div>
          <span>Uptime</span>
          <strong className="mono">{duration(data.uptime)}</strong>
          <small>{data.system.threads} process threads</small>
        </div>
        <div>
          <span>Read reuse</span>
          <strong className="mono">{number(data.refresh.cache_hits)}</strong>
          <small>Recent reads reused across workers</small>
        </div>
      </div>
      <div className="two-columns">
        <section className="panel">
          <SectionHeading title="Twitch connections" />
          {data.system.connections.map((c) => (
            <div className="status-row" key={c.name}>
              <span>{c.name}</span>
              <Badge
                tone={
                  c.state === "CONNECTED" ||
                  c.state === "OPEN" ||
                  c.state === "AUTHENTICATED"
                    ? "success"
                    : ""
                }
              >
                {label(c.state)}
              </Badge>
            </div>
          ))}
          <dl className="config-list">
            <div>
              <dt>Last watch selection</dt>
              <dd>{date(data.system.selection_at, data.timezone)}</dd>
            </div>
            <div>
              <dt>Account</dt>
              <dd>{data.account}</dd>
            </div>
            <div>
              <dt>Timezone</dt>
              <dd>{data.timezone}</dd>
            </div>
            <div>
              <dt>History capture began</dt>
              <dd>{date(data.system.capture_started_at, data.timezone)}</dd>
            </div>
          </dl>
        </section>
        <section className="panel">
          <SectionHeading title="Refresh coordinator" />
          <dl className="config-list">
            <div>
              <dt>Automatic full refresh</dt>
              <dd>{duration(data.system.refresh_seconds)} after completion</dd>
            </div>
            <div>
              <dt>Manual cooldown</dt>
              <dd>{duration(data.system.cooldown_seconds)}</dd>
            </div>
            <div>
              <dt>Extra Twitch reads</dt>
              <dd>One per {data.system.request_interval_seconds}s</dd>
            </div>
            <div>
              <dt>Backoff</dt>
              <dd>
                {data.refresh.backoff_until > now
                  ? duration(data.refresh.backoff_until - now) + " remaining"
                  : "No active restriction"}
              </dd>
            </div>
            <div>
              <dt>Dashboard Twitch requests</dt>
              <dd>{number(data.refresh.observer_requests)}</dd>
            </div>
          </dl>
          {data.refresh.errors?.length ? (
            <details>
              <summary>
                {data.refresh.errors.length} unavailable data groups
              </summary>
              <ul>
                {data.refresh.errors.map((e, i) => (
                  <li key={i}>
                    {e.channel}: {e.group}, {e.message}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </section>
      </div>
      <div className="two-columns">
        <section className="panel">
          <SectionHeading
            title="Selection priorities"
            caption="Streak slots are reserved separately from the remaining selection rules."
          />
          <p className="notice">
            Reserved streak slots: {data.system.streak_slots ?? "Default"}
          </p>
          <ol className="priority-list">
            {data.system.priorities
              .filter((p) => p !== "STREAK")
              .map((p) => (
                <li key={p}>{label(p)}</li>
              ))}
          </ol>
        </section>
        <section className="panel">
          <SectionHeading title="Default channel configuration" />
          <ConfigList value={data.system.settings} />
        </section>
      </div>
      <section className="panel">
        <SectionHeading
          title="Prediction configuration"
          caption="Configured limits are shown even when automatic betting is disabled."
        />
        <ConfigList
          value={data.system.settings.bet as Record<string, unknown>}
        />
        <ConfigList
          value={
            (data.system.settings.bet as Record<string, unknown>)
              .filter as Record<string, unknown>
          }
        />
      </section>
      <section className="panel">
        <SectionHeading
          title="Reports"
          caption="Existing account-specific Excel and CSV reports."
        />
        {reports.map((r) => (
          <a
            className="report-row"
            href={
              "/api/v1/reports/" +
              r.id.split("/").map(encodeURIComponent).join("/")
            }
            key={r.id}
          >
            <FileSpreadsheet size={18} />
            <span>
              {r.name}
              <small>
                {r.id.split("/")[0]} · {date(r.modified_at, data.timezone)}
              </small>
            </span>
            <span className="muted mono">
              {number(Math.ceil(r.bytes / 1024))} KB
            </span>
            <ExternalLink size={13} />
          </a>
        ))}
      </section>
    </>
  );
}
