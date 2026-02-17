"use client";

interface Props {
  category: string;
  displayName?: string;
  confidence?: number;
  isPrimary?: boolean;
  size?: "sm" | "md";
  showConfidence?: boolean;
}

const CATEGORY_COLORS: Record<string, string> = {
  Incident_Diagnostic: "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800",
  Performance_Tuning: "bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 border-orange-200 dark:border-orange-800",
  Security_Compliance: "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800",
  Capacity_Planning: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800",
  Impact_Analysis: "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800",
  Procedural_HowTo: "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 border-green-200 dark:border-green-800",
  Code_Generation: "bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800",
  Concept_Education: "bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-300 border-pink-200 dark:border-pink-800",
  Inventory_Discovery: "bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300 border-cyan-200 dark:border-cyan-800",
  Operational_Status: "bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800",
  Architecture_Design: "bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 border-violet-200 dark:border-violet-800",
  Backup_Recovery: "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800",
  Patching_Lifecycle: "bg-lime-100 dark:bg-lime-900/30 text-lime-700 dark:text-lime-300 border-lime-200 dark:border-lime-800",
  Data_Movement: "bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800",
  Cost_Licensing: "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800",
  Network_Connectivity: "bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800",
  Concurrency_Locking: "bg-fuchsia-100 dark:bg-fuchsia-900/30 text-fuchsia-700 dark:text-fuchsia-300 border-fuchsia-200 dark:border-fuchsia-800",
  Job_Scheduling: "bg-slate-100 dark:bg-slate-900/30 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-800",
  Configuration_Drift: "bg-zinc-100 dark:bg-zinc-900/30 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-800",
  Cloud_Infrastructure: "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800",
  default: "bg-gray-100 dark:bg-gray-900/30 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700"
};

export function CategoryBadge({
  category,
  displayName,
  confidence,
  isPrimary = false,
  size = "sm",
  showConfidence = false
}: Props) {
  const colorClass = CATEGORY_COLORS[category] || CATEGORY_COLORS.default;
  const sizeClass = size === "sm"
    ? "text-xs px-2 py-0.5"
    : "text-sm px-3 py-1";

  // Format display name: "Category_Name" -> "Category Name"
  const display = displayName || category.replace(/_/g, " ");

  const tooltipText = `Category: ${display}${confidence ? ` (${(confidence * 100).toFixed(0)}% confidence)` : ""}${isPrimary ? " - Primary" : ""}`;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-medium border ${colorClass} ${sizeClass}`}
      title={tooltipText}
    >
      {isPrimary && <span className="text-xs font-bold">★</span>}
      <span>{display}</span>
      {showConfidence && confidence !== undefined && (
        <span className="opacity-70 text-[0.7em] font-normal">
          {(confidence * 100).toFixed(0)}%
        </span>
      )}
    </span>
  );
}
