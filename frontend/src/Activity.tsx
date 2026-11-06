import { useEffect, useState } from "react";
import { db } from "./client";
type Event = {
  id: number;
  action: string;
  actor_id: string;
  subject_id: string;
  occurred_at: string;
};
export function Activity({ org }: { org: string }) {
  const [revision, setRevision] = useState(0);
  const [events, setEvents] = useState<Event[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    db!
      .from("audit_events")
      .select("id,action,actor_id,subject_id,occurred_at")
      .eq("org_id", org)
      .order("occurred_at", { ascending: false })
      .order("id", { ascending: false })
      .limit(100)
      .then(({ data, error }) => {
        if (alive) {
          setEvents(data || []);
          setError(error?.message || "");
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
  }, [org, revision]);
  return (
    <section className="panel">
      <h2>Organization activity</h2>
      <button disabled={loading} onClick={() => setRevision(value => value + 1)}>Refresh activity</button>
      {error ? (
        <p role="alert">{error}</p>
      ) : loading ? (
        <p role="status">Loading activity…</p>
      ) : events.length ? (
        <div className="data-scroll">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Event</th>
                <th>Actor</th>
                <th>Subject</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td>{new Date(e.occurred_at).toLocaleString()}</td>
                  <td>{e.action}</td>
                  <td>{e.actor_id}</td>
                  <td>{e.subject_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>Organization events will appear here.</p>
      )}
      <small>Most recent 100 events. Use Refresh to load new activity.</small>
    </section>
  );
}
