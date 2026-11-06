begin;
set local search_path = pg_catalog, public, extensions;
create extension if not exists pg_trgm with schema extensions;
create schema if not exists morphy_private;
revoke all on schema morphy_private from public, anon, authenticated;
create type public.access_mode as enum ('NONE','VIEW_ONLY','QUERY_ONLY','SCHEMA_EDIT');

create table public.profiles (
  id uuid primary key references auth.users on delete cascade,
  username text not null check (username ~ '^[a-z][a-z0-9_]{2,23}$'),
  display_name text not null check (length(trim(display_name)) between 1 and 80),
  avatar_path text check (avatar_path is null or avatar_path = id::text || '/profile.webp'),
  created_at timestamptz not null default now()
);
create unique index profiles_handle on public.profiles(lower(username));
create index profiles_typeahead on public.profiles using gin(username extensions.gin_trgm_ops);
create table public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check(length(trim(name)) between 1 and 80),
  owner_id uuid not null references public.profiles,
  created_at timestamptz not null default now()
);
create table public.roles (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations on delete cascade,
  name text not null check(length(trim(name)) between 1 and 40),
  builtin boolean not null default false,
  unique(org_id,name), unique(org_id,id)
);
create table public.memberships (
  org_id uuid not null references public.organizations on delete cascade,
  user_id uuid not null references public.profiles on delete cascade,
  role_id uuid not null, primary key(org_id,user_id),
  foreign key(org_id,role_id) references public.roles(org_id,id)
);
alter table public.organizations add constraint owner_is_member foreign key(id,owner_id)
  references public.memberships(org_id,user_id) deferrable initially deferred;
create table public.invitations (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations on delete cascade,
  user_id uuid not null references public.profiles on delete cascade,
  role_id uuid not null, invited_by uuid not null references public.profiles,
  organization_name text not null, status text not null default 'pending' check(status in ('pending','accepted')),
  created_at timestamptz not null default now(), unique(org_id,user_id),
  foreign key(org_id,role_id) references public.roles(org_id,id)
);
create table public.target_databases (
  id uuid primary key default gen_random_uuid(), org_id uuid not null references public.organizations on delete cascade,
  name text not null check(length(trim(name)) between 1 and 80),
  dialect text not null check(dialect in ('postgres','mysql','mariadb','snowflake','bigquery','sqlite','duckdb','clickhouse','mongodb')),
  unique(org_id,id), unique(org_id,name)
);
create table morphy_private.connection_secrets (
  database_id uuid primary key references public.target_databases on delete cascade,
  encrypted_credential bytea not null, key_version text not null
);
create table public.database_permissions (
  id uuid primary key default gen_random_uuid(), org_id uuid not null,
  database_id uuid not null, role_id uuid, user_id uuid, mode public.access_mode not null,
  table_columns jsonb not null default '{}', row_rules jsonb not null default '[]',
  check(num_nonnulls(role_id,user_id)=1),
  foreign key(org_id,database_id) references public.target_databases(org_id,id) on delete cascade,
  foreign key(org_id,role_id) references public.roles(org_id,id) on delete cascade,
  foreign key(org_id,user_id) references public.memberships(org_id,user_id) on delete cascade,
  unique nulls not distinct(database_id,role_id,user_id)
);
create table public.audit_events (
  id bigint generated always as identity primary key, org_id uuid not null references public.organizations on delete cascade,
  actor_id uuid references public.profiles, action text not null, subject_id uuid,
  occurred_at timestamptz not null default now()
);

create function morphy_private.member(o uuid) returns boolean language sql stable security definer set search_path='' as $$
  select exists(select from public.memberships where org_id=o and user_id=(select auth.uid()))
$$;
create function morphy_private.admin(o uuid) returns boolean language sql stable security definer set search_path='' as $$
  select exists(select from public.memberships m join public.roles r on r.id=m.role_id
    where m.org_id=o and m.user_id=(select auth.uid()) and r.builtin and r.name='ADMIN')
$$;
create function morphy_private.require_admin(o uuid) returns void language plpgsql security definer set search_path='' as $$
begin
  perform 1 from public.organizations where id=o for update;
  if not morphy_private.admin(o) then raise exception 'Administrator access required' using errcode='42501'; end if;
end $$;
create function morphy_private.log(o uuid,a text,s uuid) returns void language sql set search_path='' as $$
  insert into public.audit_events(org_id,actor_id,action,subject_id) values(o,auth.uid(),a,s)
$$;

alter table public.profiles enable row level security;
alter table public.organizations enable row level security;
alter table public.roles enable row level security;
alter table public.memberships enable row level security;
alter table public.invitations enable row level security;
alter table public.target_databases enable row level security;
alter table public.database_permissions enable row level security;
alter table public.audit_events enable row level security;
create policy read_self on public.profiles for select to authenticated using(id=(select auth.uid()));
create policy read_organizations on public.organizations for select to authenticated using(morphy_private.member(id));
create policy read_roles on public.roles for select to authenticated using(morphy_private.member(org_id));
create policy read_members on public.memberships for select to authenticated using(morphy_private.member(org_id));
create policy read_invitations on public.invitations for select to authenticated using(user_id=(select auth.uid()) or morphy_private.admin(org_id));
create policy read_databases on public.target_databases for select to authenticated using(morphy_private.admin(org_id));
create policy read_rules on public.database_permissions for select to authenticated using(morphy_private.admin(org_id));
create policy read_audit on public.audit_events for select to authenticated using(morphy_private.admin(org_id));

create function public.claim_profile(handle text, full_name text, avatar text default null) returns void
language sql security definer set search_path='' as $$
  insert into public.profiles(id,username,display_name,avatar_path) values(auth.uid(),lower(trim(handle)),trim(full_name),avatar)
$$;
create function public.username_available(handle text) returns boolean language sql stable security definer set search_path='' as $$
  select lower(trim(handle)) ~ '^[a-z][a-z0-9_]{2,23}$' and not exists(select from public.profiles where lower(username)=lower(trim(handle)))
$$;
create function public.find_people(prefix text) returns table(id uuid,username text,avatar_path text)
language sql stable security definer set search_path='' as $$
  select p.id,p.username,p.avatar_path from public.profiles p where length(prefix) between 2 and 24
  and prefix ~ '^[a-z0-9_]+$' and p.username like replace(prefix,'_','\_') || '%' order by p.username limit 12
$$;
create function public.org_people(o uuid) returns table(user_id uuid,username text,avatar_path text,role_id uuid)
language sql stable security definer set search_path='' as $$
  select p.id,p.username,p.avatar_path,m.role_id from public.memberships m join public.profiles p on p.id=m.user_id
  where m.org_id=o and morphy_private.member(o) order by p.username
$$;
create function public.create_workspace(title text) returns uuid language plpgsql security definer set search_path='' as $$
declare o uuid; r uuid;
begin
  insert into public.organizations(name,owner_id) values(trim(title),auth.uid()) returning id into o;
  insert into public.roles(org_id,name,builtin) select o,n,true from unnest(array['ADMIN','DATA_ENGINEER','ANALYST','VIEWER']) n;
  select id into r from public.roles where org_id=o and name='ADMIN';
  insert into public.memberships values(o,auth.uid(),r);
  perform morphy_private.log(o,'workspace.created',o); return o;
end $$;
create function public.create_role(o uuid,title text) returns void language plpgsql security definer set search_path='' as $$
begin
  perform morphy_private.require_admin(o);
  insert into public.roles(org_id,name) values(o,upper(trim(title)));
  perform morphy_private.log(o,'role.created',o);
end $$;
create function public.invite_person(o uuid,person uuid,r uuid) returns void language plpgsql security definer set search_path='' as $$
begin
  perform morphy_private.require_admin(o);
  if exists(select from public.memberships where org_id=o and user_id=person) then raise exception 'Already a member'; end if;
  insert into public.invitations(org_id,user_id,role_id,invited_by,organization_name)
  select o,person,r,auth.uid(),name from public.organizations where id=o
  on conflict(org_id,user_id) do update set role_id=excluded.role_id where invitations.status='pending';
  perform morphy_private.log(o,'invitation.sent',person);
end $$;
create function public.accept_invitation(inv uuid) returns void language plpgsql security definer set search_path='' as $$
declare i public.invitations;
begin
  select * into strict i from public.invitations where id=inv and user_id=auth.uid() for update;
  if i.status='accepted' then return; end if;
  insert into public.memberships values(i.org_id,i.user_id,i.role_id);
  update public.invitations set status='accepted' where id=inv;
  perform morphy_private.log(i.org_id,'invitation.accepted',i.user_id);
end $$;
create function public.set_member_role(o uuid,person uuid,r uuid) returns void language plpgsql security definer set search_path='' as $$
begin
  perform morphy_private.require_admin(o);
  if exists(select from public.organizations where id=o and owner_id=person) then raise exception 'Transfer ownership first'; end if;
  update public.memberships set role_id=r where org_id=o and user_id=person;
  if not found then raise exception 'Member not found'; end if;
  perform morphy_private.log(o,'member.role_changed',person);
end $$;
create function public.transfer_owner(o uuid,person uuid) returns void language plpgsql security definer set search_path='' as $$
begin
  perform morphy_private.require_admin(o);
  if not exists(select from public.organizations where id=o and owner_id=auth.uid()) then raise exception 'Only the owner may transfer ownership'; end if;
  update public.memberships set role_id=(select id from public.roles where org_id=o and name='ADMIN' and builtin)
  where org_id=o and user_id=person;
  if not found then raise exception 'Select an existing member'; end if;
  update public.organizations set owner_id=person where id=o;
  perform morphy_private.log(o,'ownership.transferred',person);
end $$;
create function public.register_database(o uuid,title text,engine text) returns uuid language plpgsql security definer set search_path='' as $$
declare d uuid;
begin
  perform morphy_private.require_admin(o);
  insert into public.target_databases(org_id,name,dialect) values(o,trim(title),engine) returning id into d;
  perform morphy_private.log(o,'database.registered',d); return d;
end $$;
-- Role maps grant access. User maps can only narrow the effective role grant.
-- Empty table or column sets grant no data access. Row conditions are conjunctive.
create function public.save_permission(o uuid,d uuid,r uuid,person uuid,level public.access_mode,cols jsonb,rules jsonb)
returns void language plpgsql security definer set search_path='' as $$
declare pair record; rule jsonb;
begin
  perform morphy_private.require_admin(o);
  if jsonb_typeof(cols) is distinct from 'object' or jsonb_typeof(rules) is distinct from 'array' then raise exception 'Invalid policy shape'; end if;
  for pair in select * from jsonb_each(cols) loop
    if length(trim(pair.key))=0 or jsonb_typeof(pair.value)<>'array' then raise exception 'Each table needs a column list'; end if;
    if exists(select from jsonb_array_elements(pair.value) c where jsonb_typeof(c)<>'string' or length(trim(c#>>'{}'))=0) then raise exception 'Invalid column'; end if;
  end loop;
  for rule in select * from jsonb_array_elements(rules) loop
    if jsonb_typeof(rule)<>'object' or not (rule ?& array['table','column','op','value']) or
      not coalesce((cols->(rule->>'table')) ? (rule->>'column'),false) or
      (rule->>'op') is distinct from 'eq' or jsonb_typeof(rule->'value') not in ('string','number','boolean')
      then raise exception 'Choose an allowed column and equality value'; end if;
  end loop;
  insert into public.database_permissions(org_id,database_id,role_id,user_id,mode,table_columns,row_rules)
  values(o,d,r,person,level,cols,rules) on conflict(database_id,role_id,user_id)
  do update set mode=excluded.mode,table_columns=excluded.table_columns,row_rules=excluded.row_rules;
  perform morphy_private.log(o,'permission.saved',d);
end $$;
create function public.effective_permission(d uuid) returns jsonb language plpgsql stable security definer set search_path='' as $$
declare base public.database_permissions; cap public.database_permissions; allowed jsonb; denied jsonb='{"mode":"NONE","table_columns":{},"row_rules":[]}';
begin
  select p.* into base from public.memberships m join public.database_permissions p on p.org_id=m.org_id and p.role_id=m.role_id
  where m.user_id=auth.uid() and p.database_id=d;
  if not found or base.mode='NONE' then return denied; end if;
  select * into cap from public.database_permissions where database_id=d and user_id=auth.uid();
  if not found then return jsonb_build_object('mode',base.mode,'table_columns',base.table_columns,'row_rules',base.row_rules); end if;
  if cap.mode='NONE' then return denied; end if;
  select coalesce(jsonb_object_agg(k,cs),'{}') into allowed from (
    select t.key k,jsonb_agg(distinct c.value) cs from jsonb_each(base.table_columns) t
    cross join lateral jsonb_array_elements_text(t.value) c
    where (cap.table_columns->t.key) ? c.value group by t.key) intersected;
  return jsonb_build_object('mode',least(base.mode,cap.mode),'table_columns',allowed,'row_rules',base.row_rules || cap.row_rules);
end $$;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('avatars','avatars',false,3145728,array['image/webp']);
create policy avatar_read on storage.objects for select to authenticated using(bucket_id='avatars');
create policy avatar_insert on storage.objects for insert to authenticated with check(bucket_id='avatars' and name=auth.uid()::text||'/profile.webp');
create policy avatar_update on storage.objects for update to authenticated using(bucket_id='avatars' and name=auth.uid()::text||'/profile.webp')
with check(bucket_id='avatars' and name=auth.uid()::text||'/profile.webp');
create policy avatar_delete on storage.objects for delete to authenticated using(bucket_id='avatars' and name=auth.uid()::text||'/profile.webp');

-- All writes go through narrow RPCs. SECURITY DEFINER routines have an empty search_path.
do $$
declare tbl text; fn regprocedure;
begin
  foreach tbl in array array['profiles','organizations','roles','memberships','invitations','target_databases','database_permissions','audit_events'] loop
    execute format('revoke all on public.%I from public, anon, authenticated',tbl);
    execute format('grant select on public.%I to authenticated',tbl);
  end loop;
  for fn in select p.oid::regprocedure from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public'
  and p.proname=any(array['claim_profile','username_available','find_people','org_people','create_workspace','create_role','invite_person',
  'accept_invitation','set_member_role','transfer_owner','register_database','save_permission','effective_permission']) loop
    execute format('revoke all on function %s from public,anon,authenticated',fn);
    execute format('grant execute on function %s to authenticated',fn);
  end loop;
end $$;
revoke all on all functions in schema morphy_private from public, anon, authenticated;
grant usage on schema morphy_private to authenticated;
grant execute on function morphy_private.member(uuid),morphy_private.admin(uuid) to authenticated;
commit;

