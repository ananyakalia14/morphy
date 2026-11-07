create role anon;
create role authenticated;
create schema auth;
create schema storage;
create schema extensions;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
grant usage on schema auth, storage to authenticated;
create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid default gen_random_uuid() primary key,bucket_id text,name text,metadata jsonb);
alter table storage.objects enable row level security;
grant select,insert,delete,update on storage.objects to authenticated;

-- Reproduce the legacy hosted-project trigger. Migration 006 must remove it
-- before any authentication fixtures can be inserted into auth.users.
create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path='' as $$
begin
  INSERT INTO public.profiles (id, username, full_name)
  values(new.id,'legacy_user','Legacy');
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
for each row execute function public.handle_new_user();
