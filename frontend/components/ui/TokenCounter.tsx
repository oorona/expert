"use client";

import type { TokenUsage } from "@/types";

interface Props {
  usage: TokenUsage;
}

export function TokenCounter({ usage }: Props) {
  return (
    <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400">
      <span>
        Input: <strong>{usage.prompt_token_count.toLocaleString()}</strong>
      </span>
      <span>
        Output: <strong>{usage.candidates_token_count.toLocaleString()}</strong>
      </span>
      <span>
        Total: <strong>{usage.total_token_count.toLocaleString()}</strong>
      </span>
      {usage.cached_content_token_count > 0 && (
        <span>
          Cached:{" "}
          <strong>{usage.cached_content_token_count.toLocaleString()}</strong>
        </span>
      )}
    </div>
  );
}
