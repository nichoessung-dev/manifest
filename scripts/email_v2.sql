-- Email v2 (26 Nov 2026): what scripts/mailer.py, functions/e/[[path]].js and functions/api/email-hook.js need.
-- Run once in Supabase: SQL editor, paste, Run. Safe to run again (every step checks first).

-- 1. Every email we send: one row per recipient per email.
create table if not exists public.email_sends (
  id          uuid primary key,                 -- a UUIDv7 made by mailer.py: the send time is inside the id
  batch_id    uuid,                             -- shared by every recipient of the same email, version and day: the
                                                -- id in its tracked links (so clicks are counted per email, not per person)
  member_id   uuid,                             -- profiles.id
  stream      text not null,                    -- onboarding | newsletter | alerts | winback | service
  template    text not null,                    -- w0, w1, w2, w3, picks, alert, winback1, winback2, ...
  campaign    text not null,                    -- the utm_campaign on our links (welcome, ordering, mycnbox, newsletter, saved)
  variant     text,                             -- A/B arm, for example "w0-subject:b"
  subject     text,
  provider    text,                             -- plunk
  provider_id text,                             -- the provider's message id, to match its webhook events
  status      text not null default 'sent',     -- sent | failed
  error       text,
  created_at  timestamptz not null default now()
);
create index if not exists email_sends_member   on public.email_sends (member_id, created_at desc);
create index if not exists email_sends_template on public.email_sends (template, created_at desc);
create index if not exists email_sends_provider on public.email_sends (provider_id);
create index if not exists email_sends_batch    on public.email_sends (batch_id);

-- 2. What happened to them: clicks from our own tracker (per email and link, not per person), and delivery, bounces and
--    complaints from the provider.
create table if not exists public.email_events (
  id         bigint generated always as identity primary key,
  send_id    uuid,                              -- the id in the link: an email_sends.batch_id (default, counted per email)
                                                -- or an email_sends.id when per-member tracking is switched on
  member_id  uuid,                              -- only for provider events about one recipient (bounce, complaint)
  type       text not null,                     -- click | open | delivered | bounce | complaint | unsubscribe | failed
  link       text,                              -- for clicks: the block in the email (coupon, card-3, footer ...)
  ua         text,
  asn        integer,                           -- the network the click came from (mail scanners sit on a few known ones)
  country    text,
  meta       jsonb,
  dedupe     text unique,                       -- a provider event id, so a webhook sent twice is stored once
  created_at timestamptz not null default now()
);
create index if not exists email_events_send    on public.email_events (send_id);
create index if not exists email_events_created on public.email_events (created_at desc);
create index if not exists email_events_type    on public.email_events (type, created_at desc);

-- 3. Addresses that must never get email again (hard bounce, spam complaint, or by hand).
create table if not exists public.email_suppression (
  email      text primary key,                  -- lowercase
  reason     text not null,                     -- hard_bounce | complaint | soft_bounce | manual
  source     text,                              -- plunk | brevo | site
  detail     text,
  created_at timestamptz not null default now()
);

-- 4. Per-member email state on profiles.
alter table public.profiles
  add column if not exists email_last_at      timestamptz,   -- last email of any kind
  add column if not exists email_news_at      timestamptz,   -- last weekly picks
  add column if not exists email_alert_at     timestamptz,   -- last saved-find alert
  add column if not exists email_click_at     timestamptz,   -- last human click in an email
  add column if not exists email_freq         text default 'weekly',   -- weekly | alerts (alerts only) | paused
  add column if not exists email_paused_until timestamptz,
  add column if not exists onboard_step       smallint default 0,      -- welcome series: last email sent (0 = none)
  add column if not exists onboard_at         timestamptz,             -- when that email went out
  add column if not exists email_sunset_at    timestamptz,             -- marketing stopped for inactivity (a visit or click resumes it)
  add column if not exists unsubscribed_at    timestamptz,
  add column if not exists unsub_source       text,                    -- header | link | complaint | settings
  add column if not exists style              text,                    -- the welcome tour's style pick (old, archive, street, women, or all)
  add column if not exists email_track        boolean default false,   -- yes to "Measure my email clicks" (personal ids in links)
  add column if not exists email_personal     boolean default false,   -- yes to "Personalise my emails from finds I view"
  add column if not exists email_consents     jsonb default '[]'::jsonb; -- every yes and no: [{what, value, at, text_version, via}]

-- 5. profiles.agent: the site has 18 agents now. Drop the old check that allowed only a few, so a pick saves.
do $$
declare c text;
begin
  for c in select conname from pg_constraint
           where conrelid = 'public.profiles'::regclass and contype = 'c' and pg_get_constraintdef(oid) ilike '%agent%'
  loop
    execute format('alter table public.profiles drop constraint %I', c);
  end loop;
end $$;

-- 6. Private tables: row level security on and no policies, so only the service role (the GitHub jobs and the
-- Cloudflare functions) can read or write them. Nothing here is visible to visitors.
alter table public.email_sends       enable row level security;
alter table public.email_events      enable row level security;
alter table public.email_suppression enable row level security;

-- 7. Keep click and open events for 13 months, sends for 25 (scripts/mailer.py calls this once a day).
create or replace function public.purge_email_events() returns void language sql security definer set search_path = public as $$
  delete from public.email_events where created_at < now() - interval '13 months';
  delete from public.email_sends  where created_at < now() - interval '25 months';
$$;
revoke all on function public.purge_email_events() from public, anon, authenticated;

-- 8. Site visits: phone, tablet or computer, for /stats (26 Nov 2026). functions/api/visit.js sends p_device; it falls
-- back to the old call until this has run. The old 10-argument log_visit is dropped so the API has one version.
alter table public.site_visits add column if not exists device text;   -- phone | tablet | desktop
drop function if exists public.log_visit(uuid, integer, integer, integer, integer, integer, integer, text, boolean, text);
create or replace function public.log_visit(p_sid uuid, p_active integer, p_pages integer, p_finds integer, p_find_s integer,
  p_find_n integer, p_buys integer, p_entry text, p_returning boolean, p_source text, p_device text default null)
returns void language sql security invoker set search_path = public as $$
  insert into public.site_visits as v (sid, active_s, pages, finds, find_s, find_n, buys, entry, return_visit, source, device)
  values (p_sid, least(greatest(coalesce(p_active, 0), 0), 14400), least(greatest(coalesce(p_pages, 1), 1), 500),
          least(greatest(coalesce(p_finds, 0), 0), 500), least(greatest(coalesce(p_find_s, 0), 0), 14400),
          least(greatest(coalesce(p_find_n, 0), 0), 500), least(greatest(coalesce(p_buys, 0), 0), 200),
          nullif(left(coalesce(p_entry, ''), 120), ''), coalesce(p_returning, false), nullif(left(coalesce(p_source, ''), 23), ''),
          case when p_device in ('phone', 'tablet', 'desktop') then p_device end)
  on conflict (sid) do update set
    active_s = greatest(v.active_s, excluded.active_s), pages = greatest(v.pages, excluded.pages),
    finds = greatest(v.finds, excluded.finds), find_s = greatest(v.find_s, excluded.find_s),
    find_n = greatest(v.find_n, excluded.find_n), buys = greatest(v.buys, excluded.buys), last_at = now(),
    device = coalesce(v.device, excluded.device)
  where v.started_at > now() - interval '12 hours';
$$;
