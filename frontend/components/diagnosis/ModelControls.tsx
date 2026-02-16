"use client";

import type { ModelInfo } from "@/types";

interface Props {
  model: string;
  setModel: (v: string) => void;
  temperature: number;
  setTemperature: (v: number) => void;
  thinkingLevel: string;
  setThinkingLevel: (v: string) => void;
  useGrounding: boolean;
  setUseGrounding: (v: boolean) => void;
  useFileSearch: boolean;
  setUseFileSearch: (v: boolean) => void;
  showThoughts: boolean;
  setShowThoughts: (v: boolean) => void;
  expertId: number | null;
}

const MODELS: ModelInfo[] = [
  { id: "gemini-2.5-flash-lite-preview-06-17", label: "Gemini 2.5 Flash-Lite", inputCost: 0.10, outputCost: 0.40, supportsFileSearch: true, supportsGrounding: true },
  { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash", inputCost: 0.15, outputCost: 3.50, supportsFileSearch: false, supportsGrounding: true },
  { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro", inputCost: 1.25, outputCost: 10.00, supportsFileSearch: true, supportsGrounding: true },
  { id: "gemini-3-flash-preview", label: "Gemini 3 Flash", inputCost: 0.50, outputCost: 3.00, supportsFileSearch: true, supportsGrounding: true },
  { id: "gemini-3-pro-preview", label: "Gemini 3 Pro", inputCost: 2.00, outputCost: 12.00, supportsFileSearch: true, supportsGrounding: true },
];

const THINKING_LEVELS = ["off", "low", "medium", "high"];

export function ModelControls({
  model,
  setModel,
  temperature,
  setTemperature,
  thinkingLevel,
  setThinkingLevel,
  useGrounding,
  setUseGrounding,
  useFileSearch,
  setUseFileSearch,
  showThoughts,
  setShowThoughts,
  expertId,
}: Props) {
  const currentModel = MODELS.find((m) => m.id === model);

  function handleGroundingChange(checked: boolean) {
    if (checked) setUseFileSearch(false);
    setUseGrounding(checked);
  }

  function handleFileSearchChange(checked: boolean) {
    if (checked) setUseGrounding(false);
    setUseFileSearch(checked);
  }

  function handleModelChange(id: string) {
    setModel(id);
    const m = MODELS.find((x) => x.id === id);
    if (m && !m.supportsFileSearch && useFileSearch) {
      setUseFileSearch(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-4 items-end">
        {/* Model selector */}
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Model
          </label>
          <select
            value={model}
            onChange={(e) => handleModelChange(e.target.value)}
            className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-gray-100"
          >
            {MODELS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label} (${m.inputCost}/${m.outputCost})
              </option>
            ))}
          </select>
        </div>

        {/* Thinking level */}
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Thinking
          </label>
          <select
            value={thinkingLevel}
            onChange={(e) => setThinkingLevel(e.target.value)}
            className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-gray-100"
          >
            {THINKING_LEVELS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>

        {/* Temperature */}
        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
            Temperature: {temperature.toFixed(1)}
          </label>
          <input
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={temperature}
            onChange={(e) => setTemperature(parseFloat(e.target.value))}
            className="w-32"
          />
        </div>

        {/* Grounding */}
        <label className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
          <input
            type="checkbox"
            checked={useGrounding}
            onChange={(e) => handleGroundingChange(e.target.checked)}
            className="rounded"
          />
          Grounding
        </label>

        {/* Show Thoughts */}
        <label className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
          <input
            type="checkbox"
            checked={showThoughts}
            onChange={(e) => setShowThoughts(e.target.checked)}
            className="rounded"
          />
          Show Thoughts
        </label>

        {/* File Search */}
        <label
          className={`flex items-center gap-1.5 text-sm ${
            currentModel && !currentModel.supportsFileSearch
              ? "text-gray-400 dark:text-gray-600"
              : "text-gray-700 dark:text-gray-300"
          }`}
          title={
            currentModel && !currentModel.supportsFileSearch
              ? `${currentModel.label} does not support File Search`
              : !expertId
              ? "Select an expert to enable File Search"
              : undefined
          }
        >
          <input
            type="checkbox"
            checked={useFileSearch}
            onChange={(e) => handleFileSearchChange(e.target.checked)}
            disabled={
              (currentModel && !currentModel.supportsFileSearch) || !expertId
            }
            className="rounded"
          />
          File Search
        </label>
      </div>

      {/* Cost hint */}
      {currentModel && (
        <p className="text-xs text-gray-400 dark:text-gray-500">
          Cost per 1M tokens — Input: ${currentModel.inputCost.toFixed(2)} · Output: ${currentModel.outputCost.toFixed(2)}
          {!currentModel.supportsFileSearch && " · No File Search"}
        </p>
      )}
    </div>
  );
}
