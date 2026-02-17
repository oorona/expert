"use client";

import { useEffect, useState } from "react";
import { listSchemas, updateSchema, createSchema } from "@/lib/api";
import { SchemaEditor } from "@/components/admin/SchemaEditor";
import type { SchemaItem } from "@/types";

export default function SchemasPage() {
  const [schemas, setSchemas] = useState<SchemaItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newJson, setNewJson] = useState('{\n  "type": "object",\n  "properties": {}\n}');

  useEffect(() => {
    loadSchemas();
  }, []);

  async function loadSchemas() {
    try {
      const data = await listSchemas();
      setSchemas(data);
      setSelectedId((prev) => prev ?? (data[0]?.id ?? null));
    } catch {
      // Backend may not be ready
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(id: number, schemaJson: Record<string, unknown>) {
    await updateSchema(id, { schema_json: schemaJson });
    await loadSchemas();
  }

  async function handleToggle(id: number, active: boolean) {
    await updateSchema(id, { is_active: active });
    await loadSchemas();
  }

  async function handleCreate() {
    if (!newName) return;
    try {
      const parsed = JSON.parse(newJson);
      await createSchema({ name: newName, schema_json: parsed });
      setShowCreate(false);
      setNewName("");
      setNewJson('{\n  "type": "object",\n  "properties": {}\n}');
      await loadSchemas();
    } catch {
      // JSON parse error
    }
  }

  const selectedSchema = schemas.find((s) => s.id === selectedId) ?? null;

  if (loading) {
    return <p className="text-center text-gray-500 dark:text-gray-400 py-8">Loading...</p>;
  }

  return (
    <div className="w-full space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold dark:text-gray-100">Schema Manager</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-3 py-1.5 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-700"
        >
          + New Schema
        </button>
      </div>

      {/* Schema selector */}
      <select
        value={selectedId ?? ""}
        onChange={(e) => setSelectedId(Number(e.target.value))}
        className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-800 dark:text-gray-100"
      >
        {schemas.map((s) => (
          <option key={s.id} value={s.id}>{s.name}</option>
        ))}
      </select>

      {showCreate && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 space-y-3">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Schema name"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm bg-white dark:bg-gray-700 dark:text-gray-100"
          />
          <textarea
            value={newJson}
            onChange={(e) => setNewJson(e.target.value)}
            className="w-full h-48 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm font-mono bg-white dark:bg-gray-700 dark:text-gray-100"
          />
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700"
          >
            Create
          </button>
        </div>
      )}

      {selectedSchema && (
        <SchemaEditor
          schema={selectedSchema}
          onSave={handleSave}
          onToggle={handleToggle}
        />
      )}
    </div>
  );
}
