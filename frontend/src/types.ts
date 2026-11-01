export type Freshness = {
  checked_at?: number;
  source?: string;
  error?: string;
  stale?: boolean;
};
export type Recovery = {
  days: number;
  expires_at: number;
  recoverable: boolean;
  missed_broadcasts: string[];
};
export type Job = {
  state: string;
  at: number;
  method?: string;
  replay_url?: string;
  next_retry_at?: number;
};
export type Weekly = {
  event_id: string;
  ends_at: number;
  days_visited: number;
  accumulated_weeks: number;
  reward_count: number;
  visited_today: boolean;
  earned_this_week: boolean;
};
export type Config = Record<
  string,
  boolean | number | string | null | Record<string, unknown>
>;
export type Channel = {
  channel: string;
  channel_id: string;
  points: number | null;
  earned_today: number;
  balance_change: number | null;
  balance_observed_since?: number;
  reported_period_points: Record<string, number | undefined>;
  online: boolean;
  watching: boolean;
  reason: string;
  favorite: boolean;
  streak: number | null;
  streak_status: string;
  recovery: Recovery | null;
  recoverable: boolean;
  recovery_job: Job | null;
  weekly: Weekly | null;
  subscription_tier: number | string | null;
  chat_banned: boolean;
  points_limit: number | null;
  last_activity: number | null;
  follow_date: string | null;
  title: string | null;
  game: string | null;
  viewers: number | null;
  stream_started_at: number | null;
  settings: Config;
  freshness: Record<string, Freshness>;
  needs_attention: boolean;
  attempts: number;
  verified_streak: number | null;
  last_verification_at: number | null;
};
export type Prediction = {
  id: string;
  channel: string;
  prediction: string;
  outcome: string;
  stake: number;
  result: string | null;
  payout: number | null;
  net: number | null;
  source: string;
  placed_at: number | null;
  resolved_at: number | null;
  recovered: boolean;
  notification_sent: boolean;
};
export type Drop = {
  id: string;
  campaign_id?: string;
  campaign: string;
  game?: string;
  name: string;
  reward?: string;
  minutes?: number;
  required_minutes?: number;
  claimed: boolean | null;
  preconditions_met?: boolean;
  ends_at?: number;
  claimed_at?: number;
};
export type Refresh = {
  id?: string;
  state: string;
  completed?: number;
  total?: number;
  completed_at?: number;
  next_manual_at: number;
  next_auto_at: number;
  backoff_until: number;
  requests: number;
  observer_requests: number;
  cache_hits: number;
  errors?: { channel?: string; group: string; message: string }[];
  current?: { channel: string; group: string };
};
export type Activity = {
  id: string;
  at: number;
  channel?: string;
  kind: string;
  message: string;
  details: Record<string, unknown>;
};
export type Sample = {
  at: number;
  start: number;
  balance: number;
  low: number;
  high: number;
};
export type LogLine = { at?: string; level: string; message: string };
export type Snapshot = {
  account: string;
  generated_at: number;
  timezone: string;
  running: boolean;
  session_id: string;
  uptime: number;
  channels: Channel[];
  predictions: Prediction[];
  drops: Drop[];
  campaigns: {
    id: string;
    name: string;
    game?: string;
    ends_at?: number;
    status?: string;
  }[];
  account_freshness: Record<
    string,
    { fetched_at?: number; error?: string; source?: string }
  >;
  summary: {
    online: number;
    watching: number;
    balance: number;
    earned_today: number;
    balance_change: number | null;
    balance_observed_since?: number;
    reported_period_points: Record<string, number | undefined>;
    recoverable: number;
    confirmed: number;
    wins: number;
    losses: number;
    refunds: number;
    net: number;
    win_rate: number | null;
  };
  refresh: Refresh;
  system: {
    cpu_percent: number;
    memory_mb: number;
    threads: number;
    connections: { name: string; state: string }[];
    history_error?: string;
    refresh_seconds: number;
    cooldown_seconds: number;
    request_interval_seconds: number;
    selection_at?: number;
    priorities: string[];
    streak_slots: number;
    settings: Config;
    capture_started_at: number;
  };
};
