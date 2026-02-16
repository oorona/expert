"use client";

import { useState, useEffect, useRef } from "react";

interface Props {
  /** The message displayed in the confirmation bar */
  message: string;
  /** Label for the confirm button (default: "Confirm") */
  confirmLabel?: string;
  /** Called when the user confirms */
  onConfirm: () => void | Promise<void>;
  /** Called when the user cancels (or timeout expires) */
  onCancel: () => void;
  /** Auto-cancel after this many seconds (default: 8) */
  timeout?: number;
  /** Visual variant */
  variant?: "danger" | "warning" | "neutral";
}

const variantStyles = {
  danger: {
    bar: "bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800",
    text: "text-red-700 dark:text-red-300",
    btn: "bg-red-600 hover:bg-red-700 text-white",
    progress: "bg-red-400 dark:bg-red-500",
  },
  warning: {
    bar: "bg-amber-50 dark:bg-amber-900/30 border-amber-200 dark:border-amber-800",
    text: "text-amber-700 dark:text-amber-300",
    btn: "bg-amber-600 hover:bg-amber-700 text-white",
    progress: "bg-amber-400 dark:bg-amber-500",
  },
  neutral: {
    bar: "bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700",
    text: "text-gray-700 dark:text-gray-300",
    btn: "bg-gray-600 hover:bg-gray-700 text-white",
    progress: "bg-gray-400 dark:bg-gray-500",
  },
};

export function InlineConfirm({
  message,
  confirmLabel = "Confirm",
  onConfirm,
  onCancel,
  timeout = 8,
  variant = "danger",
}: Props) {
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval>>(undefined);
  const styles = variantStyles[variant];

  useEffect(() => {
    if (timeout <= 0) return;
    const step = 50; // ms
    intervalRef.current = setInterval(() => {
      setElapsed((prev) => {
        const next = prev + step;
        if (next >= timeout * 1000) {
          onCancel();
        }
        return next;
      });
    }, step);
    return () => clearInterval(intervalRef.current);
  }, [timeout, onCancel]);

  async function handleConfirm() {
    clearInterval(intervalRef.current);
    setLoading(true);
    try {
      await onConfirm();
    } finally {
      setLoading(false);
    }
  }

  const progress = timeout > 0 ? Math.min(elapsed / (timeout * 1000), 1) : 0;

  return (
    <div
      className={`relative overflow-hidden rounded-lg border ${styles.bar} animate-in fade-in slide-in-from-top-1 duration-200`}
    >
      {/* Progress countdown bar */}
      {timeout > 0 && (
        <div
          className={`absolute bottom-0 left-0 h-0.5 ${styles.progress} transition-all duration-100 ease-linear`}
          style={{ width: `${(1 - progress) * 100}%` }}
        />
      )}

      <div className="flex items-center justify-between gap-3 px-3 py-2.5">
        <span className={`text-sm ${styles.text}`}>{message}</span>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-2.5 py-1 text-xs rounded font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={loading}
            className={`px-2.5 py-1 text-xs rounded font-medium transition-colors disabled:opacity-50 ${styles.btn}`}
          >
            {loading ? "…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
