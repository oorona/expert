"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  content: string;
}

export function MarkdownRenderer({ content }: Props) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none
      prose-headings:mt-6 prose-headings:mb-3 prose-headings:font-bold
      prose-h2:text-lg prose-h2:border-b prose-h2:border-gray-200 prose-h2:dark:border-gray-700 prose-h2:pb-2
      prose-h3:text-base
      prose-p:mb-3 prose-p:leading-relaxed
      prose-li:mb-1
      prose-ol:my-3 prose-ul:my-3
      prose-code:bg-gray-100 prose-code:dark:bg-gray-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-sm
      prose-pre:bg-gray-50 prose-pre:dark:bg-gray-900 prose-pre:border prose-pre:border-gray-200 prose-pre:dark:border-gray-700 prose-pre:rounded-lg
      prose-strong:text-gray-900 prose-strong:dark:text-gray-100
      prose-a:text-blue-600 prose-a:dark:text-blue-400
    ">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
