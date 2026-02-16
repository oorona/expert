"use client";

import { useEffect, useState } from "react";
import { listExperts, createExpert } from "@/lib/api";
import { ExpertEditor } from "@/components/admin/ExpertEditor";
import type { ExpertItem } from "@/types";

export default function ExpertsPage() {
  const [experts, setExperts] = useState<ExpertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [progressMsg, setProgressMsg] = useState("");
  const [progressStep, setProgressStep] = useState(0);
  const [progressTotal, setProgressTotal] = useState(0);

  useEffect(() => {
    loadExperts();
  }, []);

  async function loadExperts() {
    try {
      const data = await listExperts();
      setExperts(data);
    } catch {
      // Backend may not be ready
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!newName) return;
    setCreating(true);
    setProgressMsg("");
    setProgressStep(0);
    setProgressTotal(0);
    try {
      await createExpert(
        { name: newName, description: newDesc },
        (step, total, message) => {
          setProgressStep(step);
          setProgressTotal(total);
          setProgressMsg(message);
        }
      );
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
      await loadExperts();
    } finally {
      setCreating(false);
      setProgressMsg("");
    }
  }

  if (loading) {
    return <p className="text-center text-gray-500 dark:text-gray-400 py-8">Loading...</p>;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Expert Manager</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-3 py-1.5 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-700"
        >
          + New Expert
        </button>
      </div>

      {showCreate && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 space-y-3">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Expert name (e.g. Oracle Database, Linux System Admin, Kubernetes)"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-gray-100"
          />
          <textarea
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            placeholder="Describe what this expert specializes in. Be specific — this drives the AI prompt generation.&#10;&#10;Example: This expert specializes in Oracle Database administration including ORA errors, performance tuning, RAC clusters, Data Guard, RMAN backup/recovery, tablespace management, and SQL optimization. It should understand Oracle-specific terminology and provide resolution steps using Oracle tools and utilities."
            className="w-full h-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-gray-100"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400">
            The description is used by the AI to generate tailored system and user prompts specific to this expert&apos;s domain.
            A Gemini File Search store will also be created. You can edit the generated prompts afterward under <strong>Prompts</strong>.
          </p>
          <button
            onClick={handleCreate}
            disabled={creating || !newName}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:bg-gray-400"
          >
            {creating ? "Creating…" : "Create Expert"}
          </button>
          {creating && progressMsg && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span>Step {progressStep} of {progressTotal}: {progressMsg}</span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                <div
                  className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${(progressStep / progressTotal) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      <div className="space-y-4">
        {experts.length === 0 ? (
          <p className="text-center text-gray-500 dark:text-gray-400 py-8">
            No experts created yet. Create an expert to enable file search with expert-specific documents.
          </p>
        ) : (
          experts.map((e) => (
            <ExpertEditor key={e.id} expert={e} onUpdate={loadExperts} />
          ))
        )}
      </div>
    </div>
  );
}
