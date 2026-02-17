"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CodeBlock } from "@/components/ui/CodeBlock";

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
      prose-pre:p-0 prose-pre:bg-transparent prose-pre:border-none
      prose-strong:text-gray-900 prose-strong:dark:text-gray-100
      prose-a:text-blue-600 prose-a:dark:text-blue-400
    ">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children }) {
            const match = /language-(\w+)/.exec(className || "");
            if (match) {
              return (
                <CodeBlock
                  language={match[1]}
                  code={String(children).replace(/\n$/, "")}
                />
              );
            }
            // Inline code
            return (
              <code className={className}>{children}</code>
            );
          },
          // Suppress the default <pre> wrapper when CodeBlock handles it
          pre({ children }) {
            return <>{children}</>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
