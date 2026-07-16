import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Me } from "../types";
import { CompassIcon, GearIcon, SignOutIcon } from "./icons";

async function logout() {
  try { await api.logout(); } catch { /* clear client state regardless */ }
  window.location.href = "/";
}

/** Derive up-to-two-letter initials for the avatar. */
function initials(me: Me): string {
  const name = me.display_name?.trim();
  if (name) {
    const parts = name.split(/\s+/);
    return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
  }
  return (me.email[0] || "?").toUpperCase();
}

/** Top-right identity menu: avatar → dropdown with who you are, Settings, and
 * Log out. Logout only appears behind Cloudflare Access (nothing to end in dev). */
export function UserMenu({ me, onOpenSettings, onStartTour }: {
  me: Me;
  onOpenSettings: () => void;
  onStartTour: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="usermenu" ref={ref}>
      <button
        className="avatar-btn"
        title={me.email}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {initials(me)}
      </button>
      {open && (
        <div className="usermenu-pop" role="menu">
          <div className="usermenu-id">
            {me.display_name && <div className="usermenu-name">{me.display_name}</div>}
            <div className="usermenu-email">{me.email}</div>
          </div>
          <button className="usermenu-item" role="menuitem" onClick={() => { setOpen(false); onStartTour(); }}>
            <CompassIcon size={14} /> Take a tour
          </button>
          <button className="usermenu-item" role="menuitem" onClick={() => { setOpen(false); onOpenSettings(); }}>
            <GearIcon size={14} /> Settings
          </button>
          <button className="usermenu-item" role="menuitem" onClick={() => { setOpen(false); logout(); }}>
            <SignOutIcon size={14} /> Log out
          </button>
        </div>
      )}
    </div>
  );
}
