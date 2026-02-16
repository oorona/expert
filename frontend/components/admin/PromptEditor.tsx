"use client";

import { useState, useEffect } from "react";
import type { PromptItem } from "@/types";
import { useToast } from "@/components/ui/Toast";

interface Props {
  prompt: PromptItem;
  onSave: (id: number, content: string) => Promise<void>;
  onToggle: (id: number, active: boolean) => Promise<void>;
}

export function PromptEditor({ prompt, onSave, onToggle }: Props) {
  const [content, setContent] = useState(prompt.content);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const toast = useToast();

  useEffect(() => {
    setContent(prompt.content);
    setDirty(false);
  }, [prompt.id, prompt.content]);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(prompt.id, content);
      setDirty(false);
      toast.success("Prompt saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(active: boolean) {
    try {
      await onToggle(prompt.id, active);
      toast.info(active ? "Prompt activated" : "Prompt deactivated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Toggle failed");
    }
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div>
            <h3 className="font-semibold text-gray-800 dark:text-gray-200">{prompt.name}</h3>
            <div className="flex gap-1 mt-1">
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  prompt.prompt_type === "system"
                    ? "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300"
                    : "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
                }`}
              >
                {prompt.prompt_type}
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  prompt.prompt_category === "file_search"
                    ? "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                    : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                }`}
              >
                {prompt.prompt_category}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={prompt.is_active}
              onChange={(e) => handleToggle(e.target.checked)}
              className="rounded"
            />
            Active
          </label>
          <button
            onClick={handleSave}
            disabled={!dirty || saving}
            className="px-3 py-1 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
      <textarea
        value={content}
        onChange={(e) => {
          setContent(e.target.value);
          setDirty(true);
        }}
        className="w-full h-48 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm font-mono resize-y focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100"
      />
    </div>
  );
}
