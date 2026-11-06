begin;
create table public.dashboards (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  database_id uuid not null,
  author_id uuid not null default auth.uid(),
  title text not null check(length(trim(title)) between 1 and 100),
  shared boolean not null default false,
  revision bigint not null default 1,
  updated_at timestamptz not null default now(),
  unique(id,database_id),
  foreign key(org_id,database_id) references public.target_databases(org_id,id) on delete cascade,
  foreign key(org_id,author_id) references public.memberships(org_id,user_id) on delete cascade
);
alter table public.saved_queries add unique(id,database_id);
create table public.dashboard_panels (
  dashboard_id uuid not null,
  database_id uuid not null,
  query_id uuid not null,
  position integer not null default 0 check(position>=0),
  primary key(dashboard_id,query_id),
  foreign key(dashboard_id,database_id) references public.dashboards(id,database_id) on delete cascade,
  foreign key(query_id,database_id) references public.saved_queries(id,database_id) on delete cascade
);
create index dashboard_org on public.dashboards(org_id,updated_at desc);
create index panels_query on public.dashboard_panels(query_id);
create trigger dashboard_revision before update on public.dashboards
for each row execute function morphy_private.bump_saved_query_revision();
alter table public.dashboards enable row level security;
alter table public.dashboard_panels enable row level security;
revoke all on public.dashboards,public.dashboard_panels from public,anon,authenticated;
grant select,delete on public.dashboards,public.dashboard_panels to authenticated;
grant insert(id,org_id,database_id,title,shared),update(title,shared) on public.dashboards to authenticated;
grant insert(dashboard_id,database_id,query_id,position),update(position) on public.dashboard_panels to authenticated;

create policy dashboard_read on public.dashboards for select to authenticated using (
  (shared or author_id=(select auth.uid()))
  and public.effective_permission(database_id)->>'mode' in ('VIEW_ONLY','QUERY_ONLY','SCHEMA_EDIT')
);
create policy dashboard_author on public.dashboards for all to authenticated using (
  author_id=(select auth.uid()) and public.effective_permission(database_id)->>'mode' in ('QUERY_ONLY','SCHEMA_EDIT')
) with check (
  author_id=(select auth.uid()) and public.effective_permission(database_id)->>'mode' in ('QUERY_ONLY','SCHEMA_EDIT')
);
create policy panel_read on public.dashboard_panels for select to authenticated using (
  exists(select from public.dashboards d where d.id=dashboard_id)
  and exists(select from public.saved_queries q where q.id=query_id)
);
create policy panel_author on public.dashboard_panels for all to authenticated using (
  exists(select from public.dashboards d where d.id=dashboard_id and d.author_id=(select auth.uid()))
  and exists(select from public.saved_queries q where q.id=query_id)
  and public.effective_permission(database_id)->>'mode' in ('QUERY_ONLY','SCHEMA_EDIT')
) with check (
  exists(select from public.dashboards d where d.id=dashboard_id and d.author_id=(select auth.uid()))
  and exists(select from public.saved_queries q where q.id=query_id)
  and public.effective_permission(database_id)->>'mode' in ('QUERY_ONLY','SCHEMA_EDIT')
);
commit;
