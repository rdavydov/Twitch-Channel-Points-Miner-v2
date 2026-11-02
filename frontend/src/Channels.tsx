import { useMemo, useState } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { ExternalLink, Radio, Star } from "lucide-react";
import { DataTable } from "./Table";
import { Badge, CopyNumber, Remaining, SectionHeading } from "./components";
import { date, number, signed } from "./lib";
import type { Channel, Snapshot } from "./types";

export function Channels({
  data,
  now,
  onSelect,
  streaks = false,
}: {
  data: Snapshot;
  now: number;
  onSelect: (channel: string) => void;
  streaks?: boolean;
}) {
  const [filter, setFilter] = useState("All channels");
  const rows = data.channels.filter((c) =>
    filter === "Watching"
      ? c.watching
      : filter === "Live"
        ? c.online
        : filter === "Favorites"
          ? c.favorite
          : filter === "Needs attention"
            ? c.needs_attention
            : filter === "Recoverable"
              ? c.recoverable
              : true,
  );
  const columns = useMemo<ColumnDef<Channel>[]>(
    () => [
      {
        accessorKey: "channel",
        header: "Channel",
        size: 215,
        cell: ({ row }) => (
          <div className="channel-cell">
            <span
              className={
                "channel-avatar " + (row.original.watching ? "watching" : "")
              }
            >
              {row.original.channel.slice(0, 2).toUpperCase()}
            </span>
            <button
              className="channel-name"
              onClick={() => onSelect(row.original.channel)}
            >
              {row.original.channel}
              {row.original.favorite && (
                <Star size={11} className="star" fill="currentColor" />
              )}
            </button>
            <a
              className="external-channel"
              href={"https://www.twitch.tv/" + row.original.channel}
              target="_blank"
              rel="noreferrer"
              aria-label={"Open " + row.original.channel + " on Twitch"}
            >
              <ExternalLink size={12} />
            </a>
          </div>
        ),
      },
      {
        accessorKey: "watching",
        header: "Watching",
        size: 125,
        cell: ({ row }) => (
          <Badge
            tone={
              row.original.watching
                ? "accent"
                : row.original.online
                  ? "success"
                  : ""
            }
          >
            {row.original.watching ? (
              <>
                <Radio size={11} />
                Watching
              </>
            ) : row.original.online ? (
              "Live"
            ) : (
              "Offline"
            )}
          </Badge>
        ),
      },
      {
        accessorKey: "points",
        header: "Points",
        size: 145,
        cell: ({ getValue }) => (
          <CopyNumber value={getValue<number | null>()} />
        ),
      },
      {
        accessorKey: "earned_today",
        header: "Captured today",
        size: 155,
        cell: ({ getValue }) => (
          <span className="mono success-text">+{number(getValue())}</span>
        ),
      },
      {
        accessorKey: "streak",
        header: "Streak",
        size: 100,
        cell: ({ getValue }) => (
          <span className="streak-number mono">
            {getValue() == null ? "Unknown" : number(getValue()) + " days"}
          </span>
        ),
      },
      {
        accessorKey: "streak_status",
        header: "Current broadcast",
        size: 165,
        cell: ({ getValue }) => (
          <Badge
            tone={
              getValue() === "Confirmed"
                ? "success"
                : getValue() === "In progress"
                  ? "accent"
                  : ""
            }
          >
            {String(getValue())}
          </Badge>
        ),
      },
      {
        id: "recovery",
        accessorFn: (row) => row.recovery?.expires_at ?? undefined,
        header: "Recovery window",
        size: 155,
        cell: ({ row }) =>
          row.original.recoverable ? (
            <Remaining at={row.original.recovery?.expires_at} now={now} />
          ) : (
            <span className="muted">
              {row.original.recovery_job?.state === "confirmed"
                ? "Recovered"
                : "Not recoverable"}
            </span>
          ),
      },
      {
        accessorKey: "balance_change",
        header: "Observed change today",
        size: 185,
        cell: ({ getValue }) => (
          <span className="mono">{signed(getValue<number>())}</span>
        ),
      },
      ...["daily", "weekly", "monthly", "yearly"].map((period) => ({
        id: "reported_" + period,
        header: "Reported net: " + period,
        accessorFn: (row: Channel) => row.reported_period_points?.[period],
        size: 180,
        cell: ({ getValue }: { getValue: () => unknown }) => number(getValue()),
      })),
      {
        accessorKey: "favorite",
        header: "Favorite",
        size: 100,
        cell: ({ getValue }) => (getValue() ? "Yes" : "No"),
      },
      {
        accessorKey: "reason",
        header: "Selection reason",
        size: 280,
        cell: ({ getValue }) => (
          <span className="cell-ellipsis" title={String(getValue())}>
            {String(getValue())}
          </span>
        ),
      },
      {
        accessorKey: "subscription_tier",
        header: "Subscription tier",
        size: 160,
        cell: ({ getValue }) =>
          getValue() == null ? (
            <span className="muted">Not available</span>
          ) : (
            String(getValue())
          ),
      },
      {
        accessorKey: "points_limit",
        header: "Point limit",
        cell: ({ getValue }) =>
          getValue() == null ? "No limit" : number(getValue()),
      },
      {
        accessorKey: "follow_date",
        header: "Followed",
        cell: ({ getValue }) => date(getValue<string>(), data.timezone),
      },
      {
        accessorKey: "last_activity",
        header: "Last watch request",
        cell: ({ getValue }) => date(getValue<number>(), data.timezone),
      },
      {
        accessorKey: "game",
        header: "Category",
        size: 200,
        cell: ({ getValue }) => String(getValue() ?? "Not available"),
      },
      {
        accessorKey: "viewers",
        header: "Viewers",
        cell: ({ getValue }) => number(getValue()),
      },
      {
        accessorKey: "chat_banned",
        header: "Chat ban",
        cell: ({ getValue }) =>
          getValue() ? <Badge tone="danger">Banned</Badge> : "No",
      },
      {
        id: "weekly",
        header: "Weekly visits",
        accessorFn: (row) => row.weekly?.days_visited,
        cell: ({ row }) =>
          row.original.weekly
            ? number(row.original.weekly.days_visited) + " visits"
            : "Not available",
      },
      {
        id: "freshness",
        header: "Points checked",
        accessorFn: (row) => row.freshness.points?.checked_at,
        cell: ({ row }) => (
          <span
            className={
              row.original.freshness.points?.error ? "warning-text" : "muted"
            }
          >
            {date(row.original.freshness.points?.checked_at, data.timezone)}
          </span>
        ),
      },
    ],
    [onSelect, now, data.timezone],
  );
  const hidden = streaks
    ? [
        "points",
        "earned_today",
        "balance_change",
        "reported_daily",
        "reported_weekly",
        "reported_monthly",
        "reported_yearly",
        "favorite",
        "reason",
        "subscription_tier",
        "points_limit",
        "follow_date",
        "last_activity",
        "game",
        "viewers",
        "chat_banned",
        "weekly",
        "freshness",
      ]
    : [
        "balance_change",
        "reported_daily",
        "reported_weekly",
        "reported_monthly",
        "reported_yearly",
        "favorite",
        "reason",
        "subscription_tier",
        "points_limit",
        "follow_date",
        "last_activity",
        "game",
        "viewers",
        "chat_banned",
        "weekly",
        "freshness",
      ];
  return (
    <>
      <SectionHeading
        title={streaks ? "Watch streaks" : "Channels"}
        caption={
          streaks
            ? "A successful playback request is an attempt. Twitch must confirm completion."
            : undefined
        }
      />
      <div className="filter-tabs">
        {[
          "All channels",
          "Watching",
          "Live",
          "Favorites",
          "Needs attention",
          "Recoverable",
        ].map((name) => (
          <button
            key={name}
            className={filter === name ? "active" : ""}
            onClick={() => setFilter(name)}
          >
            {name}
          </button>
        ))}
      </div>
      <DataTable
        rows={rows}
        columns={columns}
        account={data.account}
        name={streaks ? "streaks" : "channels"}
        hidden={hidden}
        initialSort={[
          { id: "watching", desc: true },
          { id: "favorite", desc: true },
          { id: "points", desc: true },
        ]}
        searchPlaceholder="Find a channel or category..."
        onRow={(row) => onSelect(row.channel)}
      />
    </>
  );
}
