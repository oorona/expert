"use client";

import { useState } from "react";

interface Props {
  onSearch: (query: string, searchType: "text" | "semantic" | "hybrid") => void;
  onClear?: () => void;
}

export function ArticleSearch({ onSearch, onClear }: Props) {
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState<"text" | "semantic" | "hybrid">(
    "hybrid"
  );

  const searchOptions: { value: "text" | "semantic" | "hybrid"; label: string; tooltip: string }[] = [
    { value: "text", label: "Keyword", tooltip: "BM25 full-text search — matches exact words and phrases across error text, content, and notes" },
    { value: "semantic", label: "Semantic", tooltip: "AI-powered similarity search — finds conceptually related results even with different wording" },
    { value: "hybrid", label: "Hybrid", tooltip: "Combines keyword + semantic search for the best of both — recommended for most queries" },
  ];

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query, searchType);
    }
  }

  function handleClear() {
    setQuery("");
    onClear?.();
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <div className="relative flex-1">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search past diagnoses..."
          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100"
        />
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm"
          >
            ✕
          </button>
        )}
      </div>
      <div className="flex rounded-lg border border-gray-300 dark:border-gray-600 overflow-hidden">
        {searchOptions.map((opt) => (
          <button
            key={opt.value}
            type="button"
            title={opt.tooltip}
            onClick={() => setSearchType(opt.value)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              searchType === opt.value
                ? "bg-blue-600 text-white"
                : "bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <button
        type="submit"
        className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
      >
        Search
      </button>
    </form>
  );
}
