"use client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, post } from "@/lib/client";
import type { Member, Profile } from "@/lib/types";

type CommunityPost = {
  id: string;
  author_id: string;
  name: string;
  kind: string;
  title: string;
  body: string;
  tags: string[];
  matches: string[];
  starts_at: string | null;
  venue: string;
  neighborhood: string;
  distance: number;
};
export default function Community({
  me,
  onProfile,
}: {
  me: Member;
  onProfile: (p: Profile) => void;
}) {
  const [rows, setRows] = useState<CommunityPost[]>([]),
    [events, setEvents] = useState<CommunityPost[]>([]);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true);
  const [radius, setRadius] = useState("5"),
    [kind, setKind] = useState("all"),
    [relevant, setRelevant] = useState(true),
    [page, setPage] = useState(1),
    [total, setTotal] = useState(0);
  const [form, setForm] = useState({
    kind: "need",
    title: "",
    body: "",
    tags: "",
    zip: me.zip,
    starts_at: "",
    venue: "",
  });
  const refresh = useCallback(async () => {
    try {
      const [feed, notifications] = await Promise.all([
        api(
          `/posts?radius=${radius}&kind=${kind}&relevant=${relevant}&page=${page}`,
        ),
        api("/notifications"),
      ]);
      setRows(feed.posts);
      setTotal(feed.total);
      setEvents(notifications.events);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [radius, kind, relevant, page]);
  useEffect(() => {
    setLoading(true);
    refresh();
    const timer = setInterval(refresh, 10000);
    return () => clearInterval(timer);
  }, [refresh]);
  async function publish(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post("/posts", {
        ...form,
        tags: form.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        starts_at:
          form.kind === "event" ? new Date(form.starts_at).toISOString() : null,
        venue: form.kind === "event" ? form.venue : "",
      });
      setForm({
        kind: "need",
        title: "",
        body: "",
        tags: "",
        zip: me.zip,
        starts_at: "",
        venue: "",
      });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function act(action: () => Promise<unknown>) {
    try {
      await action();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow">WHAT’S HAPPENING NEARBY</div>
        <h1>Your community board.</h1>
        <p>Find help, share an offer, or bring neighbors together.</p>
      </div>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {events.length > 0 && (
        <section className="panel" aria-label="Event notifications">
          <h2>
            {events.length} new nearby event{events.length === 1 ? "" : "s"}
          </h2>
          <p>Upcoming events within approximately 5 miles of your ZIP.</p>
          {events.map((event) => (
            <div className="submission" key={event.id}>
              <div>
                <strong>{event.title}</strong>
                <p>
                  {new Date(event.starts_at!).toLocaleString()} · {event.venue}
                </p>
                <p>{event.body}</p>
              </div>
              <button
                className="button secondary"
                onClick={() =>
                  act(() => post(`/notifications/${event.id}/read`))
                }
              >
                Mark read
              </button>
            </div>
          ))}
        </section>
      )}
      <div className="settings-grid">
        <section>
          <div className="filter-row">
            <label>
              Distance{" "}
              <select
                value={radius}
                onChange={(e) => {
                  setRadius(e.target.value);
                  setPage(1);
                }}
              >
                <option value="2">Within 2 miles</option>
                <option value="5">Within 5 miles</option>
                <option value="all">All NYC</option>
              </select>
            </label>
            <label>
              Show{" "}
              <select
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setPage(1);
                }}
              >
                <option value="all">All posts</option>
                <option value="need">Needs / ads</option>
                <option value="offer">Offers</option>
                <option value="event">Events</option>
              </select>
            </label>
            <label>
              <input
                type="checkbox"
                checked={relevant}
                onChange={(e) => {
                  setRelevant(e.target.checked);
                  setPage(1);
                }}
              />{" "}
              For me
            </label>
          </div>
          <p className="quiet">
            “For me” matches topics to your interests, expertise, needs, and
            profession, and includes nearby events. Turn it off to browse every
            local post.
          </p>
          {loading ? (
            <p>Loading community posts…</p>
          ) : rows.length === 0 ? (
            <div className="empty">
              <h3>No posts here yet</h3>
              <p>Share the first post or broaden your filters.</p>
            </div>
          ) : (
            rows.map((row) => (
              <article className="panel" key={row.id}>
                <span className="eyebrow">
                  {row.kind === "need" ? "Need / ad" : row.kind}
                </span>
                <h2>{row.title}</h2>
                <p>
                  {row.name} · {row.neighborhood} · ~{row.distance} mi
                </p>
                {row.starts_at && (
                  <p>
                    <strong>{new Date(row.starts_at).toLocaleString()}</strong>{" "}
                    · {row.venue}
                  </p>
                )}
                <p style={{ whiteSpace: "pre-wrap" }}>{row.body}</p>
                <div className="card-tags">
                  {row.tags.map((tag) => (
                    <span className="tag" key={tag}>
                      {tag}
                    </span>
                  ))}
                </div>
                {row.matches.length > 0 && (
                  <p className="quiet">Matches you: {row.matches.join(", ")}</p>
                )}
                <div className="form-actions">
                  {row.author_id !== me.id && (
                    <button
                      className="button primary"
                      onClick={() =>
                        act(async () =>
                          onProfile(await api("/profiles/" + row.author_id)),
                        )
                      }
                    >
                      Message {row.name}
                    </button>
                  )}
                  {(row.author_id === me.id || me.role === "admin") && (
                    <button
                      className="text-button danger"
                      onClick={() => {
                        if (window.confirm("Delete this post?"))
                          act(() =>
                            api("/posts/" + row.id, { method: "DELETE" }),
                          );
                      }}
                    >
                      Delete post
                    </button>
                  )}
                </div>
              </article>
            ))
          )}
          <div className="pagination">
            <button
              className="button secondary"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              className="button secondary"
              disabled={page * 20 >= total}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </section>
        <aside>
          <form className="panel profile-form" onSubmit={publish}>
            <h2>Share with neighbors</h2>
            <label>
              Post type
              <select
                value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value })}
              >
                <option value="need">Need / ad</option>
                <option value="offer">Offer help or services</option>
                <option value="event">Community event</option>
              </select>
            </label>
            <label>
              Title
              <input
                required
                minLength={3}
                maxLength={120}
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Looking for a realtor"
              />
            </label>
            <label>
              Details
              <textarea
                required
                minLength={5}
                maxLength={2000}
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
              />
            </label>
            <label>
              Topics
              <input
                required
                value={form.tags}
                onChange={(e) => setForm({ ...form, tags: e.target.value })}
                placeholder="real estate, realtor, home buying"
              />
              <small>
                Separate topics with commas. Use terms your neighbors list on
                their profiles.
              </small>
            </label>
            <label>
              Area ZIP
              <input
                required
                pattern="[0-9]{5}"
                maxLength={5}
                value={form.zip}
                onChange={(e) => setForm({ ...form, zip: e.target.value })}
              />
            </label>
            {form.kind === "event" && (
              <>
                <label>
                  Starts at (your local time)
                  <input
                    type="datetime-local"
                    required
                    value={form.starts_at}
                    onChange={(e) =>
                      setForm({ ...form, starts_at: e.target.value })
                    }
                  />
                </label>
                <label>
                  Public meeting place
                  <input
                    required
                    maxLength={160}
                    value={form.venue}
                    onChange={(e) =>
                      setForm({ ...form, venue: e.target.value })
                    }
                    placeholder="Park entrance or community center"
                  />
                </label>
              </>
            )}
            <p className="quiet">
              Visible to approved members. Keep your email, phone number, and
              home address out of posts. Replies happen in app messages.
            </p>
            <button className="button primary" disabled={busy || !me.visible}>
              {busy ? "Publishing…" : "Publish post"}
            </button>
            {!me.visible && <p>Show your profile to publish.</p>}
          </form>
        </aside>
      </div>
    </>
  );
}
