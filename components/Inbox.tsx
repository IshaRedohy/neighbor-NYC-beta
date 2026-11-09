"use client";
import {
  useState,
  useRef,
  useEffect,
  useCallback,
  type FormEvent,
} from "react";
import { api, post } from "@/lib/client";
import type { Member } from "@/lib/types";

type Draft = {
  id: string;
  cid: string;
  body: string;
  state: "sending" | "failed" | "sent";
};
const merge = (a: any[], b: any[]) =>
  Array.from(new Map([...a, ...b].map((x) => [x.id, x])).values());

export default function Inbox({ me }: { me: Member }) {
  const [threads, setThreads] = useState<any[]>([]),
    [next, setNext] = useState<string | null>(null);
  const [selected, setSelected] = useState(""),
    [data, setData] = useState<any>(null);
  const [text, setText] = useState(""),
    [error, setError] = useState(""),
    [drafts, setDrafts] = useState<Draft[]>([]);
  const current = useRef(""),
    latest = useRef<string | null>(null),
    polling = useRef(false);
  const generation = useRef(0);
  const threadCursor = useRef<string | null | undefined>(undefined);
  const mounted = useRef(true);
  const select = useCallback((id: string) => {
    generation.current++;
    current.current = id;
    latest.current = null;
    setSelected(id);
    setData(null);
    setText("");
    setError("");
  }, []);
  useEffect(() => {
    select(
      new URLSearchParams(window.location.search).get("conversation") || "",
    );
  }, [select]);
  const refresh = useCallback(async function refreshInbox() {
    if (document.hidden || polling.current) return;
    polling.current = true;
    const gen = generation.current,
      cid = current.current;
    try {
      const [page, summary] = await Promise.all([
        api("/conversations"),
        api("/inbox-summary"),
      ]);
      if (gen !== generation.current) return;
      setThreads((old) =>
        merge(
          page.conversations,
          old.filter(
            (t) => !page.conversations.some((n: any) => n.id === t.id),
          ),
        ),
      );
      if (threadCursor.current === undefined) {
        threadCursor.current = page.nextCursor;
        setNext(page.nextCursor);
      }
      window.dispatchEvent(
        new CustomEvent("inbox-summary", { detail: summary.unread }),
      );
      if (cid) {
        const after = latest.current;
        const result = await api(
          `/conversations/${cid}/messages` +
            (after ? `?after=${encodeURIComponent(after)}` : ""),
        );
        if (gen !== generation.current || document.hidden) return;
        latest.current = result.latestCursor || after;
        setData((old: any) => ({
          ...result,
          messages:
            after && old
              ? merge(old.messages, result.messages)
              : result.messages,
          nextCursor: after && old ? old.nextCursor : result.nextCursor,
        }));
        const last = result.messages.at(-1);
        if (last)
          await post(`/conversations/${cid}/read`, { through: last.id });
      }
      setError("");
    } catch (e) {
      if (gen === generation.current) {
        setError((e as Error).message);
        if ((e as any).status === 403 || (e as any).status === 404) {
          setData(null);
          setThreads((t) => t.filter((x) => x.id !== cid));
        }
      }
    } finally {
      polling.current = false;
      if (mounted.current && gen !== generation.current) void refreshInbox();
    }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = setInterval(refresh, selected ? 5000 : 30000);
    const visible = () => {
      if (!document.hidden) void refresh();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [selected, refresh]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current++;
    };
  }, []);
  async function older() {
    const cid = selected,
      gen = generation.current;
    try {
      const result = await api(
        `/conversations/${cid}/messages?before=${encodeURIComponent(data.nextCursor)}`,
      );
      if (gen === generation.current)
        setData((old: any) => ({
          ...old,
          messages: merge(result.messages, old.messages),
          nextCursor: result.nextCursor,
        }));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function moreThreads() {
    try {
      const page = await api(
        "/conversations?before=" + encodeURIComponent(next!),
      );
      setThreads((old) => merge(old, page.conversations));
      threadCursor.current = page.nextCursor;
      setNext(page.nextCursor);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function deliver(draft: Draft) {
    setDrafts((old) =>
      old.map((d) => (d.id === draft.id ? { ...d, state: "sending" } : d)),
    );
    try {
      await post(`/conversations/${draft.cid}/messages`, {
        body: draft.body,
        clientMessageId: draft.id,
      });
      setDrafts((old) =>
        old.map((d) => (d.id === draft.id ? { ...d, state: "sent" } : d)),
      );
      await refresh();
    } catch (e) {
      setDrafts((old) =>
        old.map((d) => (d.id === draft.id ? { ...d, state: "failed" } : d)),
      );
      setError((e as Error).message);
    }
  }
  function send(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    const draft: Draft = {
      id: crypto.randomUUID(),
      cid: selected,
      body: text.trim(),
      state: "sending",
    };
    setDrafts((old) => [...old, draft]);
    setText("");
    void deliver(draft);
  }
  async function decision(action: string) {
    try {
      await post(`/conversations/${selected}/decision`, { action });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow">ONE CONVERSATION AT A TIME</div>
        <h1>
          Your conversations<span className="green-text">.</span>
        </h1>
        <p>A thoughtful hello can go a long way.</p>
      </div>
      {error && (
        <div className="error" role="alert">
          {error}{" "}
          <button className="text-button" onClick={refresh}>
            Refresh
          </button>
        </div>
      )}
      <div className="inbox">
        <aside className="thread-list">
          <div className="thread-title">
            <h3>Messages</h3>
          </div>
          {!threads.length && (
            <p className="padded">
              No conversations yet. Find a neighbor in Discover.
            </p>
          )}
          {threads.map((t) => (
            <button
              key={t.id}
              className={`thread ${selected === t.id ? "selected" : ""}`}
              onClick={() => select(t.id)}
            >
              <span>
                <strong>{t.other_name}</strong>
                <small>
                  {t.status === "pending"
                    ? "Message request"
                    : t.status === "declined"
                      ? "Request declined"
                      : t.last_message}
                </small>
              </span>
              {t.unread > 0 && <i className="unread-dot" />}
            </button>
          ))}
          {next && (
            <button className="button secondary" onClick={moreThreads}>
              More conversations
            </button>
          )}
        </aside>
        <section className="chat">
          {!selected ? (
            <p className="padded">
              Choose a conversation or find someone in Discover.
            </p>
          ) : data?.conversation.id === selected ? (
            <>
              <header className="chat-heading">
                <h3>{data.other.name}</h3>
                <button
                  className="text-button"
                  onClick={async () => {
                    if (
                      !confirm("Block this member and hide this conversation?")
                    )
                      return;
                    try {
                      await post("/blocks/" + data.other.id);
                      setThreads((t) => t.filter((x) => x.id !== selected));
                      select("");
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Block
                </button>
                <button
                  className="text-button"
                  onClick={async () => {
                    const reason = prompt(
                      "Describe what happened (at least 5 characters).",
                    );
                    if (!reason) return;
                    try {
                      await post("/reports", {
                        memberId: data.other.id,
                        reason,
                      });
                      setError("Report sent to your community host.");
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Report
                </button>
              </header>
              <div className="message-list" aria-live="polite">
                {data.nextCursor && (
                  <button className="button secondary" onClick={older}>
                    Earlier messages
                  </button>
                )}
                {data.messages.map((m: any) => (
                  <div
                    key={m.id}
                    className={`message ${m.sender_id === me.id ? "mine" : ""}`}
                  >
                    <p>{m.body}</p>
                    <time>{new Date(m.created_at).toLocaleString()}</time>
                    {m.sender_id === me.id && <small> · Sent</small>}
                  </div>
                ))}
                {drafts
                  .filter(
                    (d) =>
                      d.cid === selected &&
                      !data.messages.some(
                        (m: any) => m.client_message_id === d.id,
                      ),
                  )
                  .map((d) => (
                    <div key={d.id} className="message mine">
                      <p>{d.body}</p>
                      <small>
                        {d.state === "sending"
                          ? "Sending…"
                          : d.state === "sent"
                            ? "Sent"
                            : "Not sent"}
                      </small>
                      {d.state === "failed" && (
                        <button
                          className="text-button"
                          onClick={() => deliver(d)}
                        >
                          Retry
                        </button>
                      )}
                    </div>
                  ))}
              </div>
              {data.conversation.status === "pending" ? (
                <div className="request-banner">
                  {data.conversation.recipient_id === me.id ? (
                    <>
                      <p>Would you like to start a conversation?</p>
                      <button
                        className="button primary"
                        onClick={() => decision("accept")}
                      >
                        Accept request
                      </button>
                      <button
                        className="button secondary"
                        onClick={() => decision("decline")}
                      >
                        Decline
                      </button>
                    </>
                  ) : (
                    <p>You can continue once your neighbor accepts.</p>
                  )}
                </div>
              ) : data.conversation.status !== "accepted" ||
                data.other.status !== "approved" ? (
                <p className="padded">This conversation is closed.</p>
              ) : (
                <form className="message-composer" onSubmit={send}>
                  <textarea
                    required
                    maxLength={2000}
                    aria-label="Your message"
                    placeholder="Write a thoughtful reply…"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                  />
                  <button className="button primary" disabled={!text.trim()}>
                    Send
                  </button>
                </form>
              )}
            </>
          ) : (
            <p className="padded">
              {error
                ? "Conversation unavailable. Try refreshing."
                : "Loading conversation…"}
            </p>
          )}
        </section>
      </div>
    </>
  );
}
