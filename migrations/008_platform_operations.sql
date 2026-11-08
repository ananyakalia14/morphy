begin;

create table morphy_private.ops_staff (
  user_id uuid primary key references auth.users on delete cascade,
  role text not null check (role in ('viewer','reviewer','operator'))
);

create table morphy_private.ops_controls (
  kind text not null check (kind in ('user','organization','source')),
  target_id uuid not null,
  expires_at timestamptz,
  primary key (kind,target_id),
  check (kind='source' or expires_at is not null)
);

create table morphy_private.ops_actions (
  id bigint generated always as identity primary key,
  actor_id uuid not null,
  kind text not null check (kind in ('user','organization','source')),
  target_id uuid not null,
  action text not null check (action in ('restrict','restore')),
  reason text not null check (length(trim(reason)) between 1 and 500),
  expires_at timestamptz,
  occurred_at timestamptz not null default now()
);
create index ops_actions_target on morphy_private.ops_actions(kind,target_id,id desc);

create table morphy_private.ops_jobs (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations on delete cascade,
  actor_id uuid not null,
  source_id uuid not null,
  kind text not null check (kind in ('query','import','generation')),
  model_used boolean not null default false check (not model_used or kind='generation'),
  prompt_flagged boolean not null default false check (not prompt_flagged or kind='generation'),
  state text not null default 'running' check (state in ('running','succeeded','rejected','failed','cancelled')),
  code text check (code in ('policy_denied','invalid_query','result_limit','invalid_file','file_limit',
    'file_type_mismatch','import_unavailable','generation_rejected','model_unavailable','service_error','interrupted')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  check ((state='running') = (finished_at is null)),
  check ((state in ('running','succeeded')) = (code is null))
);
create index ops_jobs_recent on morphy_private.ops_jobs(started_at desc,id);
create index ops_jobs_org on morphy_private.ops_jobs(org_id,started_at desc);
create index ops_audit_org_recent on public.audit_events(org_id,occurred_at desc) include (actor_id);

create table morphy_private.ops_incidents (
  id uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('user','organization','source')),
  target_id uuid not null,
  job_id uuid references morphy_private.ops_jobs on delete set null,
  reason text not null check (length(trim(reason)) between 1 and 500),
  opened_by uuid not null,
  opened_at timestamptz not null default now(),
  closed_by uuid,
  closed_at timestamptz,
  resolution text check (length(trim(resolution)) between 1 and 500),
  check (num_nonnulls(closed_by,closed_at,resolution) in (0,3))
);
create index ops_incidents_queue on morphy_private.ops_incidents(opened_at desc,id);
create index ops_incidents_job on morphy_private.ops_incidents(job_id) where job_id is not null;

revoke all on morphy_private.ops_staff,morphy_private.ops_controls,morphy_private.ops_actions,
  morphy_private.ops_jobs,morphy_private.ops_incidents from public,anon,authenticated;

create function morphy_private.active_control(target_kind text, target uuid) returns boolean
language sql stable security definer set search_path='' as $$
  select exists(select from morphy_private.ops_controls c
    where c.kind=target_kind and c.target_id=target and (c.expires_at is null or c.expires_at>now()))
$$;

create function morphy_private.access_block(p_user uuid, p_org uuid, p_source uuid) returns text
language sql stable security definer set search_path='' as $$
  select case
    when morphy_private.active_control('user',p_user) then 'user_suspended'
    when morphy_private.active_control('organization',p_org) then 'organization_suspended'
    when morphy_private.active_control('source',p_source) then 'source_quarantined'
  end
$$;

create function morphy_private.workspace_enabled(o uuid) returns boolean
language sql stable security definer set search_path='' as $$
  select auth.uid() is not null and morphy_private.access_block(auth.uid(),o,null) is null
$$;

create or replace function morphy_private.member(o uuid) returns boolean
language sql stable security definer set search_path='' as $$
  select morphy_private.workspace_enabled(o)
    and exists(select from public.memberships where org_id=o and user_id=(select auth.uid()))
$$;

create or replace function morphy_private.admin(o uuid) returns boolean
language sql stable security definer set search_path='' as $$
  select morphy_private.workspace_enabled(o) and exists(
    select from public.memberships m join public.roles r on r.id=m.role_id
    where m.org_id=o and m.user_id=(select auth.uid()) and r.builtin and r.name='ADMIN')
$$;

alter policy read_self on public.profiles using (id=(select auth.uid()) and (select morphy_private.workspace_enabled(null)));
alter policy read_invitations on public.invitations using (
  (user_id=(select auth.uid()) and morphy_private.workspace_enabled(org_id)) or morphy_private.admin(org_id));

create policy enabled_avatar_session on storage.objects as restrictive for all to authenticated
  using (bucket_id<>'avatars' or (select morphy_private.workspace_enabled(null)))
  with check (bucket_id<>'avatars' or (select morphy_private.workspace_enabled(null)));

-- Definer routines write these tables outside RLS. Guard the writes at the table
-- boundary, including existing profile and workspace RPCs.
create function morphy_private.require_enabled_actor() returns trigger
language plpgsql security definer set search_path='' as $$
begin
  if auth.uid() is not null and not morphy_private.workspace_enabled(null) then
    raise exception 'This MORPHY account is suspended.' using errcode='42501';
  end if;
  return new;
end $$;
create trigger enabled_profile_actor before insert or update on public.profiles
for each row execute function morphy_private.require_enabled_actor();
create trigger enabled_workspace_creator before insert on public.organizations
for each row execute function morphy_private.require_enabled_actor();

create or replace function public.username_available(handle text) returns boolean
language sql stable security definer set search_path='' as $$
  select morphy_private.workspace_enabled(null) and lower(trim(handle)) ~ '^[a-z][a-z0-9_]{2,23}$'
    and not exists(select from public.profiles where lower(username)=lower(trim(handle)))
$$;

create or replace function public.find_people(prefix text) returns table(id uuid,username text,avatar_path text)
language sql stable security definer set search_path='' as $$
  select p.id,p.username,p.avatar_path from public.profiles p where morphy_private.workspace_enabled(null)
    and length(prefix) between 2 and 24 and prefix ~ '^[a-z0-9_]+$'
    and p.username like replace(prefix,'_','\_') || '%' order by p.username limit 12
$$;

create or replace function public.accept_invitation(inv uuid) returns void
language plpgsql security definer set search_path='' as $$
declare i public.invitations;
begin
  select * into strict i from public.invitations where id=inv and user_id=auth.uid();
  perform 1 from public.organizations where id=i.org_id for update;
  if not morphy_private.workspace_enabled(i.org_id) then
    raise exception 'This MORPHY account or organization is suspended.' using errcode='42501';
  end if;
  select * into strict i from public.invitations where id=inv and user_id=auth.uid() for update;
  if i.status='accepted' then return; end if;
  if i.status<>'pending' then raise exception 'Invitation is no longer pending' using errcode='42501'; end if;
  insert into public.memberships values(i.org_id,i.user_id,i.role_id);
  update public.invitations set status='accepted' where id=inv;
  perform morphy_private.log(i.org_id,'invitation.accepted',i.user_id);
end $$;

create or replace function public.effective_permission(d uuid) returns jsonb
language plpgsql stable security definer set search_path='' as $$
declare base public.database_permissions; cap public.database_permissions; allowed jsonb;
  denied constant jsonb='{"mode":"NONE","table_columns":{},"row_rules":[]}';
begin
  select p.* into base from public.memberships m join public.database_permissions p on p.org_id=m.org_id and p.role_id=m.role_id
  where m.user_id=auth.uid() and p.database_id=d;
  if not found or base.mode='NONE' or morphy_private.access_block(auth.uid(),base.org_id,d) is not null then return denied; end if;
  select * into cap from public.database_permissions where database_id=d and user_id=auth.uid();
  if not found then return jsonb_build_object('mode',base.mode,'table_columns',base.table_columns,'row_rules',base.row_rules); end if;
  if cap.mode='NONE' then return denied; end if;
  select coalesce(jsonb_object_agg(k,cs),'{}') into allowed from (
    select t.key k,jsonb_agg(distinct c.value) cs from jsonb_each(base.table_columns) t
    cross join lateral jsonb_array_elements_text(t.value) c
    where (cap.table_columns->t.key) ? c.value group by t.key) intersected;
  return jsonb_build_object('mode',least(base.mode,cap.mode),'table_columns',allowed,'row_rules',base.row_rules || cap.row_rules);
end $$;

revoke all on function morphy_private.active_control(text,uuid),morphy_private.access_block(uuid,uuid,uuid),
  morphy_private.workspace_enabled(uuid),morphy_private.require_enabled_actor() from public,anon,authenticated;
grant execute on function morphy_private.workspace_enabled(uuid) to authenticated;

commit;
