"use client";
import { useEffect, useState, type FormEvent } from "react";
import { api, post, title } from "@/lib/client";
const fields = [
  "name",
  "zip",
  "occupation",
  "workplace",
  "languages",
  "expertise",
  "interests",
  "needs",
  "cultures",
  "countries",
  "bio",
];
const lists = [
  "languages",
  "expertise",
  "interests",
  "needs",
  "cultures",
  "countries",
];
export default function Signup() {
  const [application, setApplication] = useState<any>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  useEffect(() => {
    api("/application")
      .then(setApplication)
      .catch((e) => setError(e.message));
  }, []);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const values = Object.fromEntries(
      fields.map((k) => [
        k,
        lists.includes(k)
          ? (form[k] || "")
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : form[k] || "",
      ]),
    );
    try {
      await post("/application", { ...values, adult: true, consent: true });
      setApplication({ ...application, status: "pending" });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="main-wrap">
      <section className="panel">
        <h1>Join your community</h1>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {!application ? (
          <a className="button primary" href="/api/auth/cognito">
            Verify with Google or an email code
          </a>
        ) : (
          <>
            <p>Verified email: {application.email}</p>
            {application.status === "pending" ? (
              <>
                <h2>Your application is awaiting approval</h2>
                <p>
                  The community host will review it. Sign in again after you
                  receive your invitation.
                </p>
              </>
            ) : application.status === "approved" ? (
              <a className="button primary" href="/api/auth/cognito">
                Sign in to the community
              </a>
            ) : application.status === "link_required" ? (
              <>
                <h2>You already have a profile</h2>
                <p>
                  Sign in with your existing Google account, then use “Link
                  Google or email-code login” in My profile.
                </p>
                <a href="/api/auth/google" className="button primary">
                  Sign in with Google
                </a>
              </>
            ) : (
              <form className="profile-form application-form" onSubmit={submit}>
                <p>
                  Complete your profile for host review. Separate multiple
                  languages, skills, and interests with commas.
                </p>
                {fields.map((k) => (
                  <label key={k}>
                    {k === "name"
                      ? "Display name"
                      : k === "expertise"
                        ? "Skills you can help with"
                        : title(k)}
                    <input
                      required={[
                        "name",
                        "zip",
                        "occupation",
                        "languages",
                        "expertise",
                      ].includes(k)}
                      maxLength={k === "bio" ? 800 : k === "zip" ? 5 : 720}
                      value={form[k] || ""}
                      onChange={(e) =>
                        setForm({ ...form, [k]: e.target.value })
                      }
                    />
                  </label>
                ))}
                <label>
                  <input type="checkbox" required /> I am at least 18.
                </label>
                <label>
                  <input type="checkbox" required /> I consent to sharing this
                  profile with approved community members.
                </label>
                <button className="button primary" disabled={busy}>
                  {busy ? "Submitting…" : "Submit for approval"}
                </button>
              </form>
            )}
          </>
        )}
        <p>
          <a href="/">Back to sign-in</a>
        </p>
      </section>
    </main>
  );
}
