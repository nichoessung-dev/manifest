-- Visit timing for the Engagement section on /stats (26 Nov 2026). Run once in the Supabase SQL editor; safe to run again.
--
-- One row per visit (one browser tab, ended by 30 minutes without activity). Written only by functions/api/visit.js with
-- the service key, through log_visit() below. Visitors cannot read or write the table: RLS is on with no policies, and
-- anon / authenticated have no grants on the table or the functions. The visit id is a random UUID made in the tab
-- (sessionStorage "pc.visit"), not linked to an account, an IP address, a cookie or anything else. No IP, user agent,
-- country or user id is stored. scripts/bake_stats.py reads only the aggregates (visit_summary, visit_daily) and deletes
-- rows older than 90 days (purge_site_visits).

create table if not exists public.site_visits (
  sid         uuid primary key,
  started_at  timestamptz not null default now(),
  last_at     timestamptz not null default now(),
  active_s    integer  not null default 0 check (active_s between 0 and 14400),   -- visible, not idle seconds (max 4 h)
  pages       smallint not null default 1 check (pages between 0 and 500),        -- page loads and in-app page changes
  finds       smallint not null default 0 check (finds between 0 and 500),        -- finds opened
  find_s      integer  not null default 0 check (find_s between 0 and 14400),     -- seconds spent on finds, in all
  find_n      smallint not null default 0 check (find_n between 0 and 500),       -- finds that were timed (1 s or more)
  buys        smallint not null default 0 check (buys between 0 and 200),         -- "Buy" clicks on agent links
  entry       text check (char_length(entry) <= 120),                             -- path of the first page, no query
  return_visit boolean not null default false,                                     -- this browser had site activity before
  source      text check (char_length(source) <= 23)                              -- the visit source track.js already works out
);
create index if not exists site_visits_started_idx on public.site_visits (started_at);
alter table public.site_visits enable row level security;
revoke all on public.site_visits from anon, authenticated;

-- Insert a visit, or raise its counters. The browser sends running totals, so the larger value wins and a late or repeated
-- beacon can never lower a number. The first page, source and returning flag are kept from the first beacon.
-- A visit is only updated for 12 hours after it started.
create or replace function public.log_visit(p_sid uuid, p_active integer, p_pages integer, p_finds integer, p_find_s integer,
  p_find_n integer, p_buys integer, p_entry text, p_returning boolean, p_source text)
returns void language sql security invoker set search_path = public as $$
  insert into public.site_visits as v (sid, active_s, pages, finds, find_s, find_n, buys, entry, return_visit, source)
  values (p_sid, least(greatest(coalesce(p_active, 0), 0), 14400), least(greatest(coalesce(p_pages, 1), 1), 500),
          least(greatest(coalesce(p_finds, 0), 0), 500), least(greatest(coalesce(p_find_s, 0), 0), 14400),
          least(greatest(coalesce(p_find_n, 0), 0), 500), least(greatest(coalesce(p_buys, 0), 0), 200),
          nullif(left(coalesce(p_entry, ''), 120), ''), coalesce(p_returning, false), nullif(left(coalesce(p_source, ''), 23), ''))
  on conflict (sid) do update set
    active_s = greatest(v.active_s, excluded.active_s), pages = greatest(v.pages, excluded.pages),
    finds = greatest(v.finds, excluded.finds), find_s = greatest(v.find_s, excluded.find_s),
    find_n = greatest(v.find_n, excluded.find_n), buys = greatest(v.buys, excluded.buys), last_at = now()
  where v.started_at > now() - interval '12 hours';
$$;

-- Everything the Engagement section shows for one period [p_from, p_to): counts, average and median visit length,
-- the visit length buckets, and the 25 most common first pages. Aggregates only.
create or replace function public.visit_summary(p_from timestamptz, p_to timestamptz)
returns jsonb language sql stable security invoker set search_path = public as $$
  with v as (select * from public.site_visits where started_at >= p_from and started_at < p_to)
  select jsonb_build_object(
    'visits', (select count(*) from v),
    'avg_s', (select round(avg(active_s)::numeric, 1) from v),
    'median_s', (select percentile_cont(0.5) within group (order by active_s) from v),
    'bounce', (select count(*) from v where active_s < 10),
    'pages', (select coalesce(sum(pages), 0) from v),
    'finds', (select coalesce(sum(finds), 0) from v),
    'find_s', (select coalesce(sum(find_s), 0) from v),
    'find_n', (select coalesce(sum(find_n), 0) from v),
    'buys', (select coalesce(sum(buys), 0) from v),
    'buy_visits', (select count(*) from v where buys > 0),
    'returning', (select count(*) from v where return_visit),
    'ret_median_s', (select percentile_cont(0.5) within group (order by active_s) from v where return_visit),
    'new_median_s', (select percentile_cont(0.5) within group (order by active_s) from v where not return_visit),
    'hist', (select jsonb_build_array(
        count(*) filter (where active_s < 10), count(*) filter (where active_s >= 10 and active_s < 30),
        count(*) filter (where active_s >= 30 and active_s < 60), count(*) filter (where active_s >= 60 and active_s < 180),
        count(*) filter (where active_s >= 180 and active_s < 600), count(*) filter (where active_s >= 600)) from v),
    'entries', (select coalesce(jsonb_agg(jsonb_build_array(entry, n, med, b) order by n desc, entry), '[]'::jsonb) from (
        select coalesce(entry, '') as entry, count(*) as n, percentile_cont(0.5) within group (order by active_s) as med,
               count(*) filter (where active_s < 10) as b
        from v group by 1 order by 2 desc, 1 limit 25) e),
    'first', (select min(started_at) from public.site_visits)
  );
$$;

-- Per UTC day since p_from: visits, average and median length, bounces, visits with a buy click.
create or replace function public.visit_daily(p_from timestamptz)
returns jsonb language sql stable security invoker set search_path = public as $$
  select coalesce(jsonb_agg(jsonb_build_array(d, n, a, m, b, bv) order by d), '[]'::jsonb) from (
    select (started_at at time zone 'utc')::date as d, count(*) as n, round(avg(active_s)::numeric, 1) as a,
           percentile_cont(0.5) within group (order by active_s) as m,
           count(*) filter (where active_s < 10) as b, count(*) filter (where buys > 0) as bv
    from public.site_visits where started_at >= p_from group by 1) x;
$$;

-- Retention: rows older than p_days (the bake keeps 90). p_dry = true only counts them.
create or replace function public.purge_site_visits(p_days integer, p_dry boolean default true)
returns integer language plpgsql security invoker set search_path = public as $$
declare n integer;
begin
  if p_dry then
    select count(*) into n from public.site_visits where started_at < now() - make_interval(days => greatest(p_days, 30));
  else
    delete from public.site_visits where started_at < now() - make_interval(days => greatest(p_days, 30));
    get diagnostics n = row_count;
  end if;
  return n;
end $$;

-- Only the service key (functions/api/visit.js and the Stats job) may call these.
revoke execute on function public.log_visit(uuid, integer, integer, integer, integer, integer, integer, text, boolean, text) from public, anon, authenticated;
revoke execute on function public.visit_summary(timestamptz, timestamptz) from public, anon, authenticated;
revoke execute on function public.visit_daily(timestamptz) from public, anon, authenticated;
revoke execute on function public.purge_site_visits(integer, boolean) from public, anon, authenticated;
grant execute on function public.log_visit(uuid, integer, integer, integer, integer, integer, integer, text, boolean, text) to service_role;
grant execute on function public.visit_summary(timestamptz, timestamptz) to service_role;
grant execute on function public.visit_daily(timestamptz) to service_role;
grant execute on function public.purge_site_visits(integer, boolean) to service_role;
grant select, insert, update, delete on public.site_visits to service_role;

notify pgrst, 'reload schema';
