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
select set_config('request.jwt.claim.sub',:'reader',true);
select public.accept_invitation(:'invite');
select pg_temp.assert_ok(not exists(select from public.saved_queries where id=:'saved'),'private definition leaked');
select set_config('request.jwt.claim.sub',:'author',true);
update public.saved_queries set shared=true where id=:'saved' and revision=1;
with stale as (update public.saved_queries set title='Stale' where id=:'saved' and revision=1 returning id)
select pg_temp.assert_ok(not exists(select from stale),'stale edit overwrote current revision');
select set_config('request.jwt.claim.sub',:'reader',true);
select pg_temp.assert_ok(exists(select from public.saved_queries where id=:'saved' and revision=2),'shared definition missing');
with edited as (update public.saved_queries set title='Hijack' where id=:'saved' returning id)
select pg_temp.assert_ok(not exists(select from edited),'viewer edited shared definition');
with removed as (delete from public.saved_queries where id=:'saved' returning id)
select pg_temp.assert_ok(not exists(select from removed),'viewer deleted shared definition');
select set_config('request.jwt.claim.sub',:'outsider',true);
select pg_temp.assert_ok(not exists(select from public.saved_queries where id=:'saved'),'cross-tenant read');
select set_config('request.jwt.claim.sub',:'author',true);
select public.save_permission(:'org',:'db',:'viewer',null,'NONE','{}','[]');
select set_config('request.jwt.claim.sub',:'reader',true);
select pg_temp.assert_ok(not exists(select from public.saved_queries where id=:'saved'),'revoked definition still visible');
select set_config('request.jwt.claim.sub',:'author',true);
delete from public.saved_queries where id=:'saved' and revision=2;
select pg_temp.assert_ok(not exists(select from public.saved_queries where id=:'saved'),'author delete failed');
rollback;
