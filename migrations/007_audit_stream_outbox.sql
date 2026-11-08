begin;

create table morphy_private.audit_stream_settings (
  singleton boolean primary key default true check (singleton),
  enabled boolean not null default false
);
insert into morphy_private.audit_stream_settings default values;

create table morphy_private.audit_stream_outbox (
  event_id bigint primary key references public.audit_events(id) on delete cascade
);

revoke all on morphy_private.audit_stream_settings, morphy_private.audit_stream_outbox
  from public, anon, authenticated;

create function morphy_private.enqueue_audit_event() returns trigger
language plpgsql security definer set search_path='' as $$
begin
  if exists (select 1 from morphy_private.audit_stream_settings where enabled) then
    insert into morphy_private.audit_stream_outbox(event_id) values (new.id);
  end if;
  return new;
end;
$$;
revoke all on function morphy_private.enqueue_audit_event() from public, anon, authenticated;

create trigger enqueue_audit_event after insert on public.audit_events
for each row execute function morphy_private.enqueue_audit_event();

commit;
