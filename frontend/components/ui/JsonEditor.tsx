"use client";

import { useRef, useEffect } from "react";

interface Props {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  hasError?: boolean;
}

function highlightJson(raw: string): string {
  const escaped = raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return escaped.replace(
    /("(\\u[0-9a-fA-F]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[{}[\],:])/g,
    (match) => {
      if (/^"/.test(match)) {
        if (/:$/.test(match)) {
          // JSON key
          return `<span style="color:#7dd3fc">${match}</span>`;
        }
        // JSON string value
        return `<span style="color:#86efac">${match}</span>`;
      }
      if (/true|false/.test(match)) {
        return `<span style="color:#fbbf24">${match}</span>`;
      }
      if (/null/.test(match)) {
        return `<span style="color:#f87171">${match}</span>`;
      }
      if (/^-?\d/.test(match)) {
        return `<span style="color:#c084fc">${match}</span>`;
      }
      // punctuation: {} [] , :
      return `<span style="color:#94a3b8">${match}</span>`;
    }
  );
}

export function JsonEditor({ value, onChange, className = "", hasError = false }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const preRef = useRef<HTMLPreElement>(null);

  // Sync scroll between textarea and pre
  function syncScroll() {
    if (textareaRef.current && preRef.current) {
      preRef.current.scrollTop = textareaRef.current.scrollTop;
      preRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }

  const sharedStyle: React.CSSProperties = {
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
    fontSize: "0.875rem",
    lineHeight: "1.5",
    padding: "0.5rem 0.75rem",
    margin: 0,
    border: "none",
    outline: "none",
    whiteSpace: "pre",
    overflowWrap: "normal",
    wordBreak: "normal",
    tabSize: 2,
    width: "100%",
    boxSizing: "border-box" as const,
  };

  return (
    <div
      className={`relative rounded overflow-hidden border ${
        hasError
          ? "border-red-400 focus-within:ring-2 focus-within:ring-red-500"
          : "border-gray-300 dark:border-gray-600 focus-within:ring-2 focus-within:ring-blue-500"
      } ${className}`}
      style={{ backgroundColor: "#0f172a" }}
    >
      {/* Syntax-highlighted layer */}
      <pre
        ref={preRef}
        aria-hidden="true"
        style={{
          ...sharedStyle,
          position: "absolute",
          top: 0,
          left: 0,
          height: "100%",
          overflow: "hidden",
          pointerEvents: "none",
          color: "#e2e8f0",
          background: "transparent",
        }}
        dangerouslySetInnerHTML={{ __html: highlightJson(value) + "\n" }}
      />

      {/* Editable textarea on top */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={syncScroll}
        spellCheck={false}
        style={{
          ...sharedStyle,
          position: "relative",
          display: "block",
          background: "transparent",
          color: "transparent",
          caretColor: "#e2e8f0",
          resize: "vertical",
          minHeight: "60vh",
          overflow: "auto",
        }}
      />
    </div>
  );
}
