"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/client";
export default function LinkLogin() {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    api("/config")
      .then((c) => setEnabled(c.nativeSignup))
      .catch(() => {});
  }, []);
  return enabled ? (
    <form action="/api/auth/cognito/link" method="post" className="panel">
      <p>
        Add a verified login to this profile without changing your membership.
      </p>
      <button className="button secondary">
        Link Google or email-code login
      </button>
    </form>
  ) : null;
}
