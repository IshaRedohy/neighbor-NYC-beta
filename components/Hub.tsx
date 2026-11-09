"use client";
import {
  useEffect,
  useState,
  useCallback,
  useRef,
  type FormEvent,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowUpRight,
  ArrowRight,
  Search,
  MapPin,
  MessageCircle,
  Users,
  Compass,
  ShieldCheck,
  SlidersHorizontal,
  X,
  Globe2,
  HeartHandshake,
  ChevronDown,
  LogOut,
  Check,
  Send,
  Sparkles,
  Upload,
  EyeOff,
  Flag,
  Ban,
  Menu,
  CheckCircle2,
} from "lucide-react";
import { api, post, initials, title } from "@/lib/client";
import type { Member, Profile } from "@/lib/types";

import LinkLogin from "@/components/LinkLogin";
import Inbox from "@/components/Inbox";
import Community from "@/components/Community";

function Logo() {
  return (
    <Link href="/discover" className="logo">
      <span className="logo-icon">
        <Users size={23} strokeWidth={2.4} />
      </span>
      neighbor<span className="logo-dot">.</span>
      <span className="nyc-label">NYC</span>
    </Link>
  );
}
function Avatar({ name, size = "normal" }: { name: string; size?: string }) {
  const colors = ["peach", "sage", "lavender", "blue", "rose"];
  const color =
    colors[
      Array.from(name).reduce((a, c) => a + c.charCodeAt(0), 0) % colors.length
    ];
  return <span className={`avatar ${color} ${size}`}>{initials(name)}</span>;
}
function ErrorNote({ error }: { error: string }) {
  return error ? (
    <div className="error" role="alert">
      {error}
    </div>
  ) : null;
}
function Tag({ children }: { children: React.ReactNode }) {
  return <span className="tag">{children}</span>;
}
function Empty({ title: heading, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <Users size={30} />
      <h3>{heading}</h3>
      <p>{text}</p>
    </div>
  );
}

export default function Hub() {
  const [me, setMe] = useState<Member | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [config, setConfig] = useState<{
    demo: boolean;
    google: boolean;
    formUrl: string | null;
    nativeSignup?: boolean;
  }>({ demo: false, google: false, formUrl: null });
  const [communityProfile, setCommunityProfile] = useState<Profile | null>(
    null,
  );
  const [eventCount, setEventCount] = useState(0);
  const [menu, setMenu] = useState(false),
    [unread, setUnread] = useState(0);
  const router = useRouter(),
    path = usePathname();
  const refresh = useCallback(async () => {
    try {
      setMe(await api("/me"));
    } catch (e) {
      if ((e as any).status !== 401) setError((e as Error).message);
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    api("/config")
      .then(setConfig)
      .catch((e) => setError(e.message));
    refresh();
  }, [refresh]);
  useEffect(() => {
    if (!me) return;
    let active = true,
      pending = false;
    const update = async () => {
      if (document.hidden || pending) return;
      pending = true;
      try {
        const jobs = [
          api("/notifications").then((n) => {
            if (active) setEventCount(n.count);
          }),
        ];
        if (path !== "/messages")
          jobs.push(
            api("/inbox-summary").then((n) => {
              if (active) setUnread(n.unread);
            }),
          );
        await Promise.all(jobs);
      } catch {
      } finally {
        pending = false;
      }
    };
    const summary = (event: Event) => setUnread((event as CustomEvent).detail);
    const visible = () => {
      if (!document.hidden) void update();
    };
    void update();
    const timer = setInterval(update, 30000);
    document.addEventListener("visibilitychange", visible);
    window.addEventListener("inbox-summary", summary);
    return () => {
      active = false;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
      window.removeEventListener("inbox-summary", summary);
    };
  }, [me, path]);
  useEffect(() => {
    const expired = () => {
      setMe(null);
      setError("Your session expired. Sign in again to continue.");
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  async function logout() {
    try {
      await post("/auth/logout");
      setMe(null);
      router.push("/");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (loading)
    return (
      <div className="loading-screen">
        <Logo />
        <span className="spinner" />
        <p>Finding your corner of the city…</p>
      </div>
    );
  if (!me)
    return <Landing config={config} onLogin={refresh} initialError={error} />;
  const nav = [
    { href: "/discover", label: "Discover", icon: Compass },
    { href: "/community", label: "Community", icon: Users },
    { href: "/messages", label: "Messages", icon: MessageCircle },
    { href: "/profile", label: "My profile", icon: Users },
    ...(me.role === "admin"
      ? [{ href: "/admin", label: "Manage community", icon: ShieldCheck }]
      : []),
  ];
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="nav-inner">
          <Logo />
          <nav className={menu ? "open" : ""}>
            {nav.map((n) => (
              <Link
                onClick={() => setMenu(false)}
                className={
                  path === n.href || (path === "/" && n.href === "/discover")
                    ? "active"
                    : ""
                }
                key={n.href}
                href={n.href}
              >
                {n.label}
                {n.href === "/community" && eventCount > 0 && (
                  <span
                    className="count"
                    aria-label={`${eventCount} new nearby events`}
                  >
                    {eventCount}
                  </span>
                )}
                {n.href === "/messages" && unread > 0 && (
                  <span className="count">{unread}</span>
                )}
              </Link>
            ))}
          </nav>
          <div className="nav-user">
            <span className="local-pill">
              <span /> {config.demo ? "LOCAL BETA" : "INVITE ONLY"}
            </span>
            <button
              className="avatar-button"
              onClick={() => router.push("/profile")}
              aria-label="Open my profile"
            >
              <Avatar name={me.name} size="small" />
            </button>
            <button
              className="icon-button mobile-menu"
              onClick={() => setMenu(!menu)}
              aria-label="Toggle navigation"
            >
              <Menu size={20} />
            </button>
          </div>
        </div>
      </header>
      <main className="main-wrap">
        <ErrorNote error={error} />
        {path === "/community" ? (
          <Community me={me} onProfile={setCommunityProfile} />
        ) : path === "/messages" ? (
          <Inbox me={me} />
        ) : path === "/profile" ? (
          <EditProfile me={me} refresh={refresh} logout={logout} />
        ) : path === "/admin" && me.role === "admin" ? (
          <Admin />
        ) : (
          <Discover me={me} formUrl={config.formUrl} />
        )}
      </main>
      {communityProfile && (
        <ProfileModal
          profile={communityProfile}
          onClose={() => setCommunityProfile(null)}
        />
      )}
      <footer className="footer">
        <span>Good neighbors. Stronger communities.</span>
        <span>
          Made for the five boroughs <span className="tiny-heart">♥</span>
          <button onClick={logout}>
            Sign out <LogOut size={13} />
          </button>
        </span>
      </footer>
    </div>
  );
}

function Landing({
  config,
  onLogin,
  initialError,
}: {
  config: {
    demo: boolean;
    google: boolean;
    formUrl: string | null;
    nativeSignup?: boolean;
  };
  onLogin: () => Promise<void>;
  initialError: string;
}) {
  const [accessState, setAccessState] = useState("");
  const [error, setError] = useState(initialError),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    const e = new URLSearchParams(window.location.search).get("error");
    if (e) setError(e);
    setAccessState(
      new URLSearchParams(window.location.search).get("status") || "",
    );
  }, []);
  useEffect(() => {
    if (initialError) setError(initialError);
  }, [initialError]);
  async function demo(email: string) {
    setBusy(true);
    try {
      await post("/auth/demo", { email });
      await onLogin();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="landing">
      <header className="topbar">
        <div className="nav-inner">
          <Logo />
          <span className="local-pill">
            <span /> A LITTLE MORE CONNECTED
          </span>
        </div>
      </header>
      <main className="landing-content">
        <div className="eyebrow">
          <span className="green-dot" /> FIVE BOROUGHS. COUNTLESS CONNECTIONS.
        </div>
        <h1>
          Your people.
          <br />A little <em>closer.</em>
        </h1>
        <p className="landing-description">
          A familiar language. A shared experience. A helping hand around the
          corner. Find the New Yorkers who make this city feel like home.
        </p>
        <div className="landing-actions">
          <a
            className="button primary"
            href={
              config.nativeSignup ? "/api/auth/cognito" : "/api/auth/google"
            }
          >
            {config.nativeSignup
              ? "Google or email code"
              : "Continue with Google"}{" "}
            <ArrowRight size={18} />
          </a>
          {(config.nativeSignup || config.formUrl) && (
            <a
              className="button secondary"
              href={config.nativeSignup ? "/signup" : config.formUrl!}
              target="_blank"
              rel="noreferrer"
            >
              Join the community <ArrowUpRight size={18} />
            </a>
          )}
        </div>
        <p className="quiet">
          Your email is private to you and the community host for sign-in and
          approval. No phone number or exact address required.
        </p>
        {accessState && (
          <section className="panel" role="status">
            <h2>
              {{
                pending: "Awaiting host approval",
                wrong_account: "Check your Google account",
                suspended: "Membership suspended",
                temporary: "Please try again shortly",
                expired: "Start sign-in again",
              }[accessState] || "Sign-in needs attention"}
            </h2>
            <p>
              {
                {
                  pending:
                    "Your submission is waiting for review. Your host will share an invitation after approval.",
                  wrong_account:
                    "Choose the Google account whose email you entered on the form. If you just submitted, ask your host to import and approve it.",
                  suspended:
                    "Contact your community host to discuss restoring access.",
                  temporary:
                    "The service is temporarily unavailable. Your profile has not changed.",
                  expired:
                    "Your sign-in session expired. Use the sign-in button above to try again.",
                }[accessState]
              }
            </p>
          </section>
        )}
        <ErrorNote error={error} />
        <p className="quiet">
          Submit the form → host imports and approves → receive your invitation
          → sign in with that Google account.
        </p>
        <div className="landing-values">
          <span>
            <ShieldCheck /> Members, not strangers
          </span>
          <span>
            <MapPin /> Rooted in NYC
          </span>
          <span>
            <HeartHandshake /> Help goes both ways
          </span>
        </div>
        {config.demo && (
          <section className="demo-box">
            <div>
              <span className="eyebrow">EXPLORE THE LOCAL BETA</span>
              <h3>Meet your fictional neighbors</h3>
              <p>
                Try both sides of a conversation. These are sample accounts, not
                real people.
              </p>
            </div>
            <div className="demo-buttons">
              <button disabled={busy} onClick={() => demo("maya@example.com")}>
                <Avatar name="Maya Rahman" size="small" />
                <span>
                  Maya <small>Community host</small>
                </span>
                <ArrowRight size={16} />
              </button>
              <button disabled={busy} onClick={() => demo("arif@example.com")}>
                <Avatar name="Arif Chowdhury" size="small" />
                <span>
                  Arif <small>Member</small>
                </span>
                <ArrowRight size={16} />
              </button>
            </div>
          </section>
        )}
        <Cityscape />
      </main>
      <footer className="landing-footer">
        A big city. A smaller circle. <span>NEW YORK, TOGETHER.</span>
      </footer>
    </div>
  );
}

function Cityscape() {
  return (
    <div className="cityscape" aria-hidden="true">
      <div className="sun" />
      {[
        60, 100, 76, 140, 95, 180, 115, 80, 135, 100, 65, 110, 165, 90, 130, 70,
        105, 150, 80, 60,
      ].map((h, i) => (
        <div
          key={i}
          className={`building building-${i % 4}`}
          style={{ height: h }}
        >
          {Array.from({ length: Math.floor(h / 25) }).map((_, j) => (
            <i key={j} />
          ))}
        </div>
      ))}
    </div>
  );
}

function Discover({ me, formUrl }: { me: Member; formUrl: string | null }) {
  const [mode, setMode] = useState("recommended"),
    [zip, setZip] = useState(""),
    [neighborhood, setNeighborhood] = useState(""),
    [occupation, setOccupation] = useState(""),
    [specialty, setSpecialty] = useState(""),
    [help, setHelp] = useState("");
  const [sharedCulture, setSharedCulture] = useState(false),
    [preferenceVersion, setPreferenceVersion] = useState(0);
  useEffect(() => {
    api("/preferences")
      .then((p) => setSharedCulture(p.sharedCulture))
      .catch(() => {});
  }, []);
  const [q, setQ] = useState(""),
    [language, setLanguage] = useState(""),
    [culture, setCulture] = useState(""),
    [country, setCountry] = useState(""),
    [interest, setInterest] = useState(""),
    [radius, setRadius] = useState("all"),
    [page, setPage] = useState(1);
  const [data, setData] = useState<any>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [selected, setSelected] = useState<Profile | null>(null),
    [extra, setExtra] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    const timer = setTimeout(() => {
      const params = new URLSearchParams({
        mode,
        zip,
        neighborhood,
        occupation,
        specialty,
        help,
        q,
        language,
        culture,
        country,
        interest,
        radius,
        page: String(page),
      });
      api("/discover?" + params, { signal: controller.signal })
        .then((d) => {
          setData(d);
          setError("");
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 220);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    q,
    language,
    culture,
    country,
    interest,
    radius,
    page,
    mode,
    zip,
    neighborhood,
    occupation,
    specialty,
    help,
    preferenceVersion,
  ]);
  function reset() {
    setQ("");
    setLanguage("");
    setCulture("");
    setCountry("");
    setInterest("");
    setRadius("all");
    setZip("");
    setNeighborhood("");
    setOccupation("");
    setSpecialty("");
    setHelp("");
    setMode("recommended");
    setPage(1);
  }
  return (
    <>
      <section className="welcome">
        <div>
          <div className="eyebrow">YOUR CITY. YOUR COMMUNITY.</div>
          <h1>
            A big city.
            <br />A <em>closer</em> community.
          </h1>
          <p>
            Find familiar faces, shared experiences, and a little help nearby.
          </p>
          <div className="welcome-bottom">
            <span className="overlapping-avatars">
              <Avatar name="Arif Chowdhury" size="tiny" />
              <Avatar name="Sofia Martinez" size="tiny" />
              <Avatar name="Jin Park" size="tiny" />
            </span>
            <span>New connections start with a hello.</span>
          </div>
        </div>
        <div className="welcome-art">
          <span className="floating-label label-one">
            <MapPin size={15} /> Your corner of NYC
          </span>
          <Cityscape />
          <span className="floating-label label-two">
            <HeartHandshake size={16} /> A neighbor can help.
          </span>
        </div>
      </section>
      <div className="content-columns">
        <section className="directory">
          <div className="section-heading">
            <div>
              <h2>
                Discover your people <span className="heading-dot" />
              </h2>
              <p>Different stories. Something in common.</p>
            </div>
            <span className="location-chip">
              <MapPin size={14} />
              {me.neighborhood} <span>· {me.zip}</span>
            </span>
          </div>
          <div className="filter-row" aria-label="Recommendation sections">
            {[
              ["recommended", "Recommended connections"],
              ["nearby", "People nearby"],
              ["help_me", "People who can help me"],
              ["i_can_help", "People I could help"],
              ["shared", "Shared interests and occupations"],
            ].map(([value, label]) => (
              <button
                key={value}
                className={`filter-select ${mode === value ? "selected" : ""}`}
                onClick={() => {
                  setMode(value);
                  setPage(1);
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="filter-row">
            {[
              ["ZIP", zip, setZip, data?.filters.zips],
              [
                "Neighborhood",
                neighborhood,
                setNeighborhood,
                data?.filters.neighborhoods,
              ],
              [
                "Occupation",
                occupation,
                setOccupation,
                data?.filters.occupations,
              ],
              ["Skills", specialty, setSpecialty, data?.filters.specialties],
            ].map(([label, value, setter, options]: any) => (
              <label className="filter-select" key={label}>
                <select
                  aria-label={label}
                  value={value}
                  onChange={(e) => {
                    setter(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">Any {label.toLowerCase()}</option>
                  {options?.map((v: string) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
            ))}
            <label className="filter-select">
              <select
                aria-label="Help direction"
                value={help}
                onChange={(e) => {
                  setHelp(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">Any help direction</option>
                <option value="receive">Can help me</option>
                <option value="give">I can help</option>
                <option value="both">Help each other</option>
              </select>
            </label>
          </div>
          <label className="preference">
            <input
              type="checkbox"
              checked={sharedCulture}
              onChange={async (e) => {
                const value = e.target.checked;
                try {
                  await api("/preferences", {
                    method: "PUT",
                    body: JSON.stringify({ sharedCulture: value }),
                  });
                  setSharedCulture(value);
                  setPreferenceVersion((v) => v + 1);
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            />{" "}
            Prefer shared culture when other matches are equal
          </label>
          <p className="quiet">
            Distance uses ZIP centers. Neighborhood labels are approximate.
          </p>
          <div className="search-box">
            <Search size={20} />
            <input
              aria-label="Search people and expertise"
              placeholder="Try gardening, programming, realtor, or your birthplace"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
            {q && (
              <button
                className="icon-button"
                aria-label="Clear search"
                onClick={() => setQ("")}
              >
                <X size={16} />
              </button>
            )}
            <span className="search-key">⌕</span>
          </div>
          <div className="filter-row">
            <label className="filter-select">
              <MapPin size={14} />
              <select
                aria-label="Distance"
                value={radius}
                onChange={(e) => {
                  setRadius(e.target.value);
                  setPage(1);
                }}
              >
                <option value="same">My ZIP code</option>
                <option value="2">Within 2 miles</option>
                <option value="5">Within 5 miles</option>
                <option value="all">All of NYC</option>
              </select>
              <ChevronDown size={12} />
            </label>
            <label className="filter-select">
              <Globe2 size={14} />
              <select
                aria-label="Language"
                value={language}
                onChange={(e) => {
                  setLanguage(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">Any language</option>
                {data?.filters.languages.map((s: string) => (
                  <option key={s} value={s}>
                    {title(s)}
                  </option>
                ))}
              </select>
              <ChevronDown size={12} />
            </label>
            <label className="filter-select">
              <Users size={14} />
              <select
                aria-label="Culture"
                value={culture}
                onChange={(e) => {
                  setCulture(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">Any culture</option>
                {data?.filters.cultures.map((s: string) => (
                  <option key={s} value={s}>
                    {title(s)}
                  </option>
                ))}
              </select>
              <ChevronDown size={12} />
            </label>
            <label className="filter-select">
              <Globe2 size={14} />
              <select
                aria-label="Country of origin"
                value={country}
                onChange={(e) => {
                  setCountry(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">Any country of origin</option>
                {data?.filters.countries.map((c: string) => (
                  <option key={c} value={c}>
                    {title(c)}
                  </option>
                ))}
              </select>
            </label>
            <button
              className={`filter-select ${extra ? "selected" : ""}`}
              onClick={() => setExtra(!extra)}
            >
              <SlidersHorizontal size={14} /> Interests
            </button>
            {(q ||
              language ||
              culture ||
              country ||
              interest ||
              radius !== "5") && (
              <button className="text-button" onClick={reset}>
                Reset
              </button>
            )}
          </div>
          {extra && (
            <div className="interest-filter">
              <label>
                Shared interest{" "}
                <select
                  aria-label="Interest"
                  value={interest}
                  onChange={(e) => {
                    setInterest(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">Any interest</option>
                  {data?.filters.interests.map((s: string) => (
                    <option key={s} value={s}>
                      {title(s)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          <div className="results-heading">
            <span>
              {loading
                ? "Finding neighbors…"
                : `${data?.total ?? 0} neighbors to get to know`}
            </span>
            <span>
              <Sparkles size={13} /> Best matches for you
            </span>
          </div>
          <ErrorNote error={error} />
          <div className={`profile-grid ${loading ? "is-loading" : ""}`}>
            {data?.profiles.map((p: Profile) => (
              <ProfileCard
                key={p.id}
                profile={p}
                onClick={() => setSelected(p)}
              />
            ))}
          </div>
          {!loading && data?.total === 0 && (
            <Empty
              title="Your people are out there"
              text="Try a wider distance or fewer filters to meet more neighbors."
            />
          )}
          {data?.total > 12 && (
            <div className="pagination">
              <button
                className="button secondary"
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </button>
              <span>
                Page {page} of {Math.ceil(data.total / 12)}
              </span>
              <button
                className="button secondary"
                disabled={page * 12 >= data.total}
                onClick={() => setPage(page + 1)}
              >
                Next
              </button>
            </div>
          )}
          <p className="directory-note">
            <ShieldCheck size={14} /> Only approved members can see these
            profiles. Distances are approximate.
          </p>
        </section>
        <aside className="sidebar">
          <section className="how-card">
            <span className="mini-icon">
              <HeartHandshake size={22} />
            </span>
            <h3>
              A little connection.
              <br />A lot of possibility.
            </h3>
            <p>
              You don’t need to know everyone.
              <br />
              Just the right someone.
            </p>
            <div className="how-step">
              <span>1</span>
              <div>
                <strong>Find common ground</strong>
                <p>A skill, a language, a shared story.</p>
              </div>
            </div>
            <div className="how-step">
              <span>2</span>
              <div>
                <strong>Say a thoughtful hello</strong>
                <p>Send a message request.</p>
              </div>
            </div>
            <div className="how-step">
              <span>3</span>
              <div>
                <strong>Be there for each other</strong>
                <p>Good neighbors make a difference.</p>
              </div>
            </div>
          </section>
          <section className="invite-card">
            <div className="eyebrow">BETTER WITH YOUR PEOPLE</div>
            <h3>Know a good neighbor?</h3>
            <p>
              Help your circle grow. Invite a friend who has something to share.
            </p>
            {formUrl ? (
              <a href={formUrl} target="_blank" rel="noreferrer">
                Share the community form <ArrowUpRight size={16} />
              </a>
            ) : (
              <span className="quiet">
                Your host will share the invitation form.
              </span>
            )}
          </section>
          <section className="community-note">
            <ShieldCheck size={17} />
            <p>
              Built on kindness, curiosity, and respect. Shared backgrounds are
              a starting point, not a guarantee of trust.
            </p>
          </section>
          {me.demo && (
            <div className="sample-note">
              LOCAL DEMO
              <br />
              <span>All profiles shown in this demo are fictional.</span>
            </div>
          )}
        </aside>
      </div>
      {selected && (
        <ProfileModal profile={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}

function ProfileCard({
  profile: p,
  onClick,
}: {
  profile: Profile;
  onClick: () => void;
}) {
  return (
    <article className="profile-card">
      <div className="card-top">
        <Avatar name={p.name} />
        <span className="distance">
          <MapPin size={12} />
          {p.distance === 0 ? "Same ZIP" : `${p.distance} mi away`}
        </span>
      </div>
      <button className="profile-name" onClick={onClick}>
        {p.name}
        <ArrowUpRight size={16} />
      </button>
      <p className="occupation">{p.occupation}</p>
      <p className="card-location">
        <MapPin size={12} />
        {p.neighborhood}, {p.borough === p.neighborhood ? "NYC" : p.borough}
      </p>
      <div className="card-tags">
        {p.expertise.slice(0, 2).map((s) => (
          <Tag key={s}>{title(s)}</Tag>
        ))}
        {p.expertise.length > 2 && (
          <span className="plus-tag">+{p.expertise.length - 2}</span>
        )}
      </div>
      <p className="card-bio">{p.bio}</p>
      <div className="card-languages">
        <Globe2 size={13} />
        {p.languages.map(title).join(", ")}
      </div>
      <div className="card-bottom">
        <span>
          <span className="green-dot" />
          {p.reasons?.includes("In your ZIP code")
            ? "Your neighborhood"
            : p.reasons?.some((s) => s.startsWith("Can help"))
              ? "A skill you’re looking for"
              : "Open to connecting"}
        </span>
        <button onClick={onClick} aria-label={`Meet ${p.name}`}>
          <ArrowRight size={17} />
        </button>
      </div>
    </article>
  );
}

function ProfileModal({
  profile: p,
  onClose,
}: {
  profile: Profile;
  onClose: () => void;
}) {
  const [text, setText] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [reporting, setReporting] = useState(false),
    [reason, setReason] = useState(""),
    [reported, setReported] = useState(false);
  const router = useRouter();
  const dialog = useRef<HTMLElement>(null);
  const requestKey = useRef<{ body: string; id: string } | null>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    dialog.current?.querySelector<HTMLElement>("button")?.focus();
    const listener = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const nodes = dialog.current?.querySelectorAll<HTMLElement>(
          "button:not([disabled]),textarea,input,a[href]",
        );
        if (!nodes?.length) return;
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", listener);
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", listener);
      document.body.style.overflow = old;
      previous?.focus();
    };
  }, [onClose]);
  async function connect(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      if (!requestKey.current || requestKey.current.body !== text)
        requestKey.current = { body: text, id: crypto.randomUUID() };
      const c = await post("/conversations", {
        clientMessageId: requestKey.current.id,
        recipientId: p.id,
        body: text,
      });
      router.push("/messages?conversation=" + c.id);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function block() {
    if (
      !window.confirm(
        `Block ${p.name}? You will no longer see each other or be able to message.`,
      )
    )
      return;
    try {
      await post("/blocks/" + p.id);
      onClose();
      window.location.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={dialog}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={p.name}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="modal-close icon-button"
          onClick={onClose}
          aria-label="Close profile"
        >
          <X />
        </button>
        <div className="profile-modal-heading">
          <Avatar name={p.name} size="large" />
          <div>
            <div className="eyebrow">YOUR NYC NEIGHBOR</div>
            <h2>{p.name}</h2>
            <p>
              {p.occupation}
              {p.workplace && ` · ${p.workplace}`}
            </p>
          </div>
        </div>
        <p className="card-location">
          <MapPin size={15} />
          {p.neighborhood} · {p.zip} · {p.distance} miles away, approximately
        </p>
        <p className="profile-bio">{p.bio}</p>
        <div className="profile-details">
          {[
            ["I can help with", p.expertise],
            ["Languages I speak", p.languages],
            ["My interests", p.interests],
            ["Looking for help with", p.needs],
            ["My cultural background", p.cultures],
            ["Country of origin", p.countries],
          ].map(
            ([label, values]) =>
              (values as string[]).length > 0 && (
                <div key={label as string}>
                  <h4>{label as string}</h4>
                  <div className="tags">
                    {(values as string[]).map((v) => (
                      <Tag key={v}>{title(v)}</Tag>
                    ))}
                  </div>
                </div>
              ),
          )}
        </div>
        {p.reasons?.length ? (
          <div className="match-note">
            <Sparkles size={17} />
            <span>{p.reasons.join(" · ")}</span>
          </div>
        ) : null}
        <form onSubmit={connect}>
          <h3>Good connections start with a hello.</h3>
          <textarea
            required
            maxLength={2000}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={`Hi ${p.name.split(" ")[0]}! I’m a neighbor and I’d love to connect about…`}
            aria-label="Introduction message"
          />
          <p className="quiet">
            They’ll accept your request before the conversation continues. Your
            email stays private.
          </p>
          <ErrorNote error={error} />
          <button
            className="button primary full"
            disabled={busy || !text.trim()}
          >
            {busy ? "Sending…" : "Send a message request"}{" "}
            <ArrowRight size={17} />
          </button>
        </form>
        <div className="safety-actions">
          <button onClick={() => setReporting(!reporting)}>
            <Flag size={13} /> Report
          </button>
          <button onClick={block}>
            <Ban size={13} /> Block member
          </button>
        </div>
        {reporting && (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await post("/reports", { memberId: p.id, reason });
                setReported(true);
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            {reported ? (
              <p className="success">Report sent to your community host.</p>
            ) : (
              <>
                <label>
                  What happened?
                  <textarea
                    required
                    minLength={5}
                    maxLength={1000}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <button className="button secondary">Send report</button>
              </>
            )}
          </form>
        )}
      </section>
    </div>
  );
}

function EditProfile({
  me,
  refresh,
  logout,
}: {
  me: Member;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}) {
  const [suggestions, setSuggestions] = useState<{
    occupations: string[];
    skills: string[];
  }>({ occupations: [], skills: [] });
  useEffect(() => {
    api("/suggestions")
      .then(setSuggestions)
      .catch(() => {});
  }, []);
  const [form, setForm] = useState<Record<string, string>>(() =>
      Object.fromEntries(
        [
          "name",
          "zip",
          "address",
          "occupation",
          "workplace",
          "bio",
          "languages",
          "cultures",
          "countries",
          "expertise",
          "interests",
          "needs",
        ].map((k) => [
          k,
          Array.isArray((me as any)[k])
            ? (me as any)[k].join(", ")
            : (me as any)[k] || "",
        ]),
      ),
    ),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false),
    [busy, setBusy] = useState(false),
    [blocks, setBlocks] = useState<any[]>([]),
    [zips, setZips] = useState<any[]>([]);
  useEffect(() => {
    api("/blocks")
      .then(setBlocks)
      .catch(() => {});
    api("/zips")
      .then(setZips)
      .catch(() => {});
  }, []);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setSaved(false);
    setError("");
    try {
      const values: any = { ...form };
      for (const k of [
        "languages",
        "cultures",
        "countries",
        "expertise",
        "interests",
        "needs",
      ])
        values[k] = form[k]
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean);
      await api("/me", { method: "PATCH", body: JSON.stringify(values) });
      await refresh();
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <LinkLogin />
      <div className="page-heading">
        <div className="eyebrow">BRING YOUR WHOLE SELF</div>
        <h1>
          Your corner of the community<span className="green-text">.</span>
        </h1>
        <p>
          Share your interests and background to find common ground. A display
          name is enough; a photo is not required.
        </p>
      </div>
      <div className="settings-grid">
        <form className="panel profile-form" onSubmit={save}>
          <div className="profile-modal-heading">
            <Avatar name={me.name} size="large" />
            <div>
              <h2>{me.name}</h2>
              <p>
                {me.email}{" "}
                <span className="private-label">Only visible to you</span>
              </p>
            </div>
          </div>
          <div className="form-grid">
            {[
              ["name", "Display name"],
              ["zip", "NYC ZIP code (required)"],
              ["address", "Street address (optional, private)"],
              ["occupation", "Your work / occupation"],
              ["workplace", "Workplace (optional)"],
              ["languages", "Languages you speak"],
              ["expertise", "What you can help with"],
              ["interests", "Hobbies, interests, and causes you care about"],
              ["needs", "What you’d like help with"],
              ["cultures", "Cultural identity (optional)"],
              ["countries", "Country of origin (optional)"],
            ].map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  required={[
                    "name",
                    "zip",
                    "occupation",
                    "languages",
                    "expertise",
                  ].includes(key)}
                  value={form[key]}
                  maxLength={
                    key === "address"
                      ? 240
                      : key === "zip"
                        ? 5
                        : [
                              "languages",
                              "expertise",
                              "interests",
                              "needs",
                              "cultures",
                              "countries",
                            ].includes(key)
                          ? 720
                          : 100
                  }
                  pattern={key === "zip" ? "[0-9]{5}" : undefined}
                  list={
                    key === "zip"
                      ? "zip-list"
                      : key === "occupation"
                        ? "occupation-list"
                        : key === "expertise" || key === "needs"
                          ? "skill-list"
                          : undefined
                  }
                  onChange={(e) => {
                    setForm({ ...form, [key]: e.target.value });
                    setSaved(false);
                  }}
                />
                {[
                  "languages",
                  "expertise",
                  "interests",
                  "needs",
                  "cultures",
                  "countries",
                ].includes(key) && (
                  <small>Separate multiple entries with commas.</small>
                )}
              </label>
            ))}
          </div>
          <datalist id="occupation-list">
            {suggestions.occupations.map((v) => (
              <option key={v} value={v} />
            ))}
          </datalist>
          <datalist id="skill-list">
            {suggestions.skills.map((v) => (
              <option key={v} value={v} />
            ))}
          </datalist>
          <datalist id="zip-list">
            {zips.map((z) => (
              <option key={z.zip} value={z.zip}>
                {z.neighborhood}, {z.borough}
              </option>
            ))}
          </datalist>
          <label>
            A little about you
            <textarea
              maxLength={800}
              value={form.bio}
              onChange={(e) => setForm({ ...form, bio: e.target.value })}
            />
          </label>
          <ErrorNote error={error} />
          <div className="form-actions">
            <button className="button primary" disabled={busy}>
              {busy ? "Saving…" : "Save profile"} <Check size={16} />
            </button>
            {saved && (
              <span className="success">
                <CheckCircle2 size={16} /> Your profile is up to date.
              </span>
            )}
          </div>
        </form>
        <aside>
          <section className="panel">
            <EyeOff size={22} />
            <h3>Your contact details stay private.</h3>
            <p>
              No phone number is collected. A street address is optional and
              hidden from other members; the host can review it during signup.
              Your required ZIP gives approximate proximity. Avoid contact
              details in your bio; use in-app messages.
            </p>
            <h3>You choose when to be visible.</h3>
            <p>
              Hiding your profile removes you and your posts from discovery.
              Existing conversations remain available.
            </p>
            <button
              className="button secondary full"
              onClick={async () => {
                try {
                  await post("/me/visibility", { visible: !me.visible });
                  await refresh();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              {me.visible ? "Hide my profile" : "Show my profile"}
            </button>
          </section>
          <section className="panel">
            <h3>Blocked members</h3>
            {blocks.length ? (
              blocks.map((b) => (
                <div className="blocked-row" key={b.id}>
                  <span>{b.name}</span>
                  <button
                    className="text-button"
                    onClick={async () => {
                      await api("/blocks/" + b.id, { method: "DELETE" });
                      setBlocks(blocks.filter((x) => x.id !== b.id));
                    }}
                  >
                    Unblock
                  </button>
                </div>
              ))
            ) : (
              <p>No blocked members.</p>
            )}
          </section>
          <section className="panel danger-zone">
            <h3>Leave the community</h3>
            <p>
              Your profile and login details will be deleted. Existing message
              text remains with a “Deleted member” label. Google Form responses
              must be deleted separately by the host.
            </p>
            <button
              className="text-button danger"
              onClick={async () => {
                if (
                  !window.confirm(
                    "Permanently delete your profile? This cannot be undone.",
                  )
                )
                  return;
                try {
                  await api("/me", { method: "DELETE" });
                  await logout();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Delete my profile
            </button>
          </section>
        </aside>
      </div>
    </>
  );
}

function Admin() {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [importResult, setImportResult] = useState<any[]>([]),
    [busy, setBusy] = useState(false);
  const refresh = useCallback(
    () =>
      api("/admin")
        .then(setData)
        .catch((e) => setError(e.message)),
    [],
  );
  useEffect(() => {
    refresh();
  }, [refresh]);
  async function action(path: string, payload: unknown) {
    setError("");
    setBusy(true);
    try {
      await post(path, payload);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div className="eyebrow">GROW WITH CARE</div>
        <h1>
          A good community starts here<span className="green-text">.</span>
        </h1>
        <p>
          Welcome neighbors, review profiles, and keep the community respectful.
        </p>
      </div>
      <ErrorNote error={error} />
      <div className="admin-stats">
        <div>
          <span>Awaiting a welcome</span>
          <strong>{data?.submissions.length ?? "—"}</strong>
        </div>
        <div>
          <span>Community members</span>
          <strong>{data?.members.length ?? "—"}</strong>
        </div>
        <div>
          <span>Open reports</span>
          <strong>{data?.reports.length ?? "—"}</strong>
        </div>
        <div>
          <span>Graph updates pending</span>
          <strong>{data?.graph.pending ?? "—"}</strong>
        </div>
      </div>
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Profile submissions</h2>
            <p>
              Approval grants access to the submitted Google email. Review
              carefully.
            </p>
          </div>
          <label className="button secondary upload-button">
            <Upload size={16} /> Import responses
            <input
              type="file"
              accept="application/json,.json"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                setError("");
                try {
                  if (file.size > 1048576)
                    throw new Error("Choose a JSON export smaller than 1 MB.");
                  const raw = JSON.parse(await file.text());
                  const result = await post("/admin/import", {
                    submissions: Array.isArray(raw) ? raw : raw.submissions,
                  });
                  setImportResult(result.results);
                  await refresh();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            />
          </label>
        </div>
        {importResult.length > 0 && (
          <div className="import-results">
            {importResult.map((r: any) => (
              <p key={r.row} className={r.error ? "danger" : "success"}>
                Row {r.row}:{" "}
                {r.error ||
                  (r.duplicate ? "Already imported" : "Ready for review")}
              </p>
            ))}
          </div>
        )}
        {data?.submissions.length ? (
          data.submissions.map((s: any) => (
            <div className="submission" key={s.id}>
              <div>
                <h3>
                  {s.payload.profile.name}{" "}
                  {s.existing_member && <Tag>Updates existing profile</Tag>}
                </h3>
                <p>
                  {s.email} · {s.payload.profile.zip} ·{" "}
                  {s.payload.profile.occupation}
                </p>
                <p>{s.payload.profile.bio}</p>
                <details>
                  <summary>Review all submitted fields</summary>
                  <dl>
                    {Object.entries(s.payload.profile).map(([key, value]) => (
                      <div key={key}>
                        <dt>{title(key)}</dt>
                        <dd>
                          {Array.isArray(value)
                            ? value.join(", ")
                            : String(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </details>
              </div>
              <div className="row-actions">
                <button
                  disabled={busy}
                  className="button primary"
                  onClick={() =>
                    action("/admin/submissions/" + s.id, { approve: true })
                  }
                >
                  Approve <Check size={15} />
                </button>
                <button
                  disabled={busy}
                  className="button secondary"
                  onClick={() =>
                    action("/admin/submissions/" + s.id, { approve: false })
                  }
                >
                  Reject
                </button>
              </div>
            </div>
          ))
        ) : (
          <Empty
            title="All caught up"
            text="New form submissions will appear here for review."
          />
        )}
      </section>
      <section className="panel">
        <h2>Community reports</h2>
        {data?.reports.length ? (
          data.reports.map((r: any) => (
            <div className="submission" key={r.id}>
              <div>
                <h3>{r.reported_name}</h3>
                <p>{r.reason}</p>
              </div>
              <div className="row-actions">
                <button
                  disabled={busy}
                  className="button secondary"
                  onClick={() =>
                    action("/admin/reports/" + r.id + "/resolve", {})
                  }
                >
                  Resolve
                </button>
                <button
                  disabled={busy}
                  className="text-button danger"
                  onClick={() =>
                    action("/admin/members/" + r.reported_id, {
                      status: "suspended",
                    })
                  }
                >
                  Suspend member
                </button>
              </div>
            </div>
          ))
        ) : (
          <p>No open reports.</p>
        )}
      </section>
      <section className="panel">
        <h2>Your neighbors</h2>
        <div className="member-table">
          {data?.members.map((m: any) => (
            <div className="member-row" key={m.id}>
              <Avatar name={m.name} size="small" />
              <div>
                <strong>{m.name}</strong>
                <small>{m.email}</small>
              </div>
              {m.status === "approved" && !m.demo && (
                <button
                  className="text-button"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(
                        `Hi ${m.name}, your Neighbor NYC profile is approved. Open ${data.appUrl} and sign in with ${m.email}. You do not need an administrator account.`,
                      );
                      setError("Invitation copied.");
                    } catch {
                      setError("Could not copy. App address: " + data.appUrl);
                    }
                  }}
                >
                  Copy invitation
                </button>
              )}
              <span className={`status ${m.status}`}>
                {m.demo ? "Demo · " : ""}
                {m.status}
              </span>
              <button
                disabled={busy}
                className="text-button"
                onClick={() =>
                  action("/admin/members/" + m.id, {
                    status: m.status === "suspended" ? "approved" : "suspended",
                  })
                }
              >
                {m.status === "suspended" ? "Restore" : "Suspend"}
              </button>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
