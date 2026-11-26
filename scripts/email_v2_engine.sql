-- Email v2 sending engine (26 Nov 2026): what scripts/mailer.py needs on top of scripts/email_v2.sql.
-- Run once in Supabase, after email_v2.sql: SQL editor, paste, Run. Safe to run again (every step checks first).

-- 1. The re-run guard. Each email has a campaign key: the template for the welcome series (w0, w1 ...), a dated key for
--    the repeating ones (alert-2026-11-26, picks-2026-11-26, wb1-<last visit day>). One member never gets the same
--    template and key twice: a second insert fails, and mailer.py then skips that member. A failed send does not count,
--    so it can be tried again (at most 3 times). The row is written before the provider is called ('sending').
--    meta: the finds an email showed ({"items": [...]}, so weekly picks never repeat them) and the provider's contact id.
alter table public.email_sends
  add column if not exists campaign_key text,
  add column if not exists meta         jsonb;
create unique index if not exists email_sends_once
  on public.email_sends (member_id, template, campaign_key) where status <> 'failed';
create index if not exists email_sends_key on public.email_sends (campaign_key);

-- 2. A little state between runs: which daily passes are done ("passes"), the last snapshot of sold-out finds and QC
--    photo counts ("alert_snapshot", to see back in stock and new QC photos) and the recent find news ("alert_events").
create table if not exists public.email_state (
  key        text primary key,
  value      jsonb not null,
  updated_at timestamptz not null default now()
);
alter table public.email_state enable row level security;   -- no policies: the service role (the GitHub job) only
