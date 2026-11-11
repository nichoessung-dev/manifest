-- Partner link swaps (/partner, 11 Nov 2026). Run once in Supabase > SQL editor.
-- A partner (a shop owner you add below) proposes "send the Buy buttons of find X to my item Y"; you approve it on /partner.
-- Approved swaps reach the app at once (approved_swaps()) and the server pages through the Swaps workflow.

create table if not exists public.partners (
  email text primary key,
  role text not null default 'partner' check (role in ('partner', 'owner')),
  created_at timestamptz not null default now()
);
alter table public.partners enable row level security;   -- no policies: read only through my_partner_role() and the service key

create table if not exists public.link_swaps (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  pid text not null check (pid ~ '^[0-9A-Za-z_-]{1,40}$'),
  platform text not null check (platform in ('weidian', 'taobao', '1688')),
  item_id text not null check (item_id ~ '^[0-9]{5,20}$'),
  note text check (char_length(note) <= 300),
  by_email text not null default lower(auth.jwt() ->> 'email'),
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected', 'removed')),
  decided_at timestamptz
);
alter table public.link_swaps enable row level security;
create index if not exists link_swaps_pid on public.link_swaps (pid, decided_at desc);

-- the signed-in person's role: 'owner', 'partner' or null
create or replace function public.my_partner_role() returns text
language sql stable security definer set search_path = public as $$
  select role from public.partners where email = lower(auth.jwt() ->> 'email')
$$;
revoke all on function public.my_partner_role() from public;
grant execute on function public.my_partner_role() to authenticated;

-- the swaps that are live: per find, the latest decision, if that was an approval. No emails or notes.
create or replace function public.approved_swaps() returns table (pid text, platform text, item_id text)
language sql stable security definer set search_path = public as $$
  select pid, platform, item_id from (
    select distinct on (pid) pid, platform, item_id, status from public.link_swaps
    where status in ('approved', 'removed') order by pid, decided_at desc nulls last, id desc
  ) last where status = 'approved'
$$;
revoke all on function public.approved_swaps() from public;
grant execute on function public.approved_swaps() to anon, authenticated;

drop policy if exists "swaps read" on public.link_swaps;
create policy "swaps read" on public.link_swaps for select to authenticated
  using (public.my_partner_role() = 'owner' or (public.my_partner_role() = 'partner' and by_email = lower(auth.jwt() ->> 'email')));
drop policy if exists "swaps add" on public.link_swaps;
create policy "swaps add" on public.link_swaps for insert to authenticated
  with check (public.my_partner_role() in ('partner', 'owner') and status = 'pending' and decided_at is null
              and by_email = lower(auth.jwt() ->> 'email'));
drop policy if exists "swaps decide" on public.link_swaps;
create policy "swaps decide" on public.link_swaps for update to authenticated
  using (public.my_partner_role() = 'owner') with check (public.my_partner_role() = 'owner');
drop policy if exists "swaps withdraw" on public.link_swaps;
create policy "swaps withdraw" on public.link_swaps for delete to authenticated
  using (status = 'pending' and by_email = lower(auth.jwt() ->> 'email'));

-- Who may use /partner. Put in your own email (owner: approves) and your friend's (partner: proposes), then run.
-- Run this line again with another email to add more partners.
insert into public.partners (email, role) values
  (lower('YOUR_EMAIL_HERE'), 'owner'),
  (lower('FRIEND_EMAIL_HERE'), 'partner')
on conflict (email) do update set role = excluded.role;
