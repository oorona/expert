"use client";

interface Props {
  diffText: string;
}

export function DiffView({ diffText }: Props) {
  const lines = diffText.split("\n");

  return (
    <pre className="font-mono text-xs overflow-x-auto rounded bg-gray-900 p-3">
      {lines.map((line, i) => {
        let className = "text-gray-300";
        if (line.startsWith("+") && !line.startsWith("+++")) {
          className = "text-green-400 bg-green-900/30";
        } else if (line.startsWith("-") && !line.startsWith("---")) {
          className = "text-red-400 bg-red-900/30";
        } else if (line.startsWith("@@")) {
          className = "text-blue-400";
        }
        return (
          <div key={i} className={className}>
            {line}
          </div>
        );
      })}
    </pre>
  );
}
