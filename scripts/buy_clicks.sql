-- "Buy" clicks per agent and country (written by functions/api/click.js with the service key; visitors cannot read or write it).
create table if not exists public.buy_clicks (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  agent       text not null check (char_length(agent) <= 20),
  item_id     text check (char_length(item_id) <= 20),
  platform    text check (char_length(platform) <= 10),
  page        text check (char_length(page) <= 120),
  country     text check (char_length(country) <= 2),
  ref         text check (char_length(ref) <= 24)
);
create index if not exists buy_clicks_time_idx on public.buy_clicks (created_at desc);
alter table public.buy_clicks enable row level security;
