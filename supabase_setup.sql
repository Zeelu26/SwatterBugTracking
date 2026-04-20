-- ============================================================
-- SWATTER BUG TRACKING — SUPABASE TABLE SETUP (V2)
-- ============================================================
-- Run this in Supabase SQL Editor → New Query → paste → Run
-- IF YOU RAN V1 BEFORE: uncomment the 4 drop lines below first
-- ============================================================
-- drop table if exists activity_log cascade;
-- drop table if exists comments cascade;
-- drop table if exists bugs cascade;
-- drop table if exists users cascade;
-- ============================================================


-- ── USERS TABLE ─────────────────────────────────────────────
create table if not exists users (
  id bigint generated always as identity primary key,
  name text not null,
  email text unique not null,
  password text not null,
  role text not null default 'user',
  is_active boolean default true,
  created_at timestamptz default now()
);

-- ── BUGS TABLE ──────────────────────────────────────────────
create table if not exists bugs (
  id bigint generated always as identity primary key,
  title text not null,
  description text default '',
  priority text not null default 'medium',
  status text not null default 'open',
  category text default 'other',
  reporter_id bigint not null references users(id),
  assignee_id bigint references users(id),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- ── COMMENTS TABLE ──────────────────────────────────────────
create table if not exists comments (
  id bigint generated always as identity primary key,
  text text not null,
  is_resolution boolean default false,
  bug_id bigint not null references bugs(id) on delete cascade,
  author_id bigint not null references users(id),
  created_at timestamptz default now()
);

-- ── ACTIVITY LOG TABLE ──────────────────────────────────────
create table if not exists activity_log (
  id bigint generated always as identity primary key,
  bug_id bigint not null references bugs(id) on delete cascade,
  user_id bigint not null references users(id),
  action text not null,
  details text default '',
  created_at timestamptz default now()
);

-- ── INDEXES ─────────────────────────────────────────────────
create index if not exists idx_bugs_reporter on bugs(reporter_id);
create index if not exists idx_bugs_assignee on bugs(assignee_id);
create index if not exists idx_bugs_status on bugs(status);
create index if not exists idx_bugs_priority on bugs(priority);
create index if not exists idx_bugs_category on bugs(category);
create index if not exists idx_comments_bug on comments(bug_id);
create index if not exists idx_activity_bug on activity_log(bug_id);
create index if not exists idx_users_role on users(role);

-- ── ROW LEVEL SECURITY ─────────────────────────────────────
alter table users enable row level security;
alter table bugs enable row level security;
alter table comments enable row level security;
alter table activity_log enable row level security;

create policy "Allow all for anon" on users for all using (true) with check (true);
create policy "Allow all for anon" on bugs for all using (true) with check (true);
create policy "Allow all for anon" on comments for all using (true) with check (true);
create policy "Allow all for anon" on activity_log for all using (true) with check (true);
