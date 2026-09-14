import React from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check } from "lucide-react";

interface CodeBlockProps {
  language?: string;
  children: string;
}

function CodeBlock({ language, children }: CodeBlockProps) {
  const [copied, setCopied] = React.useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(children);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="group relative my-2 overflow-hidden rounded-lg border border-nexus-border bg-[#0d1117]">
      <div className="flex items-center justify-between border-b border-nexus-border bg-[#161b22] px-4 py-1.5">
        <span className="text-xs text-gray-400">{language || "code"}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 rounded px-2 py-0.5 text-xs text-gray-400 transition-colors hover:bg-[#21262d] hover:text-gray-200"
        >
          {copied ? (
            <>
              <Check size={12} />
              Copied
            </>
          ) : (
            <>
              <Copy size={12} />
              Copy
            </>
          )}
        </button>
      </div>
      <SyntaxHighlighter
        language={language || "text"}
        style={oneDark}
        customStyle={{
          margin: 0,
          padding: "16px",
          background: "#0d1117",
          fontSize: "0.875rem",
          lineHeight: "1.5",
          borderRadius: 0,
        }}
      >
        {children.replace(/\n$/, "")}
      </SyntaxHighlighter>
    </div>
  );
}

interface MessageContentProps {
  content: string;
  className?: string;
}

export default function MessageContent({
  content,
  className = "",
}: MessageContentProps) {
  return (
    <div className={`prose prose-invert max-w-none prose-p:leading-relaxed prose-pre:my-2 ${className}`}>
      <ReactMarkdown
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const codeStr = String(children).replace(/\n$/, "");

            if (match) {
              return <CodeBlock language={match[1]}>{codeStr}</CodeBlock>;
            }

            if (codeStr.includes("\n")) {
              return <CodeBlock>{codeStr}</CodeBlock>;
            }

            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
          table({ children }) {
            return (
              <div className="my-4 overflow-x-auto">
                <table>{children}</table>
              </div>
            );
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
              >
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
