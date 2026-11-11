-- Partner link swaps (/partner, 11 Nov 2026, code version). Run once in Supabase > SQL editor.
-- A partner (a shop owner) opens /partner, types his code, and proposes "send the Buy buttons of find X to my item Y".
-- The owner opens /partner with the owner code and approves. Approved swaps reach the app at once (approved_swaps())
-- and the server pages through the Swaps workflow. Everything goes through the functions below; the tables have
-- row level security with no policies, so nobody can read them directly (codes included).

create table if not exists public.partner_codes (
  code text primary key check (char_length(code) >= 12),
  name text not null,
  role text not null default 'partner' check (role in ('partner', 'owner')),
  created_at timestamptz not null default now()
);
alter table public.partner_codes enable row level security;

create table if not exists public.link_swaps (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  pid text not null check (pid ~ '^[0-9A-Za-z_-]{1,40}$'),
  platform text not null check (platform in ('weidian', 'taobao', '1688')),
  item_id text not null check (item_id ~ '^[0-9]{5,20}$'),
  note text check (char_length(note) <= 300),
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected', 'removed')),
  decided_at timestamptz
);
alter table public.link_swaps add column if not exists by_name text;
alter table public.link_swaps add column if not exists by_code text;
alter table public.link_swaps enable row level security;
create index if not exists link_swaps_pid on public.link_swaps (pid, decided_at desc);
-- leftovers of the first (Google sign-in) version, if it was ever run
drop policy if exists "swaps read" on public.link_swaps;
drop policy if exists "swaps add" on public.link_swaps;
drop policy if exists "swaps decide" on public.link_swaps;
drop policy if exists "swaps withdraw" on public.link_swaps;
do $$ begin
  if exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = 'link_swaps' and column_name = 'by_email') then
    alter table public.link_swaps alter column by_email drop not null;
    alter table public.link_swaps alter column by_email drop default;
  end if;
end $$;

-- who a code belongs to (empty when the code is wrong)
create or replace function public.partner_whoami(p_code text) returns table (name text, role text)
language sql stable security definer set search_path = public as $$
  select c.name, c.role from public.partner_codes c where c.code = p_code
$$;

-- swaps: a partner sees his own, the owner sees all
create or replace function public.partner_list(p_code text)
returns table (id bigint, created_at timestamptz, pid text, platform text, item_id text, note text, by_name text, status text, decided_at timestamptz)
language plpgsql stable security definer set search_path = public as $$
declare me public.partner_codes;
begin
  select * into me from public.partner_codes c where c.code = p_code;
  if not found then raise exception 'wrong code'; end if;
  return query select s.id, s.created_at, s.pid, s.platform, s.item_id, s.note, s.by_name, s.status, s.decided_at
    from public.link_swaps s where me.role = 'owner' or s.by_code = p_code order by s.created_at desc limit 500;
end $$;

create or replace function public.partner_submit(p_code text, p_pid text, p_platform text, p_item text, p_note text) returns bigint
language plpgsql volatile security definer set search_path = public as $$
declare me public.partner_codes; new_id bigint;
begin
  select * into me from public.partner_codes c where c.code = p_code;
  if not found then raise exception 'wrong code'; end if;
  if (select count(*) from public.link_swaps s where s.by_code = p_code and s.status = 'pending') >= 500 then
    raise exception 'too many swaps waiting for approval'; end if;
  insert into public.link_swaps (pid, platform, item_id, note, by_name, by_code)
    values (p_pid, p_platform, p_item, nullif(left(coalesce(p_note, ''), 300), ''), me.name, p_code) returning id into new_id;
  return new_id;
end $$;

-- owner only: approved, rejected, or removed (undo an approved swap)
create or replace function public.partner_decide(p_code text, p_id bigint, p_status text) returns void
language plpgsql volatile security definer set search_path = public as $$
begin
  if not exists (select 1 from public.partner_codes c where c.code = p_code and c.role = 'owner') then raise exception 'owner code needed'; end if;
  if p_status not in ('approved', 'rejected', 'removed') then raise exception 'bad status'; end if;
  update public.link_swaps set status = p_status, decided_at = now() where id = p_id;
end $$;

-- a partner takes back a swap that is still waiting
create or replace function public.partner_withdraw(p_code text, p_id bigint) returns void
language plpgsql volatile security definer set search_path = public as $$
begin
  delete from public.link_swaps where id = p_id and by_code = p_code and status = 'pending';
end $$;

-- the swaps that are live: per find, the latest decision, if that was an approval. No names, codes or notes.
create or replace function public.approved_swaps() returns table (pid text, platform text, item_id text)
language sql stable security definer set search_path = public as $$
  select l.pid, l.platform, l.item_id from (
    select distinct on (s.pid) s.pid, s.platform, s.item_id, s.status from public.link_swaps s
    where s.status in ('approved', 'removed') order by s.pid, s.decided_at desc nulls last, s.id desc
  ) l where l.status = 'approved'
$$;

drop function if exists public.my_partner_role();
revoke all on function public.partner_whoami(text), public.partner_list(text), public.partner_submit(text, text, text, text, text),
  public.partner_decide(text, bigint, text), public.partner_withdraw(text, bigint), public.approved_swaps() from public;
grant execute on function public.partner_whoami(text), public.partner_list(text), public.partner_submit(text, text, text, text, text),
  public.partner_decide(text, bigint, text), public.partner_withdraw(text, bigint), public.approved_swaps() to anon, authenticated;

-- The codes. Use long random codes (12+ characters). To add another partner later, run just this line with a new code and name.
-- To take a code away: delete from public.partner_codes where code = '...';
insert into public.partner_codes (code, name, role) values
  ('OWNER_CODE_HERE', 'Owner', 'owner'),
  ('PARTNER_CODE_HERE', 'Partner', 'partner')
on conflict (code) do nothing;
