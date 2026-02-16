"use client";

import { useEffect, useRef } from "react";

interface Props {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "info";
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
  loading?: boolean;
}

const variantStyles = {
  danger: {
    bg: "bg-red-600 hover:bg-red-700",
    text: "text-red-600 dark:text-red-400",
  },
  warning: {
    bg: "bg-amber-600 hover:bg-amber-700",
    text: "text-amber-600 dark:text-amber-400",
  },
  info: {
    bg: "bg-blue-600 hover:bg-blue-700",
    text: "text-blue-600 dark:text-blue-400",
  },
};

export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "danger",
  onConfirm,
  onCancel,
  loading = false,
}: Props) {
  const styles = variantStyles[variant];
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus trap and ESC key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !loading) {
        onCancel();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onCancel, loading]);

  // Prevent body scroll
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        ref={dialogRef}
        className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 pt-6 pb-4">
          <h3 className={`text-lg font-semibold ${styles.text}`}>
            {title}
          </h3>
        </div>

        {/* Message */}
        <div className="px-6 pb-6">
          <p className="text-sm text-gray-600 dark:text-gray-300">
            {message}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 bg-gray-50 dark:bg-gray-900/30 rounded-b-lg">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${styles.bg}`}
          >
            {loading ? "Processing..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
