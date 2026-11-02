import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "ICP Lead Finder",
  description: "B2B prospecting for authorized team members.",
};

const navItems: { label: string; href?: string }[] = [
  { label: "Dashboard", href: "/" },
  { label: "Search History" },
  { label: "Saved Leads" },
  { label: "Settings" },
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <div className="brand">ICP Lead Finder</div>
            <nav aria-label="Main">
              <ul className="nav">
                {navItems.map((item) =>
                  item.href ? (
                    <li key={item.label}>
                      <Link href={item.href} className="nav-link" aria-current="page">
                        {item.label}
                      </Link>
                    </li>
                  ) : (
                    <li key={item.label}>
                      <span className="nav-link nav-link-disabled" aria-disabled="true">
                        {item.label}
                        <span className="badge">Soon</span>
                      </span>
                    </li>
                  ),
                )}
              </ul>
            </nav>
          </aside>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
