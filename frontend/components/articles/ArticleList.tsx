"use client";

import { useState } from "react";
import Link from "next/link";
import { formatDate, truncate } from "@/lib/utils";
import { InlineConfirm } from "@/components/ui/InlineConfirm";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import type { IncidentCategory } from "@/types";

interface SessionItem {
  type: "session";
  id: number;
  session_id: string;
  error_text: string | null;
  title?: string | null;
  error_summary?: string | null;
  status?: string;
  expert_id?: number | null;
  categories?: IncidentCategory[];
  created_at: string;
}

interface SearchItem {
  type: "search";
  id: number;
  session_id?: string;
  error_text: string | null;
  title?: string | null;
  error_summary?: string | null;
  markdown_content: string;
  score?: number;
}

type ListItem = SessionItem | SearchItem;

interface Expert {
  id: number;
  name: string;
}

interface Props {
  items: ListItem[];
  onDelete?: (id: number) => void;
  experts?: Expert[];
}

export function ArticleList({ items, onDelete, experts = [] }: Props) {
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  const getStatusColor = (status?: string) => {
    switch (status) {
      case "created":
        return "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400";
      case "pending_review":
        return "bg-yellow-50 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400";
      case "in_review":
        return "bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400";
      case "analyzed":
        return "bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400";
      case "closed":
        return "bg-gray-50 dark:bg-gray-900/30 text-gray-600 dark:text-gray-400";
      default:
        return "bg-gray-50 dark:bg-gray-900/30 text-gray-600 dark:text-gray-400";
    }
  };

  const getStatusLabel = (status?: string) => {
    if (!status) return null;
    return status.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const getExpertName = (expertId?: number | null) => {
    if (!expertId) return null;
    const expert = experts.find((e) => e.id === expertId);
    return expert?.name || `Expert #${expertId}`;
  };

  if (items.length === 0) {
    return (
      <p className="text-gray-500 dark:text-gray-400 text-sm text-center py-8">
        No diagnoses found
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((item) => {
        const sessionKey =
          item.type === "session"
            ? item.session_id
            : item.session_id || String(item.id);
        const href = `/articles/${sessionKey}`;

        return (
          <Link
            key={`${item.type}-${item.id}`}
            href={href}
            className="block bg-white dark:bg-gray-800 rounded-lg shadow hover:shadow-md transition-shadow border border-gray-100 dark:border-gray-700"
          >
            <div className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <p className="font-medium text-gray-800 dark:text-gray-200 text-sm">
                      {item.error_summary || item.title || item.error_text || "Image diagnosis"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {item.type === "session" && item.status && (
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getStatusColor(item.status)}`}>
                        {getStatusLabel(item.status)}
                      </span>
                    )}
                    {item.type === "session" && item.expert_id && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 font-medium">
                        {getExpertName(item.expert_id)}
                      </span>
                    )}
                    {item.type === "session" && item.categories && item.categories.length > 0 && (
                      <>
                        {item.categories.map((cat, idx) => (
                          <CategoryBadge
                            key={idx}
                            category={cat.category}
                            confidence={cat.confidence}
                            isPrimary={cat.primary}
                            size="sm"
                            showConfidence={false}
                          />
                        ))}
                      </>
                    )}
                    {item.type === "session" && (
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        {formatDate(item.created_at)}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {item.type === "search" && item.score !== undefined && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium">
                      {(item.score * 100).toFixed(0)}%
                    </span>
                  )}
                  {onDelete && confirmDeleteId !== item.id && (
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setConfirmDeleteId(item.id);
                      }}
                      className="p-1 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                      title="Delete"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  )}
                  {onDelete && confirmDeleteId === item.id && (
                    <div onClick={(e) => { e.preventDefault(); e.stopPropagation(); }} className="flex items-center gap-1">
                      <button
                        onClick={() => { onDelete(item.id); setConfirmDeleteId(null); }}
                        className="px-2 py-0.5 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 transition-colors"
                      >
                        Delete
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(null)}
                        className="px-2 py-0.5 text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
