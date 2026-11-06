-- Run with psql against a disposable, migrated control plane.
\set ON_ERROR_STOP on
begin;
create function pg_temp.assert_ok(ok boolean, reason text) returns void language plpgsql as $$
begin
  if ok is not true then raise exception '%',reason; end if;
end $$;
select gen_random_uuid() as author, gen_random_uuid() as reader, gen_random_uuid() as outsider \gset
insert into auth.users(id) values(:'author'),(:'reader'),(:'outsider');
set local role authenticated;
select set_config('request.jwt.claim.sub',:'reader',true);
select public.claim_profile('r_'||left(replace(:'reader','-',''),12),'Reader');
select set_config('request.jwt.claim.sub',:'author',true);
select public.claim_profile('a_'||left(replace(:'author','-',''),12),'Author');
select public.create_workspace('Saved query test') as org \gset
select public.register_database(:'org','Test database','postgres') as db \gset
select id as admin from public.roles where org_id=:'org' and name='ADMIN' \gset
select id as viewer from public.roles where org_id=:'org' and name='VIEWER' \gset
select public.save_permission(:'org',:'db',:'admin',null,'QUERY_ONLY','{"orders":["id"]}','[]');
select public.save_permission(:'org',:'db',:'viewer',null,'VIEW_ONLY','{"orders":["id"]}','[]');
select public.invite_person(:'org',:'reader',:'viewer');
select id as invite from public.invitations where org_id=:'org' \gset
insert into public.saved_queries(org_id,database_id,title,sql_text) values(:'org',:'db','Orders','SELECT id FROM orders') returning id as saved \gset
insert into public.dashboards(org_id,database_id,title) values(:'org',:'db','Board') returning id as board \gset
insert into public.dashboard_panels(dashboard_id,database_id,query_id) values(:'board',:'db',:'saved');
select set_config('request.jwt.claim.sub',:'reader',true);
select public.accept_invitation(:'invite');
select pg_temp.assert_ok(not exists(select from public.dashboards where id=:'board'),'private dashboard leaked');
select set_config('request.jwt.claim.sub',:'author',true);
update public.dashboards set shared=true where id=:'board' and revision=1;
select set_config('request.jwt.claim.sub',:'reader',true);
select pg_temp.assert_ok(exists(select from public.dashboards where id=:'board' and revision=2),'shared dashboard missing');
select pg_temp.assert_ok(not exists(select from public.dashboard_panels where dashboard_id=:'board'),'private query panel leaked');
with edited as (update public.dashboards set title='Hijack' where id=:'board' returning id)
select pg_temp.assert_ok(not exists(select from edited),'viewer edited dashboard');
with removed as (delete from public.dashboard_panels where dashboard_id=:'board' returning query_id)
select pg_temp.assert_ok(not exists(select from removed),'viewer deleted panel');
select set_config('request.jwt.claim.sub',:'author',true);
update public.saved_queries set shared=true where id=:'saved';
select set_config('request.jwt.claim.sub',:'reader',true);
select pg_temp.assert_ok(exists(select from public.dashboard_panels where dashboard_id=:'board'),'shared panel missing');
with edited as (update public.dashboard_panels set position=9 where dashboard_id=:'board' returning query_id)
select pg_temp.assert_ok(not exists(select from edited),'viewer reordered panel');
select set_config('request.jwt.claim.sub',:'outsider',true);
select pg_temp.assert_ok(not exists(select from public.dashboards where id=:'board'),'cross-tenant dashboard read');
select pg_temp.assert_ok(not exists(select from public.dashboard_panels where dashboard_id=:'board'),'cross-tenant panel read');
select set_config('request.jwt.claim.sub',:'author',true);
select public.save_permission(:'org',:'db',:'viewer',null,'NONE','{}','[]');
select set_config('request.jwt.claim.sub',:'reader',true);
select pg_temp.assert_ok(not exists(select from public.dashboards where id=:'board'),'revoked dashboard visible');
select pg_temp.assert_ok(not exists(select from public.dashboard_panels where dashboard_id=:'board'),'revoked panel visible');
select set_config('request.jwt.claim.sub',:'author',true);
delete from public.dashboards where id=:'board';
select pg_temp.assert_ok(not exists(select from public.dashboard_panels where dashboard_id=:'board'),'deleted board retained panels');
rollback;
