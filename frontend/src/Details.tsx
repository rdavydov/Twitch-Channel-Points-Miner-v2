import { lazy, Suspense, useEffect, useState } from "react";
import { ExternalLink, X } from "lucide-react";
import {
  Badge,
  ConfigList,
  CopyNumber,
  Remaining,
  SectionHeading,
} from "./components";
import { api, date, label } from "./lib";
import type { Activity, Snapshot } from "./types";

const BalanceChart = lazy(() =>
  import("./BalanceChart").then((module) => ({ default: module.BalanceChart })),
);

export function ChannelDetails({
  channel,
  data,
  now,
  onClose,
}: {
  channel: string;
  data: Snapshot;
  now: number;
  onClose: () => void;
}) {
  const row = data.channels.find((c) => c.channel === channel);
  const [tab, setTab] = useState("Overview"),
    [events, setEvents] = useState<Activity[]>([]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", close);
    document.getElementById("detail-close")?.focus();
    return () => {
      document.removeEventListener("keydown", close);
      previous?.focus();
    };
  }, [onClose]);
  useEffect(() => {
    const controller = new AbortController();
    api<Activity[]>("activity?channel=" + encodeURIComponent(channel), {
      signal: controller.signal,
    })
      .then(setEvents)
      .catch(() => {});
    return () => controller.abort();
  }, [channel, data.generated_at]);
  if (!row) return null;
  return (
    <div
      className="drawer-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-title"
        onKeyDown={(e) => {
          if (e.key === "Tab") {
            const all = e.currentTarget.querySelectorAll<HTMLElement>(
              'button:not(:disabled), a, input, select, [tabindex="0"]',
            );
            const first = all[0],
              last = all[all.length - 1];
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last?.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <div className="drawer-heading">
          <div>
            <span className="eyebrow">Channel details</span>
            <h2 id="detail-title">{channel}</h2>
          </div>
          <a
            className="icon-button"
            href={"https://www.twitch.tv/" + channel}
            target="_blank"
            rel="noreferrer"
            aria-label="Open Twitch channel"
          >
            <ExternalLink size={17} />
          </a>
          <button
            id="detail-close"
            className="icon-button"
            aria-label="Close channel details"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        <div className="drawer-tabs">
          {["Overview", "Activity", "Configuration"].map((t) => (
            <button
              key={t}
              className={tab === t ? "active" : ""}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="drawer-content">
          {tab === "Overview" && (
            <>
              <div className="detail-stats">
                <div>
                  <span>Channel points</span>
                  <strong>
                    <CopyNumber value={row.points} />
                  </strong>
                </div>
                <div>
                  <span>Watch streak</span>
                  <strong>
                    {row.streak ?? "Unknown"} <small>days</small>
                  </strong>
                </div>
                <div>
                  <span>Current broadcast</span>
                  <Badge
                    tone={row.streak_status === "Confirmed" ? "success" : ""}
                  >
                    {row.streak_status}
                  </Badge>
                </div>
              </div>
              <div className="detail-status">
                <Badge
                  tone={row.watching ? "accent" : row.online ? "success" : ""}
                >
                  {row.watching ? "Watching" : row.online ? "Live" : "Offline"}
                </Badge>
                <span>{row.reason}</span>
              </div>
              {row.title && <p className="stream-title">{row.title}</p>}
              <Suspense
                fallback={<div className="loading-block">Loading chart...</div>}
              >
                <BalanceChart channel={channel} timezone={data.timezone} />
              </Suspense>
              <SectionHeading title="Streak & recovery" />
              <dl className="config-list">
                <div>
                  <dt>Recovery eligibility</dt>
                  <dd>
                    {row.recoverable ? (
                      <Badge tone="warning">Recoverable</Badge>
                    ) : (
                      "Not currently recoverable"
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Recovery window</dt>
                  <dd>
                    <Remaining at={row.recovery?.expires_at} now={now} />
                  </dd>
                </div>
                <div>
                  <dt>Current broadcast attempts</dt>
                  <dd>{row.attempts}</dd>
                </div>
                <div>
                  <dt>Last verified</dt>
                  <dd>{date(row.last_verification_at, data.timezone)}</dd>
                </div>
                <div>
                  <dt>Latest recovery attempt</dt>
                  <dd>
                    {row.recovery_job
                      ? label(row.recovery_job.state)
                      : "No recorded attempts"}
                  </dd>
                </div>
                {row.recovery_job?.replay_url && (
                  <div>
                    <dt>Playback method</dt>
                    <dd>
                      <a
                        href={row.recovery_job.replay_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {row.recovery_job.method || "Replay"}{" "}
                        <ExternalLink size={11} />
                      </a>
                    </dd>
                  </div>
                )}
              </dl>
              <SectionHeading title="Data freshness" />
              {Object.entries(row.freshness).map(([group, v]) => (
                <div className="freshness-row" key={group}>
                  <strong>{label(group)}</strong>
                  <span>{date(v.checked_at, data.timezone)}</span>
                  <small>{v.error || v.source}</small>
                  <Badge
                    tone={v.error ? "danger" : v.stale ? "warning" : "success"}
                  >
                    {v.error ? "Unavailable" : v.stale ? "Stale" : "Current"}
                  </Badge>
                </div>
              ))}
            </>
          )}
          {tab === "Activity" && (
            <>
              <SectionHeading
                title="Channel timeline"
                caption="Recorded events, including available imported history."
              />
              {events.length ? (
                events.map((e) => (
                  <div className="timeline-event" key={e.id}>
                    <time>{date(e.at, data.timezone)}</time>
                    <Badge>{label(e.kind)}</Badge>
                    <p>{e.message}</p>
                  </div>
                ))
              ) : (
                <p className="muted">No recorded events for this channel.</p>
              )}
            </>
          )}
          {tab === "Configuration" && (
            <>
              <p className="notice">
                Read-only configuration from your runner. Changes are made in
                run.py.
              </p>
              <ConfigList value={row.settings} />
              <SectionHeading title="Prediction settings" />
              <ConfigList value={row.settings.bet as Record<string, unknown>} />
              <SectionHeading title="Prediction filter" />
              <ConfigList
                value={
                  (row.settings.bet as Record<string, unknown>)
                    .filter as Record<string, unknown>
                }
              />
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
