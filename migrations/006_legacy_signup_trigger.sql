begin;
-- MORPHY creates profiles through claim_profile after the user chooses a handle.
-- Older project templates installed an incompatible automatic profile insert.
do $$
begin
  if exists (
    select from pg_trigger t
    where t.tgrelid='auth.users'::regclass
      and t.tgname='on_auth_user_created'
      and t.tgfoid=to_regprocedure('public.handle_new_user()')
      and pg_get_functiondef(t.tgfoid) like '%INSERT INTO public.profiles (id, username, full_name)%'
  ) then
    drop trigger on_auth_user_created on auth.users;
  end if;
end $$;
commit;
