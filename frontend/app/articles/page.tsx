"use client";

import { useEffect, useState } from "react";
import { deleteSession, listSessions, searchContent, listExperts } from "@/lib/api";
import { ArticleSearch } from "@/components/articles/ArticleSearch";
import { ArticleList } from "@/components/articles/ArticleList";
import { CategoryFilter } from "@/components/articles/CategoryFilter";
import type { SessionListItem, SearchResult, ExpertItem } from "@/types";

export default function ArticlesPage() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [filteredSessions, setFilteredSessions] = useState<SessionListItem[]>([]);
  const [searchResults, setSearchResults] = useState<SearchResult[] | null>(null);
  const [experts, setExperts] = useState<ExpertItem[]>([]);
  const [selectedExpertId, setSelectedExpertId] = useState<number | null | "none">(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSessions();
    loadExperts();
  }, []);

  useEffect(() => {
    // Filter sessions when expert or category filter changes
    let filtered = sessions;

    // Expert filter
    if (selectedExpertId === "none") {
      filtered = filtered.filter((s) => !s.expert_id);
    } else if (selectedExpertId !== null) {
      filtered = filtered.filter((s) => s.expert_id === selectedExpertId);
    }

    // Category filter
    if (selectedCategory) {
      filtered = filtered.filter((s) =>
        s.categories?.some((c) => c.category === selectedCategory)
      );
    }

    setFilteredSessions(filtered);
  }, [sessions, selectedExpertId, selectedCategory]);

  async function loadSessions() {
    setSearchResults(null);
    try {
      const data = await listSessions();
      setSessions(data);
    } catch {
      // Backend may not be ready
    } finally {
      setLoading(false);
    }
  }

  async function loadExperts() {
    try {
      const data = await listExperts();
      setExperts(data.filter((e) => e.is_active));
    } catch {
      // Backend may not be ready
    }
  }

  async function handleSearch(
    query: string,
    searchType: "text" | "semantic" | "hybrid"
  ) {
    setLoading(true);
    try {
      const results = await searchContent(query, searchType, "incidents");
      setSearchResults(results);
    } catch {
      // Handle error
    } finally {
      setLoading(false);
    }
  }

  function handleClear() {
    setSearchResults(null);
  }

  async function handleDelete(id: number) {
    try {
      await deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      setSearchResults((prev) =>
        prev ? prev.filter((r) => r.id !== id) : null
      );
      window.dispatchEvent(new Event("sessions-changed"));
    } catch {
      // Handle error
    }
  }

  return (
    <div className="w-full space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold dark:text-gray-100">Knowledge Base</h2>
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {sessions.length} diagnosis{sessions.length !== 1 ? "es" : ""} saved
        </span>
      </div>

      <div className="flex gap-4 items-center flex-wrap">
        <ArticleSearch onSearch={handleSearch} onClear={handleClear} />
        {!searchResults && (
          <>
            {experts.length > 0 && (
              <div className="flex items-center gap-2">
                <label htmlFor="expert-filter" className="text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">
                  Expert:
                </label>
                <select
                  id="expert-filter"
                  value={selectedExpertId ?? ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    setSelectedExpertId(
                      val === "" ? null : val === "none" ? "none" : Number(val)
                    );
                  }}
                  className="px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">All Experts</option>
                  <option value="none">No Expert Assigned</option>
                  {experts.map((expert) => (
                    <option key={expert.id} value={expert.id}>
                      {expert.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <CategoryFilter
              selectedCategory={selectedCategory}
              onCategoryChange={setSelectedCategory}
            />
          </>
        )}
      </div>

      {loading ? (
        <p className="text-gray-500 dark:text-gray-400 text-center py-8">Loading...</p>
      ) : searchResults ? (
        <ArticleList
          onDelete={handleDelete}
          experts={experts}
          items={searchResults.map((r) => ({
            type: "search" as const,
            id: r.id,
            session_id: r.session_id,
            error_text: r.error_text || null,
            title: r.title,
            error_summary: r.error_summary,
            markdown_content: r.markdown_content,
            score: r.score,
          }))}
        />
      ) : (
        <ArticleList
          onDelete={handleDelete}
          experts={experts}
          items={filteredSessions.map((s) => ({
            type: "session" as const,
            id: s.id,
            session_id: s.session_id,
            error_text: s.error_text,
            title: s.title,
            error_summary: s.error_summary,
            status: s.status,
            expert_id: s.expert_id,
            categories: s.categories,
            created_at: s.created_at,
          }))}
        />
      )}
    </div>
  );
}
