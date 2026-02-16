"use client";

import type { RelatedArticle } from "@/types";
import { truncate, formatDate } from "@/lib/utils";

interface Props {
  articles: RelatedArticle[];
  currentSessionId?: string;
}

const RELATION_LABELS: Record<string, string> = {
  followup: "Follow-up",
  parent: "Parent",
  related: "Related",
};

export function RelatedArticles({ articles, currentSessionId }: Props) {
  if (articles.length === 0) return null;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
        <span>🔗</span>
        <span>Related Articles</span>
        <span className="text-xs font-normal text-gray-400 dark:text-gray-500">
          ({articles.length})
        </span>
      </h3>
      <ul className="space-y-2">
        {articles.map((a) => (
          <li key={a.session_id}>
            <a
              href={currentSessionId ? `/?session=${a.session_id}` : `/articles/${a.session_id}`}
              className="block px-3 py-2.5 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 border border-gray-100 dark:border-gray-700 transition-colors group"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="inline-block px-1.5 py-0.5 text-[10px] font-medium rounded bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
                  {RELATION_LABELS[a.relation_type] || a.relation_type}
                </span>
              </div>
              <p className="text-sm font-medium text-gray-800 dark:text-gray-200 group-hover:text-blue-600 dark:group-hover:text-blue-400 break-words whitespace-normal">
                {a.error_summary || a.title || a.error_text || "Diagnosis"}
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                {formatDate(a.created_at)}
              </p>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
