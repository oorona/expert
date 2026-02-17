"use client";

import { useEffect, useState } from "react";
import { listPrompts, updatePrompt, createPrompt, listExperts } from "@/lib/api";
import { PromptEditor } from "@/components/admin/PromptEditor";
import type { PromptItem, ExpertItem } from "@/types";

const TABS = [
  { label: "System · Grounded",    type: "system", category: "grounded"     },
  { label: "User · Grounded",      type: "user",   category: "grounded"     },
  { label: "System · File Search", type: "system", category: "file_search"  },
  { label: "User · File Search",   type: "user",   category: "file_search"  },
];

export default function PromptsPage() {
  const [prompts, setPrompts] = useState<PromptItem[]>([]);
  const [experts, setExperts] = useState<ExpertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("system");
  const [newCategory, setNewCategory] = useState("grounded");
  const [newExpertId, setNewExpertId] = useState<number | null>(null);
  const [newContent, setNewContent] = useState("");

  // null = global templates, number = specific expert
  const [filterExpert, setFilterExpert] = useState<number | null>(null);

  useEffect(() => {
    listExperts().then(setExperts).catch(() => {});
    loadPrompts();
  }, []);

  useEffect(() => {
    loadPrompts();
    setActiveTab(0);
  }, [filterExpert]);

  async function loadPrompts() {
    try {
      const data = await listPrompts(filterExpert, undefined);
      // Global: only show prompts with no expert_id
      const filtered = filterExpert === null
        ? data.filter((p) => p.expert_id === null)
        : data;
      setPrompts(filtered);
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

  const tabPrompts = prompts.filter(
        (p) =>
          p.prompt_type === TABS[activeTab].type &&
          p.prompt_category === TABS[activeTab].category
      );

  if (loading) {
    return <p className="text-center text-gray-500 dark:text-gray-400 py-8">Loading...</p>;
  }

  return (
    <div className="w-full space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold dark:text-gray-100">Prompt Manager</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-3 py-1.5 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-700"
        >
          + New Prompt
        </button>
      </div>

      {/* Expert filter */}
      <select
        value={filterExpert === null ? "__global__" : String(filterExpert)}
        onChange={(e) => {
          const v = e.target.value;
          if (v === "__global__") setFilterExpert(null);
          else setFilterExpert(Number(v));
        }}
        className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-gray-100"
      >
        <option value="__global__">Global (templates)</option>
        {experts.map((e) => (
          <option key={e.id} value={e.id}>{e.name}</option>
        ))}
      </select>

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
              <option value="">Global (no expert)</option>
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

      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
        {/* Tab bar */}
        <div className="flex border-b border-gray-200 dark:border-gray-700">
          {TABS.map((tab, idx) => (
            <button
              key={idx}
              onClick={() => setActiveTab(idx)}
              className={`flex-1 px-4 py-2.5 text-sm font-medium transition-colors ${
                activeTab === idx
                  ? "border-b-2 border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/20"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700/50"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="p-4 space-y-4">
          {tabPrompts.length === 0 ? (
            <p className="text-center text-gray-500 dark:text-gray-400 py-6">
              No prompt for this type.
            </p>
          ) : (
            tabPrompts.map((p) => (
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
    </div>
  );
}
