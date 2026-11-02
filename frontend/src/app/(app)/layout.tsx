import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { Sidebar } from "@/components/Sidebar";
import { UserProvider } from "@/components/UserContext";
import { getSession } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const result = await getSession();

  if (result.state === "anonymous") redirect("/login");
  if (result.state === "unavailable") {
    return (
      <main className="centered-page">
        <div className="card narrow-card">
          <h1>Service unavailable</h1>
          <p className="muted">The application backend could not be reached. Please try again in a moment.</p>
        </div>
      </main>
    );
  }

  return (
    <UserProvider user={result.session.user}>
      <div className="shell">
        <Sidebar />
        <main className="content">{children}</main>
      </div>
    </UserProvider>
  );
}
