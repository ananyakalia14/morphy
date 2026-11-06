begin;

create table public.saved_queries (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  database_id uuid not null,
  author_id uuid not null default auth.uid(),
  title text not null check (length(trim(title)) between 1 and 100),
  sql_text text not null check (length(trim(sql_text)) between 1 and 12000),
  shared boolean not null default false,
  revision bigint not null default 1,
  updated_at timestamptz not null default now(),
  foreign key (org_id,database_id) references public.target_databases(org_id,id) on delete cascade,
  foreign key (org_id,author_id) references public.memberships(org_id,user_id) on delete cascade
);
create index saved_queries_browser on public.saved_queries(org_id,updated_at desc,id);

create function morphy_private.bump_saved_query_revision() returns trigger
language plpgsql set search_path='' as $$
begin
  new.revision := old.revision + 1;
  new.updated_at := clock_timestamp();
  return new;
end $$;
create trigger saved_query_revision before update on public.saved_queries
for each row execute function morphy_private.bump_saved_query_revision();

alter table public.saved_queries enable row level security;
revoke all on public.saved_queries from public,anon,authenticated;
grant select,delete on public.saved_queries to authenticated;
grant insert(id,org_id,database_id,title,sql_text,shared),
      update(title,sql_text,shared) on public.saved_queries to authenticated;

create policy saved_query_read on public.saved_queries for select to authenticated using (
  (shared or author_id=(select auth.uid()))
  and public.effective_permission(database_id)->>'mode' in ('VIEW_ONLY','QUERY_ONLY','SCHEMA_EDIT')
);
create policy saved_query_create on public.saved_queries for insert to authenticated with check (
  author_id=(select auth.uid())
  and public.effective_permission(database_id)->>'mode' in ('QUERY_ONLY','SCHEMA_EDIT')
);
create policy saved_query_edit on public.saved_queries for update to authenticated using (
  author_id=(select auth.uid())
  and public.effective_permission(database_id)->>'mode' in ('QUERY_ONLY','SCHEMA_EDIT')
) with check (
  author_id=(select auth.uid())
  and public.effective_permission(database_id)->>'mode' in ('QUERY_ONLY','SCHEMA_EDIT')
);
create policy saved_query_delete on public.saved_queries for delete to authenticated using (
  author_id=(select auth.uid())
  and public.effective_permission(database_id)->>'mode' in ('QUERY_ONLY','SCHEMA_EDIT')
);
commit;
