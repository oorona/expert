"use client";

import { useState } from "react";
import type { SimilarIncident } from "@/types";

interface Props {
  incidents: SimilarIncident[];
  onSelect: (sessionId: string) => void;
}

export function SimilarIncidentBanner({ incidents, onSelect }: Props) {
  const [open, setOpen] = useState(false);

  if (incidents.length === 0) return null;

  return (
    <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-amber-100/50 dark:hover:bg-amber-900/30 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-amber-800 dark:text-amber-200">
          <span>⚡</span>
          <span>{incidents.length} similar incident{incidents.length !== 1 ? "s" : ""} found</span>
        </div>
        <span className="text-amber-500 dark:text-amber-400 text-xs">{open ? "▼" : "▶"}</span>
      </button>
      {open && (
        <ul className="px-4 pb-3 space-y-2">
          {incidents.map((inc) => (
            <li key={inc.id} className="flex items-center justify-between">
              <span className="text-sm text-amber-700 dark:text-amber-300 truncate max-w-md">
                {inc.title || inc.error_text || "Previous diagnosis"}
              </span>
              <div className="flex items-center gap-3">
                <span className="text-xs text-amber-600 dark:text-amber-400">
                  {(inc.similarity * 100).toFixed(0)}% match
                </span>
                <button
                  onClick={() => onSelect(inc.session_id)}
                  className="text-xs font-medium text-blue-600 hover:text-blue-800"
                >
                  View
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
