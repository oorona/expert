"use client";

import type { ChatMessage as ChatMessageType } from "@/types";
import { DiffView } from "./DiffView";
import { TokenCounter } from "@/components/ui/TokenCounter";

interface Props {
  message: ChatMessageType;
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2.5 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200"
        }`}
      >
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>

        {message.diff_content && (
          <div className="mt-3 border-t border-gray-300 dark:border-gray-600 pt-2">
            <p className="text-xs font-semibold mb-1">Changes:</p>
            <DiffView diffText={message.diff_content} />
          </div>
        )}

        {!isUser && message.token_usage.total_token_count > 0 && (
          <div className="mt-2 pt-1 border-t border-gray-200 dark:border-gray-600">
            <TokenCounter usage={message.token_usage} />
          </div>
        )}
      </div>
    </div>
  );
}
