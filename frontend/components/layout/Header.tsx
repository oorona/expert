"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "@/components/ui/ThemeProvider";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/articles", label: "Articles" },
  { href: "/admin/experts", label: "Experts" },
  { href: "/admin/prompts", label: "Prompts" },
  { href: "/admin/schemas", label: "Schemas" },
  { href: "/admin/api-keys", label: "API Keys" },
  { href: "/observability", label: "LLM Logs" },
];

const THEME_ICONS: Record<string, string> = {
  light: "☀️",
  dark: "🌙",
  system: "💻",
};

export function Header() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();

  function cycleTheme() {
    const order: ("light" | "dark" | "system")[] = ["light", "dark", "system"];
    const idx = order.indexOf(theme);
    setTheme(order[(idx + 1) % order.length]);
  }

  return (
    <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 px-6 py-3">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-gray-800 dark:text-gray-100">
          Expert Diagnostic Engine
        </h1>
        <div className="flex items-center gap-2">
          <nav className="flex gap-1">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                    active
                      ? "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300"
                      : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <button
            onClick={cycleTheme}
            className="ml-2 px-2 py-1.5 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            title={`Theme: ${theme}`}
          >
            {THEME_ICONS[theme]}
          </button>
        </div>
      </div>
    </header>
  );
}
