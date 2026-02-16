"use client";

import { useEffect, useState } from "react";
import { listPrompts, updatePrompt, createPrompt, listExperts } from "@/lib/api";
import { PromptEditor } from "@/components/admin/PromptEditor";
import type { PromptItem, ExpertItem } from "@/types";

export default function PromptsPage() {
  const [prompts, setPrompts] = useState<PromptItem[]>([]);
  const [experts, setExperts] = useState<ExpertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("system");
  const [newCategory, setNewCategory] = useState("grounded");
  const [newExpertId, setNewExpertId] = useState<number | null>(null);
  const [newContent, setNewContent] = useState("");

  // Filters
  const [filterExpert, setFilterExpert] = useState<number | null | undefined>(undefined);
  const [filterCategory, setFilterCategory] = useState<string>("");

  useEffect(() => {
    listExperts().then(setExperts).catch(() => {});
    loadPrompts();
  }, []);

  useEffect(() => {
    loadPrompts();
  }, [filterExpert, filterCategory]);

  async function loadPrompts() {
    try {
      const data = await listPrompts(
        filterExpert === undefined ? undefined : filterExpert,
        filterCategory || undefined
      );
      setPrompts(data);
    } catch {
      // Backend may not be ready
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(id: number, content: string) {
    await updatePrompt(id, { content });
    await loadPrompts();
  }

  async function handleToggle(id: number, active: boolean) {
    await updatePrompt(id, { is_active: active });
    await loadPrompts();
  }

  async function handleCreate() {
    if (!newName || !newContent) return;
    await createPrompt({
      name: newName,
      prompt_type: newType,
      prompt_category: newCategory,
      content: newContent,
      expert_id: newExpertId,
    });
    setShowCreate(false);
    setNewName("");
    setNewContent("");
    await loadPrompts();
  }

  if (loading) {
    return <p className="text-center text-gray-500 dark:text-gray-400 py-8">Loading...</p>;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold dark:text-gray-100">Prompt Manager</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-3 py-1.5 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-700"
        >
          + New Prompt
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 items-center">
        <select
          value={filterExpert === undefined ? "__all__" : filterExpert === null ? "__global__" : String(filterExpert)}
          onChange={(e) => {
            const v = e.target.value;
            if (v === "__all__") setFilterExpert(undefined);
            else if (v === "__global__") setFilterExpert(null);
            else setFilterExpert(Number(v));
          }}
          className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-gray-100"
        >
          <option value="__all__">All Experts</option>
          <option value="__global__">Global (no expert)</option>
          {experts.map((e) => (
            <option key={e.id} value={e.id}>{e.name}</option>
          ))}
        </select>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-gray-100"
        >
          <option value="">All Categories</option>
          <option value="grounded">Grounded</option>
          <option value="file_search">File Search</option>
        </select>
      </div>

      {showCreate && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 space-y-3">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Prompt name"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-gray-100"
          />
          <div className="flex gap-3">
            <select
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-gray-100"
            >
              <option value="system">System</option>
              <option value="user">User</option>
            </select>
            <select
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-gray-100"
            >
              <option value="grounded">Grounded</option>
              <option value="file_search">File Search</option>
            </select>
            <select
              value={newExpertId ?? ""}
              onChange={(e) => setNewExpertId(e.target.value ? Number(e.target.value) : null)}
              className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-gray-100"
            >
              <option value="" disabled>Select an expert…</option>
              {experts.map((e) => (
                <option key={e.id} value={e.id}>{e.name}</option>
              ))}
            </select>
          </div>
          <textarea
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder="Prompt content..."
            className="w-full h-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm font-mono bg-white dark:bg-gray-700 dark:text-gray-100"
          />
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700"
          >
            Create
          </button>
        </div>
      )}

      <div className="space-y-4">
        {prompts.length === 0 ? (
          <p className="text-center text-gray-500 dark:text-gray-400 py-8">No prompts match the current filters.</p>
        ) : (
          prompts.map((p) => (
            <PromptEditor
              key={p.id}
              prompt={p}
              onSave={handleSave}
              onToggle={handleToggle}
            />
          ))
        )}
      </div>
    </div>
  );
}
