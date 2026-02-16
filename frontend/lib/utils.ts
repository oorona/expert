export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}

export function truncate(str: string, maxLen: number = 80): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + "...";
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}
