"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import {
  agents,
  deleteProviderKey,
  providers,
  putProviderKey,
  updateStatus,
  type AgentStatus,
  type ProviderInfo,
  type UpdateStatus,
} from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

interface RowState {
  pending: boolean;
  error: string | null;
}

function ProvidersSection() {
  const [rows, setRows] = useState<ProviderInfo[] | null>(null);
  const [unsupported, setUnsupported] = useState(false);
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [rowStates, setRowStates] = useState<Record<string, RowState>>({});

  useEffect(() => {
    let cancelled = false;
    providers()
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch(() => {
        if (!cancelled) setUnsupported(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function setRowState(id: string, state: RowState) {
    setRowStates((prev) => ({ ...prev, [id]: state }));
  }

  function setConfigured(id: string, configured: boolean) {
    setRows((prev) => prev?.map((p) => (p.id === id ? { ...p, configured } : p)) ?? prev);
  }

  async function handleSave(id: string) {
    const key = (keyInputs[id] ?? "").trim();
    if (!key) return;
    // Cleared immediately: the field never holds a key past the moment it is submitted, win or lose.
    setKeyInputs((prev) => ({ ...prev, [id]: "" }));
    setRowState(id, { pending: true, error: null });
    try {
      const result = await putProviderKey(id, key);
      if (result.ok) {
        setConfigured(id, true);
        setRowState(id, { pending: false, error: null });
      } else {
        setRowState(id, { pending: false, error: result.reason || "key rejected" });
      }
    } catch {
      setRowState(id, { pending: false, error: "could not reach the engine" });
    }
  }

  async function handleRemove(id: string) {
    setRowState(id, { pending: true, error: null });
    try {
      const result = await deleteProviderKey(id);
      setConfigured(id, false);
      setRowState(id, { pending: false, error: result.ok ? null : result.reason || "remove failed" });
    } catch {
      setRowState(id, { pending: false, error: "could not reach the engine" });
    }
  }

  if (unsupported) {
    return <p className="text-sm text-[var(--color-text-dim)]">engine does not report providers yet.</p>;
  }
  if (rows === null) {
    return <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>;
  }
  if (rows.length === 0) {
    return <p className="text-sm text-[var(--color-text-dim)]">No model providers configured.</p>;
  }

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
      <table className="w-full text-left text-sm">
        <thead className="bg-[var(--color-surface)] text-xs uppercase tracking-wide text-[var(--color-text-dim)]">
          <tr>
            <th className="px-4 py-3 font-medium">Provider</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">API key</th>
            <th className="px-4 py-3 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => {
            const state = rowStates[p.id];
            return (
              <tr key={p.id} className="border-t border-[var(--color-border)] align-top">
                <td className="px-4 py-3 font-medium text-[var(--color-text)]">{p.title}</td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center gap-1.5 ${
                      p.configured ? "text-[var(--color-accent)]" : "text-[var(--color-text-dim)]"
                    }`}
                  >
                    {p.configured ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                    {p.configured ? "configured" : "not configured"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="password"
                      autoComplete="off"
                      placeholder={p.configured ? "Replace key" : "Enter key"}
                      value={keyInputs[p.id] ?? ""}
                      onChange={(e) => setKeyInputs((prev) => ({ ...prev, [p.id]: e.target.value }))}
                      className="w-56 rounded-md border border-[var(--color-border)] bg-transparent px-2 py-1 text-sm"
                    />
                    <button
                      type="button"
                      disabled={state?.pending || !(keyInputs[p.id] ?? "").trim()}
                      onClick={() => handleSave(p.id)}
                      className="rounded-md border border-[var(--color-border)] px-3 py-1 text-sm disabled:opacity-50"
                    >
                      {state?.pending ? "Saving…" : "Save"}
                    </button>
                    <button
                      type="button"
                      disabled={state?.pending || !p.configured}
                      onClick={() => handleRemove(p.id)}
                      className="rounded-md border border-[var(--color-border)] px-3 py-1 text-sm disabled:opacity-50"
                    >
                      Remove
                    </button>
                  </div>
                  {state?.error && <p className="mt-1 text-xs text-red-500">{state.error}</p>}
                </td>
                <td />
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function UpdatesLine() {
  const [info, setInfo] = useState<UpdateStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    updateStatus()
      .then((data) => {
        if (!cancelled) setInfo(data);
      })
      .catch(() => {
        /* no update info available; the line is simply omitted */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (info === null) return null;

  return (
    <p className="text-sm text-[var(--color-text-dim)]">
      Running {info.current.version}.{" "}
      {info.update_available && info.latest ? (
        <>
          Update available ({info.latest.tag}) — run: <code className="text-[var(--color-text)]">{info.how}</code>
        </>
      ) : (
        "Up to date."
      )}
    </p>
  );
}

export default function SettingsPage() {
  const [rows, setRows] = useState<AgentStatus[] | null>(null);
  const [unsupported, setUnsupported] = useState(false);

  useEffect(() => {
    let cancelled = false;
    agents()
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch(() => {
        if (!cancelled) setUnsupported(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <PageHeader title="Settings" subtitle="Coding agents available to this engine." />
      <div className="space-y-8 p-8">
        <div>
          {unsupported && (
            <p className="text-sm text-[var(--color-text-dim)]">engine does not report agents yet.</p>
          )}
          {!unsupported && rows === null && <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>}
          {!unsupported && rows !== null && rows.length === 0 && (
            <p className="text-sm text-[var(--color-text-dim)]">No coding agents configured.</p>
          )}
          {!unsupported && rows !== null && rows.length > 0 && (
            <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--color-surface)] text-xs uppercase tracking-wide text-[var(--color-text-dim)]">
                  <tr>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((a) => (
                    <tr key={a.name} className="border-t border-[var(--color-border)]">
                      <td className="px-4 py-3 font-medium text-[var(--color-text)]">{a.name}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1.5 ${
                            a.available ? "text-[var(--color-accent)]" : "text-[var(--color-text-dim)]"
                          }`}
                        >
                          {a.available ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                          {a.available ? "ready" : "unavailable"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[var(--color-text-dim)]">{a.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div>
          <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">Model providers</h2>
          <ProvidersSection />
        </div>

        <UpdatesLine />
      </div>
    </div>
  );
}
