"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  markdown: string;
  view: "preview" | "raw";
}

export function MarkdownPanel({ markdown, view }: Props) {
  if (view === "raw") {
    return (
      <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono leading-relaxed p-4 overflow-auto h-full bg-gray-50 rounded-lg border border-gray-200">
        {markdown}
      </pre>
    );
  }

  return (
    <div className="overflow-auto h-full p-4">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-xl font-bold text-gray-900 mt-6 mb-2 leading-tight">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-lg font-semibold text-gray-900 mt-5 mb-2 leading-tight">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-base font-semibold text-gray-800 mt-4 mb-1.5 leading-tight">{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 className="text-sm font-semibold text-gray-800 mt-3 mb-1">{children}</h4>
          ),
          h5: ({ children }) => (
            <h5 className="text-sm font-medium text-gray-700 mt-3 mb-1">{children}</h5>
          ),
          h6: ({ children }) => (
            <h6 className="text-xs font-medium text-gray-500 mt-2 mb-1 uppercase tracking-wide">{children}</h6>
          ),
          p: ({ children }) => (
            <p className="text-sm text-gray-700 leading-relaxed mb-3">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc list-outside ml-5 mb-3 space-y-0.5 text-sm text-gray-700">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-outside ml-5 mb-3 space-y-0.5 text-sm text-gray-700">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed">{children}</li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-gray-300 pl-3 my-3 text-gray-500 italic text-sm">{children}</blockquote>
          ),
          code: ({ className, children, ...props }) => {
            const isBlock = className?.startsWith("language-");
            if (isBlock) {
              return (
                <pre className="bg-gray-100 rounded-lg px-4 py-3 overflow-x-auto my-3 border border-gray-200">
                  <code className={`${className} text-xs font-mono text-gray-800 leading-relaxed`} {...props}>
                    {children}
                  </code>
                </pre>
              );
            }
            return (
              <code className="bg-gray-100 text-indigo-600 text-xs font-mono px-1.5 py-0.5 rounded" {...props}>
                {children}
              </code>
            );
          },
          table: ({ children }) => (
            <div className="overflow-x-auto my-3">
              <table className="w-full text-sm border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-gray-100">{children}</thead>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 text-left text-xs font-semibold text-gray-700 border border-gray-200">{children}</th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 text-xs text-gray-700 border border-gray-200">{children}</td>
          ),
          tr: ({ children }) => (
            <tr className="even:bg-gray-50">{children}</tr>
          ),
          hr: () => (
            <hr className="border-gray-200 my-4" />
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-gray-900">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="italic text-gray-700">{children}</em>
          ),
          a: ({ href, children }) => (
            <a href={href} className="text-indigo-600 underline hover:text-indigo-500 transition-colors" target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
