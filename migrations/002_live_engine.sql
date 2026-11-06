begin;
-- Authorized query users can discover their permitted database records.
drop policy read_databases on public.target_databases;
create policy read_databases on public.target_databases for select to authenticated
using (
  morphy_private.admin(org_id)
  or public.effective_permission(id)->>'mode' in ('QUERY_ONLY','SCHEMA_EDIT')
);
commit;
