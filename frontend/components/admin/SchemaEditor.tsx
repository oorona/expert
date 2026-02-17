"use client";

import { useState, useEffect } from "react";
import type { SchemaItem, Category } from "@/types";
import { useToast } from "@/components/ui/Toast";
import { getSchemaCategoryMappings, updateSchemaCategoryMappings, listCategories } from "@/lib/api";
import { JsonEditor } from "@/components/ui/JsonEditor";

interface Props {
  schema: SchemaItem;
  onSave: (id: number, schemaJson: Record<string, unknown>) => Promise<void>;
  onToggle: (id: number, active: boolean) => Promise<void>;
}

interface CategoryMapping {
  category_name: string;
  priority: number;
}

export function SchemaEditor({ schema, onSave, onToggle }: Props) {
  const [jsonText, setJsonText] = useState(
    JSON.stringify(schema.json_schema || schema.schema_json || {}, null, 2)
  );
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [showCategories, setShowCategories] = useState(false);
  const [categoryMappings, setCategoryMappings] = useState<CategoryMapping[]>([]);
  const [allCategories, setAllCategories] = useState<Category[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(false);
  const toast = useToast();

  // Reset content when schema changes (dropdown switch)
  useEffect(() => {
    setJsonText(JSON.stringify(schema.json_schema || schema.schema_json || {}, null, 2));
    setDirty(false);
    setValidationError(null);
    setShowCategories(false);
  }, [schema.id]);

  useEffect(() => {
    if (showCategories) {
      if (allCategories.length === 0) {
        loadAllCategories();
      }
      loadCategoryMappings();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showCategories, schema.id]);

  async function loadAllCategories() {
    try {
      const cats = await listCategories();
      setAllCategories(cats);
    } catch (err) {
      toast.error("Failed to load categories");
    }
  }

  async function loadCategoryMappings() {
    try {
      setLoadingCategories(true);
      const mappings = await getSchemaCategoryMappings(schema.id);
      setCategoryMappings(mappings);
    } catch (err) {
      toast.error("Failed to load category mappings");
    } finally {
      setLoadingCategories(false);
    }
  }

  async function handleSaveCategories() {
    try {
      setLoadingCategories(true);
      await updateSchemaCategoryMappings(schema.id, categoryMappings);
      toast.success("Category mappings saved");
    } catch (err) {
      toast.error("Failed to save category mappings");
    } finally {
      setLoadingCategories(false);
    }
  }

  function handleAddCategory(categoryName: string) {
    if (!categoryMappings.find(m => m.category_name === categoryName)) {
      setCategoryMappings([...categoryMappings, { category_name: categoryName, priority: 1 }]);
    }
  }

  function handleRemoveCategory(categoryName: string) {
    setCategoryMappings(categoryMappings.filter(m => m.category_name !== categoryName));
  }

  function handleChangePriority(categoryName: string, priority: number) {
    setCategoryMappings(
      categoryMappings.map(m =>
        m.category_name === categoryName ? { ...m, priority } : m
      )
    );
  }

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
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-gray-800 dark:text-gray-200">{schema.name}</h3>
          <button
            onClick={() => setShowCategories(!showCategories)}
            className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            {showCategories ? "Hide" : "Show"} Categories
          </button>
        </div>
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

      {showCategories && (
        <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-600">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Category Associations</h4>
            <button
              onClick={handleSaveCategories}
              disabled={loadingCategories}
              className="text-xs px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400"
            >
              {loadingCategories ? "Saving..." : "Save Categories"}
            </button>
          </div>

          {loadingCategories && categoryMappings.length === 0 ? (
            <p className="text-sm text-gray-500">Loading...</p>
          ) : (
            <>
              <div className="space-y-2 mb-3">
                {categoryMappings.map((mapping) => {
                  const cat = allCategories.find(c => c.name === mapping.category_name);
                  return (
                    <div key={mapping.category_name} className="flex items-center gap-2 text-sm">
                      <span className="flex-1 text-gray-700 dark:text-gray-300">
                        {cat?.display_name || mapping.category_name}
                      </span>
                      <label className="flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400">
                        Priority:
                        <input
                          type="number"
                          min="1"
                          max="10"
                          value={mapping.priority}
                          onChange={(e) => handleChangePriority(mapping.category_name, parseInt(e.target.value) || 1)}
                          className="w-12 px-1 py-0.5 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-gray-200"
                        />
                      </label>
                      <button
                        onClick={() => handleRemoveCategory(mapping.category_name)}
                        className="text-xs px-2 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded hover:bg-red-200 dark:hover:bg-red-900/50"
                      >
                        Remove
                      </button>
                    </div>
                  );
                })}
              </div>

              <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                <select
                  onChange={(e) => {
                    if (e.target.value) {
                      handleAddCategory(e.target.value);
                      e.target.value = "";
                    }
                  }}
                  className="w-full text-sm px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 dark:text-gray-200"
                >
                  <option value="">+ Add Category</option>
                  {allCategories
                    .filter(c => !categoryMappings.find(m => m.category_name === c.name))
                    .map(c => (
                      <option key={c.name} value={c.name}>
                        {c.display_name}
                      </option>
                    ))}
                </select>
              </div>
            </>
          )}
        </div>
      )}

      <JsonEditor
        value={jsonText}
        onChange={handleChange}
        hasError={!!validationError}
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
