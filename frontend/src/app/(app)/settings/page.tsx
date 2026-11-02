"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useAuthRequired, useUser } from "@/components/UserContext";
import { apiJson, apiRequest, errorText } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { ProviderInfo, Role, User } from "@/lib/types";

const MIN_PASSWORD = 12;

function Message({ kind, text }: { kind: "success" | "error"; text: string | null }) {
  if (!text) return null;
  return (
    <div className={`alert alert-${kind}`} role={kind === "error" ? "alert" : "status"}>
      {text}
    </div>
  );
}

function ChangePassword() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (next.length < MIN_PASSWORD) return setError(`New password must be at least ${MIN_PASSWORD} characters.`);
    if (next !== confirm) return setError("New passwords do not match.");
    setBusy(true);
    try {
      await apiRequest("/api/auth/change-password", {
        method: "POST",
        body: { current_password: current, new_password: next },
      });
      setCurrent("");
      setNext("");
      setConfirm("");
      setSuccess("Password changed. Other signed-in sessions were signed out.");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <label className="field">
        <span>Current password</span>
        <input type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
      </label>
      <label className="field">
        <span>New password</span>
        <input type="password" autoComplete="new-password" required minLength={MIN_PASSWORD} value={next} onChange={(e) => setNext(e.target.value)} />
        <small className="hint">At least {MIN_PASSWORD} characters</small>
      </label>
      <label className="field">
        <span>Confirm new password</span>
        <input type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      </label>
      <Message kind="error" text={error} />
      <Message kind="success" text={success} />
      <div>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Saving…" : "Change password"}
        </button>
      </div>
    </form>
  );
}

function TeamManagement({ currentUserId }: { currentUserId: number }) {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "member" as Role });

  const load = useCallback(async () => {
    try {
      setUsers(await apiJson<User[]>("/api/users"));
    } catch (err) {
      setError(errorText(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      await action();
      setSuccess(message);
      await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function addUser(e: FormEvent) {
    e.preventDefault();
    if (form.password.length < MIN_PASSWORD) {
      setError(`Initial password must be at least ${MIN_PASSWORD} characters.`);
      return;
    }
    void run(async () => {
      await apiJson("/api/users", { method: "POST", body: { ...form, email: form.email.trim() } });
      setForm({ email: "", full_name: "", password: "", role: "member" });
    }, `Added ${form.email.trim()}. Share the initial password with them securely.`);
  }

  function resetPassword(user: User) {
    const password = window.prompt(`New password for ${user.email} (at least ${MIN_PASSWORD} characters):`);
    if (!password) return;
    if (password.length < MIN_PASSWORD) {
      setError(`Password must be at least ${MIN_PASSWORD} characters.`);
      return;
    }
    void run(
      () => apiRequest(`/api/users/${user.id}/password`, { method: "POST", body: { new_password: password } }),
      `Password reset for ${user.email}. Their sessions were signed out.`,
    );
  }

  return (
    <>
      <Message kind="error" text={error} />
      <Message kind="success" text={success} />
      <div className="table-wrapper">
        <table className="results-table">
          <caption className="visually-hidden">Team members</caption>
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Email</th>
              <th scope="col">Role</th>
              <th scope="col">Status</th>
              <th scope="col">Last sign-in</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const self = u.id === currentUserId;
              return (
                <tr key={u.id}>
                  <td className="cell-strong">{u.full_name}</td>
                  <td>{u.email}</td>
                  <td>
                    <select
                      aria-label={`Role for ${u.email}`}
                      value={u.role}
                      disabled={busy || self}
                      onChange={(e) =>
                        run(
                          () => apiJson(`/api/users/${u.id}`, { method: "PATCH", body: { role: e.target.value } }),
                          `Updated role for ${u.email}.`,
                        )
                      }
                    >
                      <option value="member">Member</option>
                      <option value="admin">Administrator</option>
                    </select>
                  </td>
                  <td>{u.is_active ? "Active" : <span className="muted">Deactivated</span>}</td>
                  <td className="nowrap">{formatDateTime(u.last_login_at)}</td>
                  <td className="col-action actions-inline">
                    <button type="button" className="btn btn-secondary btn-small" disabled={busy} onClick={() => resetPassword(u)}>
                      Reset password
                    </button>
                    {!self && (
                      <button
                        type="button"
                        className={`btn btn-small ${u.is_active ? "btn-danger" : "btn-secondary"}`}
                        disabled={busy}
                        onClick={() =>
                          run(
                            () => apiJson(`/api/users/${u.id}`, { method: "PATCH", body: { is_active: !u.is_active } }),
                            `${u.is_active ? "Deactivated" : "Reactivated"} ${u.email}.`,
                          )
                        }
                      >
                        {u.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h3 className="subheading">Add a team member</h3>
      <form className="form-grid" onSubmit={addUser}>
        <label className="field">
          <span>Full name</span>
          <input required maxLength={200} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        </label>
        <label className="field">
          <span>Email</span>
          <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </label>
        <label className="field">
          <span>Initial password</span>
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <small className="hint">At least {MIN_PASSWORD} characters. They can change it in Settings.</small>
        </label>
        <label className="field">
          <span>Role</span>
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            <option value="member">Member</option>
            <option value="admin">Administrator</option>
          </select>
        </label>
        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Add team member
          </button>
        </div>
      </form>
    </>
  );
}

export default function SettingsPage() {
  const user = useUser();
  const authRequired = useAuthRequired();
  // undefined while loading, null if the request failed
  const [provider, setProvider] = useState<ProviderInfo | null | undefined>(undefined);

  useEffect(() => {
    apiJson<ProviderInfo>("/api/search/provider")
      .then(setProvider)
      .catch(() => setProvider(null));
  }, []);

  return (
    <>
      <header className="page-header">
        <h1>Settings</h1>
      </header>

      {authRequired ? (
        <>
          <section className="card">
            <h2>Your account</h2>
            <dl className="details">
              <dt>Name</dt>
              <dd>{user.full_name}</dd>
              <dt>Email</dt>
              <dd>{user.email}</dd>
              <dt>Role</dt>
              <dd>{user.role === "admin" ? "Administrator" : "Team member"}</dd>
            </dl>
          </section>

          <section className="card">
            <h2>Change password</h2>
            <ChangePassword />
          </section>
        </>
      ) : (
        <section className="card">
          <h2>Access</h2>
          <p className="muted">
            Sign-in is turned off. Everyone who can open this site shares the same saved leads and search history.
            To require sign-in, set <code>AUTH_REQUIRED=true</code> on the server.
          </p>
        </section>
      )}

      <section className="card">
        <h2>Contact-data provider</h2>
        {provider === undefined ? (
          <p className="muted">Loading…</p>
        ) : provider ? (
          <dl className="details">
            <dt>Provider</dt>
            <dd>
              {provider.display_name} {provider.is_demo && <span className="demo-badge">DEMO</span>}
            </dd>
            <dt>Status</dt>
            <dd>
              {provider.is_demo
                ? "Demonstration mode. Results are fictional and not real contacts."
                : "Connected to a live provider. Usage may consume provider credits."}
            </dd>
          </dl>
        ) : (
          <p className="muted">Provider information is unavailable.</p>
        )}
        <p className="muted small">The provider and its API credentials are configured on the server only.</p>
      </section>

      {authRequired && user.role === "admin" && (
        <section className="card">
          <h2>Team members</h2>
          <p className="muted">There is no public sign-up. Administrators add team members here.</p>
          <TeamManagement currentUserId={user.id} />
        </section>
      )}
    </>
  );
}
