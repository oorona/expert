"use client";

import { useState } from "react";
import type { SchemaItem } from "@/types";
import { useToast } from "@/components/ui/Toast";

interface Props {
  schema: SchemaItem;
  onSave: (id: number, schemaJson: Record<string, unknown>) => Promise<void>;
  onToggle: (id: number, active: boolean) => Promise<void>;
}

export function SchemaEditor({ schema, onSave, onToggle }: Props) {
  const [jsonText, setJsonText] = useState(
    JSON.stringify(schema.schema_json, null, 2)
  );
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const toast = useToast();

  function handleChange(value: string) {
    setJsonText(value);
    setDirty(true);
    try {
      JSON.parse(value);
      setValidationError(null);
    } catch (err) {
      setValidationError(String(err));
    }
  }

  async function handleSave() {
    try {
      const parsed = JSON.parse(jsonText);
      setSaving(true);
      await onSave(schema.id, parsed);
      setSaving(false);
      setDirty(false);
      toast.success("Schema saved");
    } catch (err) {
      setSaving(false);
      if (err instanceof SyntaxError) {
        setValidationError(String(err));
      } else {
        toast.error(err instanceof Error ? err.message : "Save failed");
      }
    }
  }

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-800 dark:text-gray-200">{schema.name}</h3>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={schema.is_active}
              onChange={(e) => {
                const active = e.target.checked;
                onToggle(schema.id, active)
                  .then(() => toast.info(active ? "Schema activated" : "Schema deactivated"))
                  .catch((err: unknown) => toast.error(err instanceof Error ? err.message : "Toggle failed"));
              }}
              className="rounded"
            />
            Active
          </label>
          <button
            onClick={handleSave}
            disabled={!dirty || saving || !!validationError}
            className="px-3 py-1 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      <textarea
        value={jsonText}
        onChange={(e) => handleChange(e.target.value)}
        className={`w-full h-64 px-3 py-2 border rounded text-sm font-mono resize-y focus:ring-2 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100 ${
          validationError
            ? "border-red-400 focus:ring-red-500"
            : "border-gray-300 dark:border-gray-600 focus:ring-blue-500"
        }`}
      />

      {validationError && (
        <p className="text-xs text-red-600 dark:text-red-400 mt-1">{validationError}</p>
      )}

      {!validationError && jsonText && (
        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
          <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">Preview:</p>
          <div className="text-xs text-gray-600 dark:text-gray-400">
            {(() => {
              try {
                const parsed = JSON.parse(jsonText);
                const props = parsed.properties || {};
                return (
                  <ul className="list-disc pl-4">
                    {Object.entries(props).map(([key, val]) => (
                      <li key={key}>
                        <span className="font-medium">{key}</span>:{" "}
                        {(val as Record<string, string>).type}
                        {(val as Record<string, string>).description && (
                          <span className="text-gray-400">
                            {" "}
                            — {(val as Record<string, string>).description}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                );
              } catch {
                return null;
              }
            })()}
          </div>
        </div>
      )}
    </div>
  );
}
