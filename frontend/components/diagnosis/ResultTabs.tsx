"use client";

import { useState } from "react";

interface Props {
  diagnosisContent: React.ReactNode;
  webSourcesContent: React.ReactNode | null;
  fileSearchContent: React.ReactNode | null;
}

export function ResultTabs({ diagnosisContent, webSourcesContent, fileSearchContent }: Props) {
  const [activeTab, setActiveTab] = useState<"diagnosis" | "web" | "document">(
    "diagnosis"
  );

  const tabs: { id: "diagnosis" | "web" | "document"; label: string }[] = [
    { id: "diagnosis", label: "Diagnosis" },
  ];
  if (webSourcesContent) {
    tabs.push({ id: "web", label: "Web Sources" });
  }
  if (fileSearchContent) {
    tabs.push({ id: "document", label: "Document Citations" });
  }

  return (
    <div>
      <div className="flex border-b border-gray-200 dark:border-gray-700">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "border-b-2 border-blue-500 text-blue-600 dark:text-blue-400"
                : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="pt-4">
        {activeTab === "diagnosis" && diagnosisContent}
        {activeTab === "web" && webSourcesContent}
        {activeTab === "document" && fileSearchContent}
      </div>
    </div>
  );
}
