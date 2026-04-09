"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { cn } from "@/lib/utils";

interface MarkdownContentProps {
  content: string;
  className?: string;
  enableMath?: boolean;
  isStreaming?: boolean;
}

interface MarkdownRendererProps {
  content: string;
  className?: string;
  enableMath: boolean;
  variant: "final" | "streaming";
}

const DATA_URI_IMAGE_MARKDOWN_REGEX =
  /!\[([^\]]*)\]\s*\(\s*data:image\/[a-zA-Z0-9.+-]+;base64,[^)]*\)/gim;
const DATA_URI_REGEX = /data:image\/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+/gim;
const INLINE_SVG_REGEX = /<svg[\s\S]*?<\/svg>/gim;
const OMITTED_IMAGE_MARKDOWN_REGEX =
  /!\[([^\]]*)\]\s*\(\s*\[inline image payload omitted; see tool visualization\]\s*\)?/gim;
const FENCED_CODE_BLOCK_REGEX = /```[\s\S]*?```/g;
const FENCE_DELIMITER_REGEX = /^\s*(`{3,}|~{3,})/;
const STREAMING_SENTENCE_BOUNDARY_REGEX =
  /[.!?。！？;；:：](?:["')\]]*)\s+/g;
const STREAMING_BLOCK_TARGET_LENGTH = 320;
const STREAMING_MIN_TAIL_LENGTH = 120;
const STREAMING_UNSAFE_TAIL_START_REGEX = /^[)\]}>,:;.!?]/;
const MARKDOWN_PROSE_CLASS =
  "prose min-w-0 max-w-full overflow-hidden break-words text-sm leading-relaxed text-inherit [font-family:var(--font-family-base)] [&_h1:first-child]:mt-0 [&_h1]:mb-4 [&_h1]:mt-6 [&_h1]:font-semibold [&_h2:first-child]:mt-0 [&_h2]:mb-4 [&_h2]:mt-6 [&_h2]:font-semibold [&_h3:first-child]:mt-0 [&_h3]:mb-4 [&_h3]:mt-6 [&_h3]:font-semibold [&_h4:first-child]:mt-0 [&_h4]:mb-4 [&_h4]:mt-6 [&_h4]:font-semibold [&_h5:first-child]:mt-0 [&_h5]:mb-4 [&_h5]:mt-6 [&_h5]:font-semibold [&_h6:first-child]:mt-0 [&_h6]:mb-4 [&_h6]:mt-6 [&_h6]:font-semibold [&_p:last-child]:mb-0 [&_p]:mb-4";

function containsLikelyMath(expression: string): boolean {
  const normalized = expression.trim();
  if (!normalized) return false;

  return (
    /\\[a-zA-Z]+/.test(normalized) ||
    /[_^]/.test(normalized) ||
    /[=<>]/.test(normalized) ||
    /(?:∑|Σ|∫|∞|θ|α|β|γ|λ|μ|σ|Δ)/.test(normalized) ||
    /[A-Za-z]\([^)]*\)/.test(normalized)
  );
}

function normalizeMathExpression(expression: string): string {
  return expression.trim().replace(/\\\\/g, "\\");
}

function buildDisplayMathBlock(
  expression: string,
  equationCounter: { value: number },
  options?: { numbered?: boolean }
): string {
  const numbered = options?.numbered ?? true;
  const trimmed = normalizeMathExpression(expression);
  if (!trimmed) return "";

  const hasExplicitTag = /\\tag\{.*?\}/.test(trimmed);
  const needsTag = numbered && !hasExplicitTag;
  const taggedMath = needsTag
    ? `${trimmed} \\tag{${++equationCounter.value}}`
    : trimmed;

  return `\n\n$$\n${taggedMath}\n$$\n\n`;
}

function normalizeMathInNonCodeSegment(
  segment: string,
  equationCounter: { value: number }
): string {
  let normalized = segment;

  normalized = normalized.replace(
    /\\begin\{equation\*\}([\s\S]*?)\\end\{equation\*\}/g,
    (_match, expression: string) =>
      buildDisplayMathBlock(expression, equationCounter, { numbered: false })
  );

  normalized = normalized.replace(
    /\\begin\{equation\}([\s\S]*?)\\end\{equation\}/g,
    (_match, expression: string) => buildDisplayMathBlock(expression, equationCounter)
  );

  normalized = normalized.replace(
    /\\begin\{align\*\}([\s\S]*?)\\end\{align\*\}/g,
    (_match, expression: string) =>
      buildDisplayMathBlock(`\\begin{aligned}${expression}\\end{aligned}`, equationCounter, {
        numbered: false,
      })
  );

  normalized = normalized.replace(
    /\\begin\{align\}([\s\S]*?)\\end\{align\}/g,
    (_match, expression: string) =>
      buildDisplayMathBlock(`\\begin{aligned}${expression}\\end{aligned}`, equationCounter)
  );

  normalized = normalized.replace(
    /\\\[((?:.|\n)*?)\\\]/g,
    (_match, expression: string) => buildDisplayMathBlock(expression, equationCounter)
  );

  normalized = normalized.replace(
    /\\\(((?:.|\n)*?)\\\)/g,
    (_match, expression: string) => `$${normalizeMathExpression(expression)}$`
  );

  normalized = normalized.replace(
    /(^|[\r\n])([ \t]*)\[\s*([\s\S]*?)\s*\](?=\s*(?:[\r\n]|$))/g,
    (_match, prefix: string, indentation: string, expression: string) => {
      if (!containsLikelyMath(expression)) return _match;
      return `${prefix}${indentation}${buildDisplayMathBlock(
        expression,
        equationCounter
      )}`;
    }
  );

  normalized = normalized.replace(
    /\[\s*([^[\]\r\n]+?)\s*\]/g,
    (match, expression: string) => {
      if (!containsLikelyMath(expression)) return match;
      return `$${normalizeMathExpression(expression)}$`;
    }
  );

  return normalized;
}

function normalizeMathMarkdown(content: string): string {
  const equationCounter = { value: 0 };
  const segments = content.split(FENCED_CODE_BLOCK_REGEX);
  const codeBlocks = content.match(FENCED_CODE_BLOCK_REGEX) ?? [];
  const rebuilt: string[] = [];

  segments.forEach((segment, index) => {
    rebuilt.push(normalizeMathInNonCodeSegment(segment, equationCounter));
    if (index < codeBlocks.length) {
      rebuilt.push(codeBlocks[index]);
    }
  });

  return rebuilt.join("");
}

function inlineVisualizationNote(altText?: string): string {
  return `> Inline visualization${
    altText ? ` "${altText}"` : ""
  } was omitted from the chat body. See the rendered chart in the tool result card.`;
}

function sanitizeMarkdownContent(
  content: string,
  options?: { normalizeMath?: boolean }
): string {
  let sanitized = content;

  sanitized = sanitized.replace(
    DATA_URI_IMAGE_MARKDOWN_REGEX,
    (_match, altText: string) => inlineVisualizationNote(altText)
  );
  sanitized = sanitized.replace(
    INLINE_SVG_REGEX,
    "\n> Inline SVG payload omitted from the chat body. See the rendered chart in the tool result card.\n"
  );
  sanitized = sanitized.replace(
    DATA_URI_REGEX,
    "[inline image payload omitted; see tool visualization]"
  );
  sanitized = sanitized.replace(
    OMITTED_IMAGE_MARKDOWN_REGEX,
    (_match, altText: string) => inlineVisualizationNote(altText)
  );

  return options?.normalizeMath === false
    ? sanitized
    : normalizeMathMarkdown(sanitized);
}

function sanitizeRenderableMarkdown(content: string): string {
  return sanitizeMarkdownContent(content);
}

function sanitizeStreamingMarkdown(content: string): string {
  return sanitizeMarkdownContent(content, { normalizeMath: false });
}

function splitStreamingMarkdownBlocks(content: string): {
  committedBlocks: string[];
  liveTail: string;
} {
  if (!content) {
    return { committedBlocks: [], liveTail: "" };
  }

  const normalizedContent = content.replace(/\r\n/g, "\n");
  const lines = normalizedContent.split(/(?<=\n)/);
  const committedBlocks: string[] = [];
  let currentBlock = "";
  let inFence = false;
  let fenceCharacter = "";
  let fenceLength = 0;

  const commitCurrentBlock = () => {
    if (!currentBlock.trim()) {
      currentBlock = "";
      return;
    }
    committedBlocks.push(currentBlock);
    currentBlock = "";
  };

  const findProgressiveSplitIndex = (block: string): number => {
    if (
      block.length <
      STREAMING_BLOCK_TARGET_LENGTH + STREAMING_MIN_TAIL_LENGTH
    ) {
      return 0;
    }

    const matches = block.matchAll(STREAMING_SENTENCE_BOUNDARY_REGEX);

    for (const match of matches) {
      const boundaryIndex = (match.index ?? 0) + match[0].length;
      const tailAfterBoundary = block.slice(boundaryIndex).trimStart();
      if (
        boundaryIndex >= STREAMING_BLOCK_TARGET_LENGTH &&
        block.length - boundaryIndex >= STREAMING_MIN_TAIL_LENGTH &&
        !STREAMING_UNSAFE_TAIL_START_REGEX.test(tailAfterBoundary)
      ) {
        return boundaryIndex;
      }
    }

    return 0;
  };

  lines.forEach((line, index) => {
    const lineWithoutBreak = line.endsWith("\n") ? line.slice(0, -1) : line;
    const trimmedLine = lineWithoutBreak.trim();
    const fenceMatch = lineWithoutBreak.match(FENCE_DELIMITER_REGEX);
    let closedFenceThisLine = false;

    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (!inFence) {
        inFence = true;
        fenceCharacter = marker[0];
        fenceLength = marker.length;
      } else if (marker[0] === fenceCharacter && marker.length >= fenceLength) {
        inFence = false;
        fenceCharacter = "";
        fenceLength = 0;
        closedFenceThisLine = true;
      }
    }

    currentBlock += line;

    if (inFence) {
      return;
    }

    if (trimmedLine === "") {
      commitCurrentBlock();
      return;
    }

    if (closedFenceThisLine) {
      const nextLine = lines[index + 1];
      if (nextLine !== undefined && nextLine.trim() !== "") {
        commitCurrentBlock();
      }
    }
  });

  if (!inFence) {
    let splitIndex = findProgressiveSplitIndex(currentBlock);

    while (splitIndex > 0) {
      committedBlocks.push(currentBlock.slice(0, splitIndex));
      currentBlock = currentBlock.slice(splitIndex);
      splitIndex = findProgressiveSplitIndex(currentBlock);
    }
  }

  return {
    committedBlocks,
    liveTail: currentBlock,
  };
}

const MarkdownRenderer = React.memo<MarkdownRendererProps>(
  ({ content, className = "", enableMath, variant }) => {
    const isFinalRender = variant === "final";

    return (
      <div className={cn(MARKDOWN_PROSE_CLASS, className)}>
        <ReactMarkdown
          remarkPlugins={
            isFinalRender
              ? enableMath
                ? [remarkGfm, remarkMath]
                : [remarkGfm]
              : [remarkGfm]
          }
          rehypePlugins={
            isFinalRender && enableMath
              ? [[rehypeKatex, { throwOnError: false, strict: "ignore" }]]
              : []
          }
          components={{
            code({
              inline,
              className,
              children,
              ...props
            }: {
              inline?: boolean;
              className?: string;
              children?: React.ReactNode;
            }) {
              const match = /language-(\w+)/.exec(className || "");
              return !inline && match && isFinalRender ? (
                <SyntaxHighlighter
                  style={oneDark}
                  language={match[1]}
                  PreTag="div"
                  className="max-w-full rounded-md text-sm"
                  wrapLines={true}
                  wrapLongLines={true}
                  lineProps={{
                    style: {
                      wordBreak: "break-all",
                      whiteSpace: "pre-wrap",
                      overflowWrap: "break-word",
                    },
                  }}
                  customStyle={{
                    margin: 0,
                    maxWidth: "100%",
                    overflowX: "auto",
                    fontSize: "0.875rem",
                  }}
                >
                  {String(children).replace(/\n$/, "")}
                </SyntaxHighlighter>
              ) : (
                <code
                  className={cn(
                    "bg-surface rounded-sm px-1 py-0.5 font-mono text-[0.9em]",
                    !inline &&
                      "block overflow-x-auto rounded-md px-3 py-2 text-sm leading-6"
                  )}
                  {...props}
                >
                  {children}
                </code>
              );
            },
            pre({ children }: { children?: React.ReactNode }) {
              return (
                <div className="my-4 max-w-full overflow-hidden last:mb-0">
                  {children}
                </div>
              );
            },
            a({
              href,
              children,
            }: {
              href?: string;
              children?: React.ReactNode;
            }) {
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary no-underline hover:underline"
                >
                  {children}
                </a>
              );
            },
            img(props: React.ImgHTMLAttributes<HTMLImageElement>) {
              const src = typeof props.src === "string" ? props.src : undefined;
              const alt = typeof props.alt === "string" ? props.alt : undefined;
              if (!src) return null;
              if (src.startsWith("data:image/")) {
                return (
                  <p className="text-sm italic text-muted-foreground">
                    Inline visualization{alt ? ` "${alt}"` : ""} was omitted
                    from the chat body. See the tool result card for the
                    rendered chart.
                  </p>
                );
              }
              return (
                <img
                  src={src}
                  alt={alt || ""}
                  className="h-auto max-w-full rounded-md border border-border"
                />
              );
            },
            blockquote({ children }: { children?: React.ReactNode }) {
              return (
                <blockquote className="text-primary/50 my-4 border-l-4 border-border pl-4 italic">
                  {children}
                </blockquote>
              );
            },
            ul({ children }: { children?: React.ReactNode }) {
              return (
                <ul className="my-4 pl-6 [&>li:last-child]:mb-0 [&>li]:mb-1">
                  {children}
                </ul>
              );
            },
            ol({ children }: { children?: React.ReactNode }) {
              return (
                <ol className="my-4 pl-6 [&>li:last-child]:mb-0 [&>li]:mb-1">
                  {children}
                </ol>
              );
            },
            table({ children }: { children?: React.ReactNode }) {
              return (
                <div className="my-4 overflow-x-auto">
                  <table className="[&_th]:bg-surface w-full border-collapse [&_td]:border [&_td]:border-border [&_td]:p-2 [&_th]:border [&_th]:border-border [&_th]:p-2 [&_th]:text-left [&_th]:font-semibold">
                    {children}
                  </table>
                </div>
              );
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  }
);

export const MarkdownContent = React.memo<MarkdownContentProps>(
  ({ content, className = "", enableMath = true, isStreaming = false }) => {
    const sanitizedFinalContent = useMemo(
      () =>
        isStreaming
          ? ""
          : enableMath
            ? sanitizeRenderableMarkdown(content)
            : content,
      [content, enableMath, isStreaming]
    );
    const sanitizedStreamingContent = useMemo(
      () => (isStreaming ? sanitizeStreamingMarkdown(content) : ""),
      [content, isStreaming]
    );
    const streamingSegments = useMemo(
      () =>
        isStreaming
          ? splitStreamingMarkdownBlocks(sanitizedStreamingContent)
          : { committedBlocks: [], liveTail: "" },
      [isStreaming, sanitizedStreamingContent]
    );

    if (isStreaming) {
      return (
        <div className="flex min-w-0 flex-col gap-4">
          {streamingSegments.committedBlocks.map((block, index) => (
            <MarkdownRenderer
              key={`stream-block-${index}`}
              content={block}
              className={className}
              enableMath={false}
              variant="streaming"
            />
          ))}
          {streamingSegments.liveTail ? (
            <MarkdownRenderer
              content={streamingSegments.liveTail}
              className={className}
              enableMath={false}
              variant="streaming"
            />
          ) : null}
        </div>
      );
    }

    return (
      <MarkdownRenderer
        content={sanitizedFinalContent}
        className={className}
        enableMath={enableMath}
        variant="final"
      />
    );
  }
);

MarkdownRenderer.displayName = "MarkdownRenderer";
MarkdownContent.displayName = "MarkdownContent";
