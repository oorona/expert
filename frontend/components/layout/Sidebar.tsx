"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { listSessions, listExperts } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { SessionListItem, ExpertItem } from "@/types";

const STATUS_COLORS: Record<string, string> = {
  created: "bg-yellow-500",
  pending_review: "bg-orange-500",
  in_review: "bg-blue-500",
  analyzed: "bg-purple-500",
  closed: "bg-gray-500",
  resolved: "bg-green-500",
};

const STATUS_LABELS: Record<string, string> = {
  created: "New",
  pending_review: "Pending",
  in_review: "Reviewing",
  analyzed: "Analyzed",
  closed: "Closed",
  resolved: "Resolved",
};

const MAX_SIDEBAR_ITEMS = 50;

export function Sidebar() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [experts, setExperts] = useState<ExpertItem[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [timeFilter, setTimeFilter] = useState<"7d" | "30d" | "all">("30d");
  const pathname = usePathname();

  // Only show on the dashboard (root path, with or without query params)
  const isDashboard = pathname === "/";

  const getExpertName = (expertId?: number | null) => {
    if (!expertId) return null;
    const expert = experts.find((e) => e.id === expertId);
    return expert?.name || `Expert #${expertId}`;
  };

  useEffect(() => {
    if (!isDashboard) return;
    loadSessions();
    loadExperts();
    const handler = () => {
      loadSessions();
    };
    window.addEventListener("sessions-changed", handler);
    return () => {
      window.removeEventListener("sessions-changed", handler);
    };
  }, [isDashboard, timeFilter]);

  async function loadSessions() {
    try {
      const data = await listSessions();
      // Filter by time range
      const now = new Date();
      const filtered = data.filter((s) => {
        if (timeFilter === "all") return true;
        const created = new Date(s.created_at);
        const daysAgo = (now.getTime() - created.getTime()) / (1000 * 60 * 60 * 24);
        if (timeFilter === "7d") return daysAgo <= 7;
        if (timeFilter === "30d") return daysAgo <= 30;
        return true;
      });
      // Limit to most recent items
      setSessions(filtered.slice(0, MAX_SIDEBAR_ITEMS));
    } catch {
      // Backend may not be ready yet
    }
  }

  async function loadExperts() {
    try {
      const data = await listExperts();
      setExperts(data.filter((e) => e.is_active));
    } catch {
      // Backend may not be ready yet
    }
  }

  if (!isDashboard) return null;

  if (collapsed) {
    return (
      <div className="w-12 bg-gray-900 dark:bg-gray-950 flex flex-col items-center pt-4">
        <button
          onClick={() => setCollapsed(false)}
          className="text-gray-400 hover:text-white text-lg"
          title="Expand sidebar"
        >
          &raquo;
        </button>
      </div>
    );
  }

  return (
    <div className="w-72 bg-gray-900 dark:bg-gray-950 text-gray-100 flex flex-col">
      <div className="px-4 py-3 border-b border-gray-700">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider">
            History
          </h2>
          <button
            onClick={() => setCollapsed(true)}
            className="text-gray-400 hover:text-white text-sm"
          >
            &laquo;
          </button>
        </div>
        <select
          value={timeFilter}
          onChange={(e) => setTimeFilter(e.target.value as "7d" | "30d" | "all")}
          className="w-full px-2 py-1 text-xs bg-gray-800 border border-gray-700 rounded text-gray-300 focus:outline-none focus:ring-1 focus:ring-gray-600"
        >
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="all">All time (max {MAX_SIDEBAR_ITEMS})</option>
        </select>
      </div>

      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="px-4 py-8 text-gray-500 text-sm text-center">
            <p>No sessions in this time range</p>
            <a href="/articles" className="text-xs text-blue-400 hover:text-blue-300 mt-2 inline-block">
              View all in Knowledge Base &rarr;
            </a>
          </div>
        ) : (
          <ul>
            {sessions.map((s) => (
              <li key={s.session_id}>
                <a
                  href={`/?session=${s.session_id}`}
                  className="block px-4 py-3 hover:bg-gray-800 border-b border-gray-800"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium break-words whitespace-normal flex-1">
                      {s.title || s.error_summary || s.error_text || "Image diagnosis"}
                    </p>
                    <div className="flex flex-col gap-1 items-end shrink-0">
                      {s.status && s.status !== "resolved" && (
                        <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${STATUS_COLORS[s.status] || "bg-gray-600"} text-white`}>
                          {STATUS_LABELS[s.status] || s.status}
                        </span>
                      )}
                      {s.expert_id && (
                        <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-indigo-600 text-white">
                          {getExpertName(s.expert_id)}
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    {formatDate(s.created_at)}
                  </p>
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="px-4 py-3 border-t border-gray-700 space-y-2">
        <button
          onClick={() => loadSessions()}
          className="w-full text-xs text-gray-400 hover:text-white"
        >
          Refresh
        </button>
        {sessions.length >= MAX_SIDEBAR_ITEMS && (
          <a
            href="/articles"
            className="block text-center text-xs text-blue-400 hover:text-blue-300"
          >
            View all in Knowledge Base &rarr;
          </a>
        )}
      </div>
    </div>
  );
}
