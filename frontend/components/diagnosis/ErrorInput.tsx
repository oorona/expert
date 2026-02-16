"use client";

import { useEffect, useRef, useState } from "react";
import type { ExpertItem } from "@/types";

interface Props {
  onSubmit: (formData: FormData) => void;
  loading: boolean;
  model: string;
  temperature: number;
  thinkingLevel: string;
  useGrounding: boolean;
  useFileSearch: boolean;
  expertId: number | null;
  setExpertId: (v: number | null) => void;
  experts: ExpertItem[];
  initialErrorText?: string | null;
}

export function ErrorInput({
  onSubmit,
  loading,
  model,
  temperature,
  thinkingLevel,
  useGrounding,
  useFileSearch,
  expertId,
  setExpertId,
  experts,
  initialErrorText,
}: Props) {
  const [errorText, setErrorText] = useState(initialErrorText || "");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeExperts = experts.filter((e) => e.is_active);

  // Update error text when initial value changes (e.g. review mode)
  useEffect(() => {
    if (initialErrorText) setErrorText(initialErrorText);
  }, [initialErrorText]);

  function handleImageChange(file: File | null) {
    setImageFile(file);
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => setImagePreview(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      setImagePreview(null);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) {
      handleImageChange(file);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!errorText && !imageFile) return;

    const formData = new FormData();
    formData.append("error_text", errorText);
    formData.append("model", model);
    formData.append("temperature", String(temperature));
    formData.append("thinking_level", thinkingLevel);
    formData.append("use_grounding", String(useGrounding));
    formData.append("use_file_search", String(useFileSearch));
    if (expertId !== null) {
      formData.append("expert_id", String(expertId));
    }
    if (imageFile) {
      formData.append("image", imageFile);
    }

    onSubmit(formData);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Expert Selector */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Expert
        </label>
        <select
          value={expertId ?? ""}
          onChange={(e) => setExpertId(e.target.value ? Number(e.target.value) : null)}
          disabled={loading}
          className={`w-full px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-800 dark:text-gray-100 transition-colors ${
            !expertId ? "border-red-400 dark:border-red-500" : "border-gray-300 dark:border-gray-600"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <option value="" disabled>Select an expert…</option>
          {activeExperts.map((ex) => (
            <option key={ex.id} value={ex.id}>
              {ex.name} ({ex.document_count} docs)
            </option>
          ))}
        </select>
        {!expertId && (
          <p className="text-xs text-red-500 dark:text-red-400 mt-1">Please select an expert to continue</p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Error Description
        </label>
        <textarea
          value={errorText}
          onChange={(e) => setErrorText(e.target.value)}
          placeholder="Paste your error message, stack trace, or log entry..."
          className="w-full h-40 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-mono resize-y focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100"
        />
      </div>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-4 text-center hover:border-blue-400 dark:hover:border-blue-500 transition-colors"
      >
        {imagePreview ? (
          <div className="relative inline-block">
            <img
              src={imagePreview}
              alt="Preview"
              className="max-h-48 rounded"
            />
            <button
              type="button"
              onClick={() => handleImageChange(null)}
              className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-6 h-6 text-xs"
            >
              X
            </button>
          </div>
        ) : (
          <div>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
              Drag & drop a screenshot, or
            </p>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium"
            >
              browse files
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => handleImageChange(e.target.files?.[0] || null)}
            />
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={loading || (!errorText && !imageFile) || !expertId}
        className="w-full py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? "Analyzing..." : !expertId ? "Select an Expert to Diagnose" : "Diagnose Error"}
      </button>
    </form>
  );
}
