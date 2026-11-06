-- Run against a disposable, migrated local Supabase database. All changes roll back.
\set ON_ERROR_STOP on
begin;
insert into auth.users(id) values('00000000-0000-4000-9000-000000000001'),('00000000-0000-4000-9000-000000000002');
set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-9000-000000000001',true);
select public.claim_profile('Alice_QA','Alice'), public.create_workspace('Alpha') where false;
select public.claim_profile('Alice_QA','Alice');
select public.create_workspace('Alpha') as a \gset
select id as viewer from public.roles where name='VIEWER' and org_id=:'a' \gset
select public.register_database(:'a','Warehouse','postgres') as db \gset
select public.save_permission(:'a',:'db',:'viewer',null,'QUERY_ONLY','{"orders":["region","amount"]}','[{"table":"orders","column":"region","op":"eq","value":"APAC"}]');
select set_config('request.jwt.claim.sub','00000000-0000-4000-9000-000000000002',true);
do $$begin
 if exists(select from public.organizations) or exists(select from public.database_permissions) then raise exception 'Cross-tenant read'; end if;
 begin perform public.claim_profile('ALICE_QA','Bob');raise exception 'Duplicate allowed';exception when unique_violation then null;end;
end$$;
select public.claim_profile('bob_qa','Bob');
select public.create_workspace('Beta') as b \gset
select set_config('request.jwt.claim.sub','00000000-0000-4000-9000-000000000001',true);
select public.invite_person(:'a','00000000-0000-4000-9000-000000000002',:'viewer');
select id as inv from public.invitations where org_id=:'a' \gset
select set_config('morphy.test_inv',:'inv',true),set_config('morphy.test_org',:'a',true),set_config('morphy.test_database',:'db',true);
do $$begin
 begin perform public.accept_invitation(current_setting('morphy.test_inv')::uuid); raise exception 'Wrong account accepted'; exception when no_data_found then null;end;
end$$;
select set_config('request.jwt.claim.sub','00000000-0000-4000-9000-000000000002',true);
select public.accept_invitation(:'inv');
select public.accept_invitation(:'inv');
do $$begin
 begin perform public.create_role(current_setting('morphy.test_org')::uuid,'esc'); raise exception 'Viewer escalation';exception when insufficient_privilege then null;end;
 begin update public.organizations set owner_id=auth.uid();raise exception 'Direct write allowed';exception when insufficient_privilege then null;end;
end$$;
select set_config('request.jwt.claim.sub','00000000-0000-4000-9000-000000000001',true);
select public.save_permission(:'a',:'db',null,'00000000-0000-4000-9000-000000000002','SCHEMA_EDIT','{"orders":["region","ssn"]}','[]');
select public.transfer_owner(:'a','00000000-0000-4000-9000-000000000002');
do $$begin
 if (select count(*) from public.organizations)<>1 then raise exception 'Organization isolation lost';end if;
 if (select count(*) from public.organizations where owner_id='00000000-0000-4000-9000-000000000002')<>1 then raise exception 'Transfer failed';end if;
end$$;
-- The new owner has ADMIN's database grant, which defaults to NONE.
select set_config('request.jwt.claim.sub','00000000-0000-4000-9000-000000000002',true);
do $$begin
 if public.effective_permission(current_setting('morphy.test_database')::uuid)->>'mode'<>'NONE' then raise exception 'User restriction created a grant';end if;
end$$;
select set_config('request.jwt.claim.sub','00000000-0000-4000-9000-000000000001',true);
insert into storage.objects(bucket_id,name) values('avatars','00000000-0000-4000-9000-000000000001/profile.webp');
select set_config('request.jwt.claim.sub','00000000-0000-4000-9000-000000000002',true);
do $$
declare changed integer;
begin
  begin
    insert into storage.objects(bucket_id,name) values('avatars','00000000-0000-4000-9000-000000000001/other.webp');
    raise exception 'Foreign avatar insert allowed';
  exception when insufficient_privilege then null; end;
  update storage.objects set name=name where name='00000000-0000-4000-9000-000000000001/profile.webp';
  get diagnostics changed=row_count;
  if changed<>0 then raise exception 'Foreign avatar update allowed'; end if;
end $$;
rollback;

