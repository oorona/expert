import { readFileSync, existsSync } from "fs";

const BACKEND = process.env.INTERNAL_API_URL || "http://expert-backend:8000";

let _apiKey: string | null = null;

function getApiKey(): string {
  if (_apiKey !== null) return _apiKey;
  const keyFile = process.env.API_KEY_FILE || "/run/secrets/api_key";
  if (existsSync(keyFile)) {
    _apiKey = readFileSync(keyFile, "utf-8").trim();
  } else {
    _apiKey = process.env.API_KEY || "";
  }
  return _apiKey;
}

export function backendUrl(path: string): string {
  return `${BACKEND}${path}`;
}

export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return {
    "X-API-Key": getApiKey(),
    ...extra,
  };
}
