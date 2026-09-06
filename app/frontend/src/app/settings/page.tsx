"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import {
  agents,
  applyUpdate,
  deleteProviderKey,
  IS_DEMO,
  providers,
  putProviderKey,
  putUpdateConfig,
  rollbackUpdate,
  updateConfig,
  updateStatus,
  type AgentStatus,
  type ApplyResult,
  type ProviderInfo,
  type UpdateConfig,
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

interface ActionState {
  pending: boolean;
  result: ApplyResult | null;
  error: string | null;
}

const IDLE_ACTION: ActionState = { pending: false, result: null, error: null };

function UpdatesSection() {
  const [info, setInfo] = useState<UpdateStatus | null>(null);
  const [config, setConfig] = useState<UpdateConfig | null>(null);
  const [configUnsupported, setConfigUnsupported] = useState(false);
  const [channel, setChannel] = useState<"dev" | "release">("release");
  const [autoApply, setAutoApply] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [applyState, setApplyState] = useState<ActionState>(IDLE_ACTION);
  const [rollbackState, setRollbackState] = useState<ActionState>(IDLE_ACTION);

  useEffect(() => {
    let cancelled = false;
    updateStatus()
      .then((data) => {
        if (!cancelled) setInfo(data);
      })
      .catch(() => {
        /* no update info available; the section renders nothing until it has some */
      });
    if (!IS_DEMO) {
      updateConfig()
        .then((data) => {
          if (cancelled) return;
          setConfig(data);
          setChannel(data.channel);
          setAutoApply(data.auto_apply);
        })
        .catch(() => {
          if (!cancelled) setConfigUnsupported(true);
        });
    }
    return () => {
      cancelled = true;
    };
  }, []);

  const dirty = config !== null && (channel !== config.channel || autoApply !== config.auto_apply);

  async function handleSaveConfig() {
    if (config === null) return;
    setSavingConfig(true);
    try {
      const saved = await putUpdateConfig({ ...config, channel, auto_apply: autoApply });
      setConfig(saved);
      setChannel(saved.channel);
      setAutoApply(saved.auto_apply);
    } catch {
      /* the selector keeps the attempted values so the operator can retry */
    } finally {
      setSavingConfig(false);
    }
  }

  async function handleApply() {
    setApplyState({ pending: true, result: null, error: null });
    try {
      const result = await applyUpdate(channel);
      setApplyState({ pending: false, result, error: null });
    } catch {
      setApplyState({ pending: false, result: null, error: "could not reach the engine" });
    }
  }

  async function handleRollback() {
    setRollbackState({ pending: true, result: null, error: null });
    try {
      const result = await rollbackUpdate();
      setRollbackState({ pending: false, result, error: null });
    } catch {
      setRollbackState({ pending: false, result: null, error: "could not reach the engine" });
    }
  }

  if (info === null) return null;

  return (
    <div>
      <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">Updates</h2>
      <div className="space-y-3 rounded-lg border border-[var(--color-border)] p-4 text-sm">
        <p className="text-[var(--color-text-dim)]">
          Running {info.current.version}.{" "}
          {info.update_available && info.latest ? `Latest release: ${info.latest.tag}.` : "Up to date."}
        </p>

        {IS_DEMO ? (
          <p className="text-xs text-[var(--color-text-dim)]">This is a recorded run: update controls are disabled.</p>
        ) : (
          <>
            {configUnsupported && (
              <p className="text-xs text-[var(--color-text-dim)]">engine does not report update config yet.</p>
            )}
            {!configUnsupported && config !== null && (
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2">
                  <span className="text-[var(--color-text-dim)]">Channel</span>
                  <select
                    value={channel}
                    onChange={(e) => setChannel(e.target.value as "dev" | "release")}
                    className="rounded-md border border-[var(--color-border)] bg-transparent px-2 py-1 text-sm"
                  >
                    <option value="release">release</option>
                    <option value="dev">dev</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 text-[var(--color-text-dim)]">
                  <input type="checkbox" checked={autoApply} onChange={(e) => setAutoApply(e.target.checked)} />
                  Auto-apply
                </label>
                <button
                  type="button"
                  disabled={savingConfig || !dirty}
                  onClick={handleSaveConfig}
                  className="rounded-md border border-[var(--color-border)] px-3 py-1 text-sm disabled:opacity-50"
                >
                  {savingConfig ? "Saving…" : "Save"}
                </button>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={applyState.pending}
                onClick={handleApply}
                className="rounded-md border border-[var(--color-border)] px-3 py-1 text-sm disabled:opacity-50"
              >
                {applyState.pending ? "Updating…" : "Update now"}
              </button>
              <button
                type="button"
                disabled={rollbackState.pending}
                onClick={handleRollback}
                className="rounded-md border border-[var(--color-border)] px-3 py-1 text-sm disabled:opacity-50"
              >
                {rollbackState.pending ? "Rolling back…" : "Roll back"}
              </button>
            </div>
            {applyState.result && (
              <p className="text-xs text-[var(--color-text-dim)]">{applyState.result.reason}</p>
            )}
            {applyState.error && <p className="text-xs text-red-500">{applyState.error}</p>}
            {rollbackState.result && (
              <p className="text-xs text-[var(--color-text-dim)]">{rollbackState.result.reason}</p>
            )}
            {rollbackState.error && <p className="text-xs text-red-500">{rollbackState.error}</p>}
          </>
        )}
      </div>
    </div>
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

        <UpdatesSection />
      </div>
    </div>
  );
}
