"use client";

import type { Source } from "@/types";

interface Props {
  sources: Source[];
}

export function SourcesList({ sources }: Props) {
  if (sources.length === 0) return null;

  // Check if any sources have detailed citation information
  const hasDetailedCitations = sources.some((s) => s.citations && s.citations.length > 0);

  if (!hasDetailedCitations) {
    // Simple display for sources without citation details
    return (
      <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
        <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-2">
          Sources
        </h4>
        <ul className="space-y-1">
          {sources.map((s, i) => (
            <li key={i}>
              <a
                href={s.uri}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:underline"
              >
                {s.title}
              </a>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  // Detailed display with citation information (similar to file search results)
  return (
    <div className="mt-4 space-y-3">
      <h3 className="font-semibold dark:text-gray-200">
        🌐 Web Sources ({sources.length})
      </h3>
      {sources.map((source, i) => (
        <div
          key={i}
          className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
        >
          <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 dark:bg-gray-800/50">
            <span className="text-sm">🔗</span>
            <a
              href={source.uri}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline flex-1"
            >
              {source.title}
            </a>
          </div>

          {source.citations && source.citations.length > 0 && (
            <div className="px-4 py-3 space-y-2 bg-white dark:bg-gray-900/50">
              <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">
                Citations ({source.citations.length})
              </div>
              {source.citations.map((citation, j) => (
                <div
                  key={j}
                  className="pl-3 border-l-2 border-blue-200 dark:border-blue-800"
                >
                  <p className="text-sm text-gray-700 dark:text-gray-300 italic">
                    "{citation.cited_text}"
                  </p>
                  {citation.confidence > 0 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Confidence: {(citation.confidence * 100).toFixed(0)}%
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
