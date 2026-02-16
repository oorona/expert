"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  useEffect,
  type ReactNode,
} from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ToastType = "success" | "error" | "info" | "warning";

interface Toast {
  id: number;
  type: ToastType;
  message: string;
  duration: number; // ms, 0 = sticky
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType, duration?: number) => void;
  success: (message: string, duration?: number) => void;
  error: (message: string, duration?: number) => void;
  info: (message: string, duration?: number) => void;
  warning: (message: string, duration?: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const add = useCallback(
    (message: string, type: ToastType = "info", duration = 4000) => {
      const id = ++nextId;
      setToasts((prev) => [...prev, { id, type, message, duration }]);
      if (duration > 0) {
        setTimeout(() => remove(id), duration);
      }
    },
    [remove]
  );

  const ctx: ToastContextValue = {
    toast: add,
    success: (msg, dur) => add(msg, "success", dur),
    error: (msg, dur) => add(msg, "error", dur ?? 6000),
    info: (msg, dur) => add(msg, "info", dur),
    warning: (msg, dur) => add(msg, "warning", dur ?? 5000),
  };

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      {/* Toast container — bottom-right, above everything */}
      <div className="fixed bottom-4 right-4 z-[9999] flex flex-col-reverse gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onClose={() => remove(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within <ToastProvider>");
  }
  return ctx;
}

// ---------------------------------------------------------------------------
// Single toast item
// ---------------------------------------------------------------------------

const icons: Record<ToastType, string> = {
  success: "✓",
  error: "✕",
  info: "ℹ",
  warning: "⚠",
};

const colors: Record<ToastType, string> = {
  success:
    "bg-green-50 dark:bg-green-900/40 border-green-300 dark:border-green-700 text-green-800 dark:text-green-200",
  error:
    "bg-red-50 dark:bg-red-900/40 border-red-300 dark:border-red-700 text-red-800 dark:text-red-200",
  info: "bg-blue-50 dark:bg-blue-900/40 border-blue-300 dark:border-blue-700 text-blue-800 dark:text-blue-200",
  warning:
    "bg-amber-50 dark:bg-amber-900/40 border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-200",
};

const iconColors: Record<ToastType, string> = {
  success: "text-green-500 dark:text-green-400",
  error: "text-red-500 dark:text-red-400",
  info: "text-blue-500 dark:text-blue-400",
  warning: "text-amber-500 dark:text-amber-400",
};

function ToastItem({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Trigger enter animation
    requestAnimationFrame(() => setVisible(true));
  }, []);

  function handleClose() {
    setVisible(false);
    setTimeout(onClose, 200);
  }

  return (
    <div
      className={`pointer-events-auto flex items-start gap-2.5 px-4 py-3 rounded-lg border shadow-lg backdrop-blur-sm transition-all duration-200 ${
        colors[toast.type]
      } ${
        visible
          ? "translate-y-0 opacity-100"
          : "translate-y-2 opacity-0"
      }`}
    >
      <span className={`text-sm font-bold mt-0.5 ${iconColors[toast.type]}`}>
        {icons[toast.type]}
      </span>
      <p className="text-sm flex-1 leading-snug">{toast.message}</p>
      <button
        onClick={handleClose}
        className="text-current opacity-40 hover:opacity-70 text-xs ml-1 mt-0.5 shrink-0"
      >
        ✕
      </button>
    </div>
  );
}
