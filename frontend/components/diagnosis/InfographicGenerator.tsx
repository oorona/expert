"use client";

import { useState } from "react";
import { generateInfographic, saveInfographic } from "@/lib/api";

interface Props {
  suggestedPrompt: string;
  incidentId?: number;
  savedInfographic?: string | null;
  onGenerated?: (imageData: string) => void;
}

const IMAGEN_MODELS = [
  { value: "gemini-2.5-flash-image", label: "Nano Banana (Fast - Recommended)" },
  { value: "gemini-3-pro-image-preview", label: "Nano Banana Pro (High Quality)" },
];

const ASPECT_RATIOS = [
  { value: "16:9", label: "16:9 (Widescreen)" },
  { value: "9:16", label: "9:16 (Portrait)" },
  { value: "1:1", label: "1:1 (Square)" },
  { value: "4:3", label: "4:3 (Standard)" },
  { value: "3:4", label: "3:4 (Portrait)" },
];

const IMAGE_SIZES = [
  { value: "1K", label: "1K (Fast)" },
  { value: "2K", label: "2K (Balanced)" },
  { value: "4K", label: "4K (High Quality)" },
];

export function InfographicGenerator({ suggestedPrompt, incidentId, savedInfographic, onGenerated }: Props) {
  const [prompt, setPrompt] = useState(suggestedPrompt);
  const [model, setModel] = useState("gemini-2.5-flash-image");
  const [aspectRatio, setAspectRatio] = useState("4:3");
  const [imageSize, setImageSize] = useState("1K");
  const [generating, setGenerating] = useState(false);
  const [generatedImage, setGeneratedImage] = useState<string | null>(
    savedInfographic ? `data:image/png;base64,${savedInfographic}` : null
  );
  const [error, setError] = useState<string | null>(null);
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [saving, setSaving] = useState(false);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);

    try {
      const result = await generateInfographic(prompt, aspectRatio, model, imageSize);
      setGeneratedImage(`data:image/png;base64,${result.image_data}`);

      // Save to incident if incidentId is provided
      if (incidentId) {
        setSaving(true);
        try {
          await saveInfographic(incidentId, result.image_data, prompt);
        } catch (saveErr) {
          console.error("Failed to save infographic:", saveErr);
          // Don't fail the whole operation if save fails
        } finally {
          setSaving(false);
        }
      }

      if (onGenerated) {
        onGenerated(result.image_data);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setGenerating(false);
    }
  }

  function handleDownload() {
    if (!generatedImage) return;

    const link = document.createElement("a");
    link.href = generatedImage;
    link.download = "infographic.png";
    link.click();
  }

  return (
    <div className="border border-blue-200 dark:border-blue-800 rounded-lg p-4 bg-blue-50 dark:bg-blue-900/20">
      <div className="flex items-start gap-3 mb-3">
        <span className="text-2xl">💡</span>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-1">
            Visual Aid Suggested
          </h3>
          <p className="text-xs text-blue-700 dark:text-blue-300">
            An infographic could help illustrate this problem. Review and customize the prompt below, then generate.
          </p>
        </div>
      </div>

      {!showPromptEditor ? (
        <div className="space-y-3">
          <div className="bg-white dark:bg-gray-800 rounded p-3 border border-blue-100 dark:border-blue-800">
            <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-3">
              {prompt}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 rounded transition-colors disabled:cursor-not-allowed"
            >
              {generating ? "Generating..." : "Generate Infographic"}
            </button>
            <button
              onClick={() => setShowPromptEditor(true)}
              className="px-4 py-2 text-sm font-medium text-blue-700 dark:text-blue-300 bg-white dark:bg-gray-800 border border-blue-300 dark:border-blue-700 rounded hover:bg-blue-50 dark:hover:bg-gray-700 transition-colors"
            >
              Customize Prompt
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
              Image Generation Model:
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100"
            >
              {IMAGEN_MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Aspect Ratio:
              </label>
              <select
                value={aspectRatio}
                onChange={(e) => setAspectRatio(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100"
              >
                {ASPECT_RATIOS.map((ar) => (
                  <option key={ar.value} value={ar.value}>
                    {ar.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Resolution:
              </label>
              <select
                value={imageSize}
                onChange={(e) => setImageSize(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100"
              >
                {IMAGE_SIZES.map((size) => (
                  <option key={size.value} value={size.value}>
                    {size.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
              Edit Image Generation Prompt:
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={6}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-800 dark:text-gray-100"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleGenerate}
              disabled={generating || !prompt.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 rounded transition-colors disabled:cursor-not-allowed"
            >
              {generating ? "Generating..." : "Generate Infographic"}
            </button>
            <button
              onClick={() => setShowPromptEditor(false)}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
            >
              Collapse
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-xs text-red-700 dark:text-red-300">
          <strong>Error:</strong> {error}
        </div>
      )}

      {generatedImage && (
        <div className="mt-4 space-y-3">
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden bg-white dark:bg-gray-800">
            <img
              src={generatedImage}
              alt="Generated infographic"
              className="w-full h-auto"
            />
          </div>
          <button
            onClick={handleDownload}
            className="px-4 py-2 text-sm font-medium text-blue-700 dark:text-blue-300 bg-white dark:bg-gray-800 border border-blue-300 dark:border-blue-700 rounded hover:bg-blue-50 dark:hover:bg-gray-700 transition-colors"
          >
            Download Image
          </button>
        </div>
      )}
    </div>
  );
}
