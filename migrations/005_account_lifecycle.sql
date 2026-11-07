begin;
alter table public.invitations drop constraint invitations_status_check;
alter table public.invitations add constraint invitations_status_check
  check(status in ('pending','accepted','revoked'));

-- The account identifier and global handle remain stable when editing a profile.
create function public.update_profile(full_name text, avatar text) returns void
language plpgsql security definer set search_path='' as $$
begin
  update public.profiles set display_name=trim(full_name),avatar_path=avatar where id=auth.uid();
  if not found then raise exception 'Claim your profile first' using errcode='42501'; end if;
end $$;

create function public.revoke_invitation(inv uuid) returns void
language plpgsql security definer set search_path='' as $$
declare i public.invitations;
begin
  select * into strict i from public.invitations where id=inv;
  perform morphy_private.require_admin(i.org_id);
  select * into strict i from public.invitations where id=inv for update;
  if i.status='revoked' then return; end if;
  if i.status<>'pending' then raise exception 'Only pending invitations can be revoked'; end if;
  update public.invitations set status='revoked' where id=inv;
  perform morphy_private.log(i.org_id,'invitation.revoked',i.user_id);
end $$;

create or replace function public.invite_person(o uuid,person uuid,r uuid) returns void
language plpgsql security definer set search_path='' as $$
begin
  perform morphy_private.require_admin(o);
  if exists(select from public.memberships where org_id=o and user_id=person) then raise exception 'Already a member'; end if;
  insert into public.invitations(org_id,user_id,role_id,invited_by,organization_name)
  select o,person,r,auth.uid(),name from public.organizations where id=o
  on conflict(org_id,user_id) do update set
    id=case when invitations.status='revoked' then gen_random_uuid() else invitations.id end,
    role_id=excluded.role_id,invited_by=excluded.invited_by,
    organization_name=excluded.organization_name,created_at=now(),status='pending'
  where invitations.status in ('pending','revoked');
  if not found then raise exception 'Invitation cannot be renewed'; end if;
  perform morphy_private.log(o,'invitation.sent',person);
end $$;

create or replace function public.accept_invitation(inv uuid) returns void
language plpgsql security definer set search_path='' as $$
declare i public.invitations;
begin
  select * into strict i from public.invitations where id=inv and user_id=auth.uid();
  -- Serialize acceptance, withdrawal and reissue on the organization first.
  perform 1 from public.organizations where id=i.org_id for update;
  select * into strict i from public.invitations where id=inv and user_id=auth.uid() for update;
  if i.status='accepted' then return; end if;
  if i.status<>'pending' then raise exception 'Invitation is no longer pending' using errcode='42501'; end if;
  insert into public.memberships values(i.org_id,i.user_id,i.role_id);
  update public.invitations set status='accepted' where id=inv;
  perform morphy_private.log(i.org_id,'invitation.accepted',i.user_id);
end $$;

revoke all on function public.update_profile(text,text),public.revoke_invitation(uuid) from public,anon,authenticated;
grant execute on function public.update_profile(text,text),public.revoke_invitation(uuid) to authenticated;
commit;
