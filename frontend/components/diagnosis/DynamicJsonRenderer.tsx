"use client";

import { useState } from "react";
import { CodeBlock } from "@/components/ui/CodeBlock";

interface Props {
  data: Record<string, unknown>;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200 border-red-300 dark:border-red-700",
  high: "bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200 border-orange-300 dark:border-orange-700",
  medium: "bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200 border-yellow-300 dark:border-yellow-700",
  low: "bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 border-green-300 dark:border-green-700",
};

const SECTION_ICONS: Record<string, string> = {
  error_summary: "⚠️",
  root_cause: "🔍",
  severity: "🎯",
  affected_systems: "🖥️",
  resolution_steps: "🔧",
  preventive_measures: "🛡️",
  additional_notes: "📝",
};

export function DynamicJsonRenderer({ data }: Props) {
  // If the data only has a single "response" key with a string value,
  // it's an old-format unstructured response — render as formatted markdown-like sections
  if (
    Object.keys(data).length === 1 &&
    "response" in data &&
    typeof data.response === "string"
  ) {
    return <UnstructuredResponse text={data.response as string} />;
  }

  const priorityKeys = [
    // Fixer / general
    "error_summary",
    "severity",
    "root_cause",
    "affected_systems",
    "resolution_steps",
    "preventive_measures",
    "additional_notes",
    // Developer schema
    "script_summary",
    "safety_warning",
    "primary_language",
    "code",
    "explanation",
    "variables_to_replace",
  ];
  const metadataKeys = ["title", "visual_aid_suggested", "image_generation_prompt", "expert_id"];
  const extraKeys = Object.keys(data).filter((k) => !priorityKeys.includes(k) && !metadataKeys.includes(k));
  const allKeys = [...priorityKeys.filter((k) => k in data), ...extraKeys];

  const primaryLanguage = typeof data["primary_language"] === "string" ? data["primary_language"] : undefined;

  return (
    <div className="space-y-4">
      {allKeys.map((key) => (
        <Section
          key={key}
          sectionKey={key}
          value={data[key]}
          language={key === "code" ? primaryLanguage : undefined}
        />
      ))}
    </div>
  );
}

/** Render old-format responses that are a single markdown string. */
function UnstructuredResponse({ text }: { text: string }) {
  // Split by markdown headings to create visual sections
  const sections = text.split(/^(#{1,3}\s+.+)$/m).filter(Boolean);
  const parsed: { heading: string; body: string }[] = [];

  for (let i = 0; i < sections.length; i++) {
    const s = sections[i].trim();
    if (/^#{1,3}\s+/.test(s)) {
      parsed.push({ heading: s.replace(/^#{1,3}\s+/, ""), body: (sections[i + 1] || "").trim() });
      i++; // skip body
    } else if (parsed.length === 0) {
      // Leading text before any heading
      parsed.push({ heading: "Overview", body: s });
    }
  }

  if (parsed.length === 0) {
    parsed.push({ heading: "Response", body: text });
  }

  return (
    <div className="space-y-4">
      {parsed.map((sec, i) => {
        const key = sec.heading.toLowerCase().replace(/[^a-z0-9]+/g, "_");
        const icon = SECTION_ICONS[key] || "📄";
        return (
          <div key={i} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 dark:bg-gray-800/50">
              <span className="text-lg">{icon}</span>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-300">
                {sec.heading}
              </h3>
            </div>
            <div className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed">
              {sec.body}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Section({ sectionKey, value, language }: { sectionKey: string; value: unknown; language?: string }) {
  const [collapsed, setCollapsed] = useState(false);
  const icon = SECTION_ICONS[sectionKey] || "📄";
  const title = sectionKey.replace(/_/g, " ");

  // Severity gets special inline rendering
  if (sectionKey === "severity" && typeof value === "string") {
    const colors = SEVERITY_COLORS[value.toLowerCase()] || SEVERITY_COLORS.medium;
    return (
      <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${colors}`}>
        <span className="text-lg">{icon}</span>
        <span className="text-sm font-semibold uppercase tracking-wide capitalize">{title}</span>
        <span className="ml-auto text-sm font-bold uppercase">{value}</span>
      </div>
    );
  }

  // Error summary gets a prominent card
  if (sectionKey === "error_summary" && typeof value === "string") {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg">{icon}</span>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-red-800 dark:text-red-200 capitalize">
            {title}
          </h3>
        </div>
        <p className="text-sm text-red-700 dark:text-red-300 whitespace-pre-wrap">{value}</p>
      </div>
    );
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-4 py-3 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-left"
      >
        <span className="text-lg">{icon}</span>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-300 capitalize flex-1">
          {title}
        </h3>
        <span className="text-gray-400 dark:text-gray-500 text-xs">
          {collapsed ? "▶" : "▼"}
        </span>
      </button>
      {!collapsed && (
        <div className={sectionKey === "code" ? "" : "px-4 py-3"}>
          <SectionContent sectionKey={sectionKey} value={value} language={language} />
        </div>
      )}
    </div>
  );
}

function guessLanguage(cmd: string): string | undefined {
  const t = cmd.trimStart().toUpperCase();
  if (/^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|BEGIN|DECLARE|MERGE|TRUNCATE|WITH\s)/.test(t)) return "sql";
  if (/^(#!\/bin\/(ba)?sh|#!\/usr\/bin\/(env\s+)?(ba)?sh)/.test(cmd) || /\b(grep|sed|awk|docker|kubectl|git|chmod|chown|sudo|systemctl|service|psql|sqlplus|rman)\b/.test(cmd)) return "bash";
  if (/^(def |class |import |from .* import|print\(|if __name__)/.test(cmd)) return "python";
  return undefined;
}

function SectionContent({ sectionKey, value, language }: { sectionKey: string; value: unknown; language?: string }) {
  if (value === null || value === undefined) {
    return <span className="text-gray-400 dark:text-gray-500 italic text-sm">N/A</span>;
  }

  // Developer schema: code block with syntax highlighting
  if (sectionKey === "code" && typeof value === "string") {
    return (
      <div className="relative group">
        <CodeBlock code={value} language={language} />
        <button
          type="button"
          onClick={() => navigator.clipboard.writeText(value)}
          className="absolute top-10 right-2 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded opacity-0 group-hover:opacity-100 transition-opacity"
          title="Copy code"
        >
          📋 Copy
        </button>
      </div>
    );
  }

  // Numbered steps for resolution_steps and preventive_measures
  if (
    (sectionKey === "resolution_steps" || sectionKey === "preventive_measures") &&
    Array.isArray(value)
  ) {
    return (
      <ol className="space-y-4">
        {value.map((item, i) => {
          // New structured format: { action, command }
          if (typeof item === "object" && item !== null && "action" in item) {
            const step = item as { action: string; command?: string };
            return (
              <li key={i} className="flex gap-3 items-start">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 text-xs font-bold flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 dark:text-gray-300">{step.action}</p>
                  {step.command && (
                    <div className="mt-2 relative group">
                      <CodeBlock
                        code={step.command}
                        language={guessLanguage(step.command)}
                      />
                      <button
                        type="button"
                        onClick={() => navigator.clipboard.writeText(step.command!)}
                        className="absolute top-9 right-2 px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Copy command"
                      >
                        📋 Copy
                      </button>
                    </div>
                  )}
                </div>
              </li>
            );
          }
          // Legacy string format
          return (
            <li key={i} className="flex gap-3 items-start">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 text-xs font-bold flex items-center justify-center mt-0.5">
                {i + 1}
              </span>
              <span className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                {typeof item === "string" ? item : JSON.stringify(item)}
              </span>
            </li>
          );
        })}
      </ol>
    );
  }

  // Tags/pills for affected_systems
  if (sectionKey === "affected_systems" && Array.isArray(value)) {
    return (
      <div className="flex flex-wrap gap-2">
        {value.map((item, i) => (
          <span
            key={i}
            className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800"
          >
            {typeof item === "string" ? item : JSON.stringify(item)}
          </span>
        ))}
      </div>
    );
  }

  return <GenericValue value={value} />;
}

function GenericValue({ value }: { value: unknown }): React.ReactNode {
  if (typeof value === "string") {
    return <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{value}</p>;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return (
      <span className="font-mono bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-sm text-gray-800 dark:text-gray-200">
        {String(value)}
      </span>
    );
  }
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc pl-5 space-y-1">
        {value.map((item, i) => (
          <li key={i} className="text-sm text-gray-700 dark:text-gray-300">
            <GenericValue value={item} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object" && value !== null) {
    return (
      <div className="pl-4 border-l-2 border-gray-200 dark:border-gray-600 space-y-2 mt-1">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k}>
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">
              {k.replace(/_/g, " ")}
            </span>
            <div className="mt-0.5">
              <GenericValue value={v} />
            </div>
          </div>
        ))}
      </div>
    );
  }
  return <p className="text-sm text-gray-700 dark:text-gray-300">{String(value)}</p>;
}
