import { useId, useState } from "react";
import { Check, Copy, Info, CircleHelp } from "lucide-react";
import { date, dayBoundary, duration, inputDate, label, number } from "./lib";

export function Badge({
  children,
  tone = "",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <Info size={25} />
      <h3>{title}</h3>
      {children && <p>{children}</p>}
    </div>
  );
}
export function Hint({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  return (
    <span
      className="hint"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={(e) => {
        if (!e.currentTarget.contains(document.activeElement)) setOpen(false);
      }}
    >
      <button
        type="button"
        className="hint-trigger"
        aria-label={`About ${label}`}
        aria-describedby={open ? id : undefined}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setOpen(false);
            e.stopPropagation();
          }
        }}
      >
        <CircleHelp size={13} />
      </button>
      {open && (
        <span id={id} role="tooltip" className="hint-text">
          {children}
        </span>
      )}
    </span>
  );
}
export function SectionHeading({
  title,
  caption,
  children,
}: {
  title: string;
  caption?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        <h2>
          {title}
          {caption && <Hint label={title}>{caption}</Hint>}
        </h2>
      </div>
      {children}
    </div>
  );
}
export function CopyNumber({
  value,
  suffix = "",
}: {
  value: number | null | undefined;
  suffix?: string;
}) {
  const [copied, set] = useState(false);
  return (
    <button
      className="copy-number mono"
      title="Copy exact value"
      disabled={value == null}
      onClick={() => {
        navigator.clipboard
          .writeText(String(value))
          .then(() => {
            set(true);
            setTimeout(() => set(false), 1500);
          })
          .catch(() => set(false));
      }}
    >
      {number(value)}
      {suffix}
      {copied ? <Check size={12} /> : <Copy size={11} />}
    </button>
  );
}
export function Remaining({ at, now }: { at?: number | null; now: number }) {
  return at ? (
    <span
      title={date(at)}
      className={at <= now ? "muted" : at - now < 3600 ? "warning-text" : ""}
    >
      {at <= now ? "Expired" : duration(at - now) + " left"}
    </span>
  ) : (
    <span className="muted">Not available</span>
  );
}
export function Progress({
  value,
  total,
}: {
  value?: number | null;
  total?: number | null;
}) {
  const percent =
    value != null && total ? Math.min(100, (value / total) * 100) : null;
  return (
    <div className="progress-cell">
      <span>
        {percent == null ? "Not available" : Math.round(percent) + "%"}
        <small>
          {value != null && total
            ? ` · ${number(value)} / ${number(total)} min`
            : ""}
        </small>
      </span>
      <div className="progress-track">
        <i style={{ width: (percent ?? 0) + "%" }} />
      </div>
    </div>
  );
}
export function ConfigList({ value }: { value: Record<string, unknown> }) {
  return (
    <dl className="config-list">
      {Object.entries(value)
        .filter(([, v]) => typeof v !== "object" || v === null)
        .map(([k, v]) => (
          <div key={k}>
            <dt>{label(k)}</dt>
            <dd>
              {v == null ? (
                "Not set"
              ) : typeof v === "boolean" ? (
                <Badge tone={v ? "success" : ""}>
                  {v ? "Enabled" : "Disabled"}
                </Badge>
              ) : (
                String(v)
              )}
            </dd>
          </div>
        ))}
    </dl>
  );
}
export function TimeRange({
  value,
  onChange,
  timezone = "Europe/Budapest",
}: {
  value: { start: number; end: number; preset: string };
  onChange: (value: { start: number; end: number; preset: string }) => void;
  timezone?: string;
}) {
  return (
    <div className="time-range">
      <select
        aria-label="Date range"
        value={value.preset}
        onChange={(e) => {
          const preset = e.target.value,
            end = Date.now() / 1000;
          onChange({
            preset,
            end,
            start:
              preset === "custom"
                ? value.start || end - 7 * 86400
                : preset === "all"
                  ? 0
                  : end - Number(preset) * 86400,
          });
        }}
      >
        <option value="1">Last 24 hours</option>
        <option value="7">Last 7 days</option>
        <option value="30">Last 30 days</option>
        <option value="all">All captured history</option>
        <option value="custom">Custom range</option>
      </select>
      {value.preset === "custom" && (
        <>
          <input
            type="date"
            aria-label="Start date"
            value={value.start ? inputDate(value.start, timezone) : ""}
            onChange={(e) => {
              if (Number.isFinite(e.target.valueAsNumber))
                onChange({
                  ...value,
                  start: dayBoundary(e.target.value, timezone),
                });
            }}
          />
          <input
            type="date"
            aria-label="End date"
            value={inputDate(value.end, timezone)}
            onChange={(e) => {
              if (Number.isFinite(e.target.valueAsNumber))
                onChange({
                  ...value,
                  end: dayBoundary(e.target.value, timezone, true),
                });
            }}
          />
        </>
      )}
    </div>
  );
}
