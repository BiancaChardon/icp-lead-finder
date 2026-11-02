import { redirect } from "next/navigation";
import { LoginForm } from "./LoginForm";
import { getSession } from "@/lib/server-auth";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  if ((await getSession()).state === "authenticated") redirect("/");

  return (
    <main className="centered-page">
      <div className="card narrow-card">
        <div className="login-brand">ICP Lead Finder</div>
        <h1>Sign in</h1>
        <p className="muted">For authorized team members only. Ask an administrator for an account.</p>
        <LoginForm />
      </div>
    </main>
  );
}
