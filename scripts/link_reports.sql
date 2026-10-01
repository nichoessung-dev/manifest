-- Dead-link reports from the product drawer ("Report broken link").
-- index.html reportLink() inserts here with the anon/publishable key; until this
-- is applied the insert 404s (PGRST205) and the drawer shows the "couldn't send" message.
-- Apply once in Supabase -> SQL editor.
create table if not exists public.link_reports (
  id          bigint generated always as identity primary key,
  product_id  text not null check (char_length(product_id) <= 64),
  platform    text check (char_length(platform) <= 32),
  item_id     text check (char_length(item_id) <= 64),
  user_id     uuid default auth.uid(),
  created_at  timestamptz not null default now()
);
create index if not exists link_reports_product_idx on public.link_reports (product_id, created_at desc);

alter table public.link_reports enable row level security;

-- anyone (signed in or not) may file a report; nobody can read them through the API
drop policy if exists "link_reports insert" on public.link_reports;
create policy "link_reports insert" on public.link_reports
  for insert to anon, authenticated
  with check (user_id is null or user_id = auth.uid());

grant insert on public.link_reports to anon, authenticated;
