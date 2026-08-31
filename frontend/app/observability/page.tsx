"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getObservabilityEvent,
  getObservabilityStats,
  listObservabilityEvents,
  searchObservability,
} from "@/lib/api";
import type { LLMCall, LLMEvent, ObservabilityStats } from "@/types";

// ---- helpers ---------------------------------------------------------------

const EVENT_TYPE_COLORS: Record<string, string> = {
  diagnose: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  chat: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  classify: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  image: "bg-pink-100 text-pink-800 dark:bg-pink-900/40 dark:text-pink-300",
  prompt_gen: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  desc_gen: "bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300",
};

const STATUS_COLORS: Record<string, string> = {
  success: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
};

function Badge({ label, colorClass }: { label: string; colorClass: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
      {label}
    </span>
  );
}

function fmtDuration(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

function truncate(s: string | null | undefined, max = 200): string {
  if (!s) return "—";
  return s.length > max ? s.slice(0, max) + "…" : s;
}

// ---- Stats bar -------------------------------------------------------------

function StatsBar({ stats }: { stats: ObservabilityStats | null }) {
  if (!stats) return null;
  const cards = [
    { label: "Events", value: stats.total_events.toLocaleString() },
    { label: "Calls", value: stats.total_calls.toLocaleString() },
    { label: "Input tokens", value: fmtTokens(stats.total_input_tokens) },
    { label: "Output tokens", value: fmtTokens(stats.total_output_tokens) },
    { label: "Cache tokens", value: fmtTokens(stats.total_cache_tokens) },
    { label: "Think tokens", value: fmtTokens(stats.total_thinking_tokens) },
    {
      label: "Avg duration",
      value: fmtDuration(stats.avg_duration_ms ? Math.round(stats.avg_duration_ms) : null),
    },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 mb-6">
      {cards.map((c) => (
        <div
          key={c.label}
          className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center"
        >
          <p className="text-xs text-gray-500 dark:text-gray-400">{c.label}</p>
          <p className="text-lg font-semibold mt-0.5">{c.value}</p>
        </div>
      ))}
    </div>
  );
}

// ---- Call detail card ------------------------------------------------------

function CallCard({ call }: { call: LLMCall & { event_type?: string } }) {
  const [expanded, setExpanded] = useState(false);
  const totalTok = call.input_tokens + call.output_tokens;

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded((p) => !p)}
        className="w-full flex flex-wrap gap-2 items-center px-4 py-2 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-750 text-left"
      >
        <span className="text-xs font-mono text-gray-500">#{call.call_index}</span>
        <Badge
          label={call.call_type}
          colorClass={call.is_image_call ? EVENT_TYPE_COLORS.image : "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"}
        />
        <Badge
          label={call.status}
          colorClass={STATUS_COLORS[call.status] ?? STATUS_COLORS.pending}
        />
        <span className="text-xs text-gray-600 dark:text-gray-400 font-mono">{call.model}</span>
        {call.temperature != null && (
          <span className="text-xs text-gray-500">t={call.temperature}</span>
        )}
        {call.thinking_level && (
          <span className="text-xs text-gray-500">think={call.thinking_level}</span>
        )}
        <span className="ml-auto text-xs text-gray-500">
          {fmtTokens(totalTok)} tok &bull; {fmtDuration(call.total_duration_ms)}
          {call.time_to_first_token_ms != null && (
            <> &bull; ttft {fmtDuration(call.time_to_first_token_ms)}</>
          )}
        </span>
        <span className="text-gray-400 text-xs">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="p-4 space-y-4 text-sm">
          {/* Token breakdown */}
          <div className="flex flex-wrap gap-4">
            <span className="text-gray-500">Input: <strong>{call.input_tokens.toLocaleString()}</strong></span>
            <span className="text-gray-500">Output: <strong>{call.output_tokens.toLocaleString()}</strong></span>
            <span className="text-gray-500">Cache read: <strong>{call.cache_read_tokens.toLocaleString()}</strong></span>
            <span className="text-gray-500">Thinking: <strong>{call.thinking_tokens.toLocaleString()}</strong></span>
            {call.prompt_name && (
              <span className="text-gray-500">Prompt: <strong>{call.prompt_name}</strong></span>
            )}
          </div>

          {/* Prompt / response */}
          {call.is_image_call ? (
            <div className="space-y-2">
              {call.prompt_text && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Prompt</p>
                  <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{call.prompt_text}</p>
                </div>
              )}
              {call.image_prompt && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Enhanced Prompt</p>
                  <p className="text-gray-600 dark:text-gray-400 whitespace-pre-wrap text-xs">{call.image_prompt}</p>
                </div>
              )}
              {call.image_data && (
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Generated Image</p>
                  <img
                    src={`data:image/png;base64,${call.image_data}`}
                    alt="Generated infographic"
                    className="max-w-sm rounded border border-gray-200 dark:border-gray-700"
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Prompt</p>
                <pre className="text-xs bg-gray-100 dark:bg-gray-900 rounded p-3 whitespace-pre-wrap overflow-auto max-h-60">
                  {call.prompt_text || "—"}
                </pre>
              </div>
              <div>
                <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Response</p>
                <pre className="text-xs bg-gray-100 dark:bg-gray-900 rounded p-3 whitespace-pre-wrap overflow-auto max-h-60">
                  {call.response_text || "—"}
                </pre>
              </div>
            </div>
          )}

          {call.error_message && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded p-3 text-red-700 dark:text-red-300 text-xs">
              {call.error_message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---- Event row -------------------------------------------------------------

function EventRow({ event }: { event: LLMEvent }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<LLMEvent | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleExpand() {
    if (!expanded && !detail) {
      setLoading(true);
      try {
        const d = await getObservabilityEvent(event.id);
        setDetail(d);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    setExpanded((p) => !p);
  }

  const calls = detail?.calls ?? [];
  const entityLink =
    event.entity_type === "incident" && event.session_id
      ? `/?session=${event.session_id}`
      : null;

  return (
    <>
      <tr
        className="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
        onClick={handleExpand}
      >
        <td className="px-4 py-3 text-xs text-gray-500">{event.id}</td>
        <td className="px-4 py-3">
          <Badge
            label={event.event_type}
            colorClass={EVENT_TYPE_COLORS[event.event_type] ?? "bg-gray-100 text-gray-700"}
          />
        </td>
        <td className="px-4 py-3">
          <Badge
            label={event.status}
            colorClass={STATUS_COLORS[event.status] ?? STATUS_COLORS.pending}
          />
        </td>
        <td className="px-4 py-3 text-xs text-gray-600 dark:text-gray-400">
          {entityLink ? (
            <a
              href={entityLink}
              className="text-blue-600 dark:text-blue-400 hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {event.entity_type} #{event.entity_id}
            </a>
          ) : event.entity_type ? (
            `${event.entity_type} #${event.entity_id ?? "?"}`
          ) : (
            "—"
          )}
        </td>
        <td className="px-4 py-3 text-xs text-right font-mono">
          {fmtTokens(event.total_tokens)}
        </td>
        <td className="px-4 py-3 text-xs text-right">{event.call_count}</td>
        <td className="px-4 py-3 text-xs text-right">{fmtDuration(event.duration_ms)}</td>
        <td className="px-4 py-3 text-xs text-gray-500">{fmtDate(event.created_at)}</td>
        <td className="px-4 py-3 text-xs text-gray-400">{expanded ? "▲" : "▼"}</td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={9} className="px-4 pb-4">
            {loading ? (
              <p className="text-sm text-gray-500 py-4 text-center">Loading calls…</p>
            ) : calls.length === 0 ? (
              <p className="text-sm text-gray-500 py-4 text-center">No calls recorded.</p>
            ) : (
              <div className="space-y-2 mt-2">
                {calls.map((c) => (
                  <CallCard key={c.id} call={c} />
                ))}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

// ---- Search results --------------------------------------------------------

type SearchRow = LLMCall & {
  event_type: string;
  entity_type: string | null;
  entity_id: number | null;
  session_id: string | null;
  score: number;
};

function SearchResults({ results }: { results: SearchRow[] }) {
  if (results.length === 0) {
    return <p className="text-sm text-gray-500 py-8 text-center">No results found.</p>;
  }
  return (
    <div className="space-y-3">
      {results.map((r) => (
        <div
          key={r.id}
          className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
        >
          <div className="flex flex-wrap gap-2 items-center mb-2">
            <Badge
              label={r.event_type}
              colorClass={EVENT_TYPE_COLORS[r.event_type] ?? "bg-gray-100 text-gray-700"}
            />
            <Badge
              label={r.call_type}
              colorClass="bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
            />
            <Badge
              label={r.status}
              colorClass={STATUS_COLORS[r.status] ?? STATUS_COLORS.pending}
            />
            <span className="text-xs font-mono text-gray-500">{r.model}</span>
            <span className="ml-auto text-xs text-gray-400">
              {fmtTokens(r.input_tokens + r.output_tokens)} tok &bull; {fmtDuration(r.total_duration_ms)}
            </span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 text-xs">
            <div>
              <p className="font-semibold text-gray-500 uppercase mb-1">Prompt</p>
              <p className="text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {truncate(r.prompt_text)}
              </p>
            </div>
            <div>
              <p className="font-semibold text-gray-500 uppercase mb-1">Response</p>
              <p className="text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                {truncate(r.response_text)}
              </p>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-2">{fmtDate(r.created_at)}</p>
        </div>
      ))}
    </div>
  );
}

// ---- Main page -------------------------------------------------------------

export default function ObservabilityPage() {
  const [stats, setStats] = useState<ObservabilityStats | null>(null);
  const [events, setEvents] = useState<LLMEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchRow[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [filterType, setFilterType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [view, setView] = useState<"events" | "search">("events");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [s, e] = await Promise.all([
        getObservabilityStats(),
        listObservabilityEvents({
          event_type: filterType || undefined,
          status: filterStatus || undefined,
          limit: 100,
        }),
      ]);
      setStats(s);
      setEvents(e);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [filterType, filterStatus]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    setView("search");
    try {
      const results = await searchObservability(searchQuery.trim(), "text", 30);
      setSearchResults(results as SearchRow[]);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  function handleClearSearch() {
    setSearchQuery("");
    setSearchResults(null);
    setView("events");
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">LLM Observability</h1>
        <button
          onClick={loadData}
          className="text-sm text-gray-500 hover:text-gray-800 dark:hover:text-gray-200"
        >
          Refresh
        </button>
      </div>

      {/* Stats */}
      <StatsBar stats={stats} />

      {/* Search + filters */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search prompts and responses (BM25)…"
            className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={searching || !searchQuery.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {searching ? "Searching…" : "Search"}
          </button>
          {searchResults !== null && (
            <button
              type="button"
              onClick={handleClearSearch}
              className="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded text-sm hover:bg-gray-300 dark:hover:bg-gray-600"
            >
              Clear
            </button>
          )}
        </form>

        {view === "events" && (
          <div className="flex gap-3">
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-900 focus:outline-none"
            >
              <option value="">All event types</option>
              {["diagnose", "chat", "classify", "image", "prompt_gen", "desc_gen"].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-900 focus:outline-none"
            >
              <option value="">All statuses</option>
              <option value="success">success</option>
              <option value="failed">failed</option>
              <option value="pending">pending</option>
            </select>
          </div>
        )}
      </div>

      {/* Content */}
      {view === "search" ? (
        <div>
          <h2 className="text-sm font-semibold text-gray-600 dark:text-gray-400 mb-3">
            Search results for &ldquo;{searchQuery}&rdquo;
          </h2>
          <SearchResults results={searchResults ?? []} />
        </div>
      ) : loading ? (
        <p className="text-center text-gray-500 py-12">Loading…</p>
      ) : events.length === 0 ? (
        <p className="text-center text-gray-500 py-12">No events recorded yet. Run a diagnosis to see logs here.</p>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Entity</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Tokens</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Calls</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Duration</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                <th className="px-4 py-3 w-8"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {events.map((event) => (
                <EventRow key={event.id} event={event} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
