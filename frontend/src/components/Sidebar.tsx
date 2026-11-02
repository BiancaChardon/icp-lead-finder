"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { apiRequest } from "@/lib/api";
import { useUser } from "./UserContext";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/" },
  { label: "Search History", href: "/history" },
  { label: "Saved Leads", href: "/saved" },
  { label: "Settings", href: "/settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  const user = useUser();
  const [signingOut, setSigningOut] = useState(false);

  async function signOut() {
    setSigningOut(true);
    try {
      await apiRequest("/api/auth/logout", { method: "POST" });
    } finally {
      window.location.assign("/login");
    }
  }

  return (
    <aside className="sidebar">
      <div className="brand">ICP Lead Finder</div>
      <nav aria-label="Main">
        <ul className="nav">
          {NAV_ITEMS.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <li key={item.href}>
                <Link href={item.href} className="nav-link" aria-current={active ? "page" : undefined}>
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="sidebar-footer">
        <div className="sidebar-user">
          <span className="sidebar-user-name">{user.full_name}</span>
          <span className="sidebar-user-role">{user.role === "admin" ? "Administrator" : "Team member"}</span>
        </div>
        <button type="button" className="btn btn-ghost-dark" onClick={signOut} disabled={signingOut}>
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
      </div>
    </aside>
  );
}
