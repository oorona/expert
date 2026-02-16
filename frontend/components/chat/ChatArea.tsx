"use client";

import { useState } from "react";
import type { TokenUsage } from "@/types";

interface Props {
  incidentId: number;
  sessionId: string;
  model: string;
  temperature: number;
  onTokenUsage?: (usage: TokenUsage) => void;
  onCreateArticle?: (question: string) => void;
}

export function ChatArea({
  sessionId,
  onCreateArticle,
}: Props) {
  const [input, setInput] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || !onCreateArticle || submitted) return;
    setSubmitted(true);
    onCreateArticle(input.trim());
  }

  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-1">Follow-up Question</h3>
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
        Ask a related question — it will be diagnosed as a new linked article.
      </p>

      <form onSubmit={handleSend} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a follow-up question..."
          className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100"
          disabled={submitted}
        />
        <button
          type="submit"
          disabled={submitted || !input.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
        >
          {submitted ? "Creating..." : "Send"}
        </button>
      </form>
      {submitted && (
        <p className="mt-2 text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1">
          <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Creating linked article — you will be redirected when ready…
        </p>
      )}
    </div>
  );
}
