"use client";

import { useCallback, useEffect, useState } from "react";
import { listApiKeys, createApiKey, updateApiKey, deleteApiKey } from "@/lib/api";
import { InlineConfirm } from "@/components/ui/InlineConfirm";
import type { ApiKeyItem } from "@/types";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyDesc, setNewKeyDesc] = useState("");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const cancelConfirmDelete = useCallback(() => setConfirmDeleteId(null), []);

  useEffect(() => {
    loadKeys();
  }, []);

  async function loadKeys() {
    try {
      setLoading(true);
      const data = await listApiKeys();
      setKeys(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!newKeyName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const result = await createApiKey({
        name: newKeyName.trim(),
        description: newKeyDesc.trim(),
      });
      setRevealedKey(result.raw_key || null);
      setNewKeyName("");
      setNewKeyDesc("");
      await loadKeys();
    } catch (err) {
      setError(String(err));
    } finally {
      setCreating(false);
    }
  }

  async function handleToggle(key: ApiKeyItem) {
    try {
      await updateApiKey(key.id, { is_active: !key.is_active });
      await loadKeys();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleDelete(key: ApiKeyItem) {
    try {
      await deleteApiKey(key.id);
      setConfirmDeleteId(null);
      await loadKeys();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Client API Keys
        </h1>
      </div>

      <p className="text-sm text-gray-600 dark:text-gray-400">
        Create and manage API keys for external systems to submit errors via the ingestion API.
        Keys are shown only once at creation — store them securely.
      </p>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-500 hover:text-red-700">✕</button>
        </div>
      )}

      {/* Revealed Key Banner */}
      {revealedKey && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-5">
          <div className="flex items-start gap-3">
            <span className="text-2xl">🔑</span>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-green-900 dark:text-green-200">
                API Key Created — Copy it now!
              </h3>
              <p className="mt-1 text-xs text-green-700 dark:text-green-400">
                This key will not be shown again. Store it securely.
              </p>
              <div className="mt-3 flex items-center gap-2">
                <code className="flex-1 text-sm font-mono bg-green-100 dark:bg-green-900/40 rounded px-3 py-2 text-green-800 dark:text-green-200 break-all select-all">
                  {revealedKey}
                </code>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(revealedKey);
                  }}
                  className="shrink-0 px-3 py-2 text-sm font-medium text-green-700 dark:text-green-300 bg-white dark:bg-gray-800 border border-green-300 dark:border-green-700 rounded hover:bg-green-50 dark:hover:bg-green-900/30 transition-colors"
                >
                  Copy
                </button>
              </div>
              <button
                onClick={() => setRevealedKey(null)}
                className="mt-3 text-xs text-green-600 dark:text-green-400 hover:underline"
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create New Key */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">
          Create New Key
        </h2>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Name *
            </label>
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="e.g. Production Monitoring"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Description
            </label>
            <input
              type="text"
              value={newKeyDesc}
              onChange={(e) => setNewKeyDesc(e.target.value)}
              placeholder="Optional description for this key"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-800 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={creating || !newKeyName.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {creating ? "Creating..." : "Generate Key"}
          </button>
        </div>
      </div>

      {/* Keys List */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            Existing Keys
          </h2>
        </div>
        {loading ? (
          <div className="px-6 py-8 text-center text-gray-400">Loading...</div>
        ) : keys.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-400">
            No API keys yet. Create one above.
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-900/50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Preview
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Last Used
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {keys.map((k) => (
                <tr key={k.id}>
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {k.name}
                    </div>
                    {k.description && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        {k.description}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm font-mono text-gray-500 dark:text-gray-400">
                    {k.key_preview}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                        k.is_active
                          ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
                          : "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300"
                      }`}
                    >
                      {k.is_active ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                    {k.last_used_at ? formatDate(k.last_used_at) : "Never"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                    {formatDate(k.created_at)}
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    {confirmDeleteId === k.id ? (
                      <InlineConfirm
                        message={`Delete "${k.name}"?`}
                        confirmLabel="Delete"
                        variant="danger"
                        timeout={6}
                        onConfirm={() => handleDelete(k)}
                        onCancel={cancelConfirmDelete}
                      />
                    ) : (
                      <>
                        <button
                          onClick={() => handleToggle(k)}
                          className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                            k.is_active
                              ? "text-orange-700 dark:text-orange-300 bg-orange-50 dark:bg-orange-900/20 hover:bg-orange-100 dark:hover:bg-orange-900/30"
                              : "text-green-700 dark:text-green-300 bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/30"
                          }`}
                        >
                          {k.is_active ? "Disable" : "Enable"}
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(k.id)}
                          className="px-3 py-1 text-xs font-medium text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20 rounded hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
