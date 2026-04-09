"use client";

import React, {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Message } from "@langchain/langgraph-sdk";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { MarkdownContent } from "@/app/components/MarkdownContent";
import { SubAgentIndicator } from "@/app/components/SubAgentIndicator";
import {
  getToolActivityMeta,
  ToolCallBox,
} from "@/app/components/ToolCallBox";
import type { ConversationDensity } from "@/lib/config";
import type {
  ActionRequest,
  ReviewConfig,
  SubAgent,
  ToolCall,
} from "@/app/types/types";
import {
  extractStringFromMessageContent,
  extractSubAgentContent,
  sanitizeAssistantDisplayText,
} from "@/app/utils/utils";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: Message;
  toolCalls: ToolCall[];
  isLoading?: boolean;
  isStreamingMessage?: boolean;
  actionRequestsMap?: Map<string, ActionRequest>;
  reviewConfigsMap?: Map<string, ReviewConfig>;
  ui?: any[];
  stream?: any;
  onResumeInterrupt?: (value: any) => void;
  graphId?: string;
  smoothStreaming?: boolean;
  conversationDensity?: ConversationDensity;
}

function useStreamingMarkdownValue(
  value: string,
  enabled: boolean,
  intervalMs = 80
): string {
  const [streamingValue, setStreamingValue] = useState(value);
  const lastCommitRef = useRef(0);

  useEffect(() => {
    if (!enabled) {
      setStreamingValue(value);
      lastCommitRef.current = 0;
      return;
    }

    const now = performance.now();
    const elapsed = now - lastCommitRef.current;

    if (elapsed >= intervalMs) {
      setStreamingValue(value);
      lastCommitRef.current = now;
      return;
    }

    const timeout = window.setTimeout(() => {
      setStreamingValue(value);
      lastCommitRef.current = performance.now();
    }, intervalMs - elapsed);

    return () => window.clearTimeout(timeout);
  }, [enabled, intervalMs, value]);

  return streamingValue;
}

export const ChatMessage = React.memo<ChatMessageProps>(
  ({
    message,
    toolCalls,
    isLoading,
    isStreamingMessage = false,
    actionRequestsMap,
    reviewConfigsMap,
    ui,
    stream,
    onResumeInterrupt,
    graphId,
    smoothStreaming = true,
    conversationDensity = "comfortable",
  }) => {
    const isUser = message.type === "human";
    const rawMessageContent = extractStringFromMessageContent(message);
    const messageContent = isUser
      ? rawMessageContent
      : sanitizeAssistantDisplayText(rawMessageContent);
    const isAssistantStreaming = !isUser && isStreamingMessage;
    const deferredMessageContent = useDeferredValue(messageContent);
    const renderMessageContent =
      isStreamingMessage ? messageContent : deferredMessageContent;
    const streamingMarkdownContent = useStreamingMarkdownValue(
      renderMessageContent,
      isAssistantStreaming && smoothStreaming
    );
    const displayMessageContent =
      isAssistantStreaming && smoothStreaming
        ? streamingMarkdownContent
        : renderMessageContent;
    const showStreamingDots = isAssistantStreaming;
    const hasContent = Boolean(messageContent && messageContent.trim() !== "");
    const [copied, setCopied] = useState(false);
    const messageTextClass =
      conversationDensity === "compact" ? "text-sm leading-6" : "text-[15px] leading-7";
    const visibleToolCalls = useMemo(
      () => toolCalls.filter((toolCall: ToolCall) => toolCall.name !== "task"),
      [toolCalls]
    );
    const hasVisibleToolCalls = visibleToolCalls.length > 0;
    const toolNarrationItems = useMemo(
      () =>
        visibleToolCalls.map((toolCall) => {
          const activityMeta = getToolActivityMeta(
            toolCall.name || "unknown",
            (toolCall.args as Record<string, unknown>) || {}
          );

          return {
            id: toolCall.id,
            title: activityMeta.title,
            subtitle: activityMeta.subtitle,
          };
        }),
      [visibleToolCalls]
    );
    const showToolNarration =
      !isUser && !hasContent && hasVisibleToolCalls;

    useEffect(() => {
      if (!copied) return undefined;
      const timeout = window.setTimeout(() => setCopied(false), 1800);
      return () => window.clearTimeout(timeout);
    }, [copied]);

    const handleCopyMessage = useCallback(async () => {
      if (!messageContent.trim()) return;
      try {
        await navigator.clipboard.writeText(messageContent);
        setCopied(true);
      } catch (error) {
        console.error("Failed to copy message content:", error);
        toast.error("Failed to copy the answer.");
      }
    }, [messageContent]);

    const subAgents = useMemo(() => {
      return toolCalls
        .filter((toolCall: ToolCall) => {
          return (
            toolCall.name === "task" &&
            toolCall.args["subagent_type"] &&
            toolCall.args["subagent_type"] !== "" &&
            toolCall.args["subagent_type"] !== null
          );
        })
        .map((toolCall: ToolCall) => {
          const subagentType = (toolCall.args as Record<string, unknown>)[
            "subagent_type"
          ] as string;
          return {
            id: toolCall.id,
            name: toolCall.name,
            subAgentName: subagentType,
            input: toolCall.args,
            output: toolCall.result ? { result: toolCall.result } : undefined,
            status: toolCall.status,
          } as SubAgent;
        });
    }, [toolCalls]);

    const [expandedSubAgents, setExpandedSubAgents] = useState<
      Record<string, boolean>
    >({});

    const isSubAgentExpanded = useCallback(
      (id: string) => expandedSubAgents[id] ?? false,
      [expandedSubAgents]
    );

    const toggleSubAgent = useCallback((id: string) => {
      setExpandedSubAgents((prev) => ({
        ...prev,
        [id]: !prev[id],
      }));
    }, []);

    return (
      <div className={cn("flex w-full", isUser && "justify-end")}>
        <div className={cn("min-w-0", isUser ? "max-w-[78%]" : "w-full")}>
          {hasContent && (
            <div className="flex flex-col gap-2">
              <div
                className={cn(
                  "overflow-hidden break-words",
                  isUser
                    ? "message-enter rounded-[18px] border border-[rgba(24,33,38,0.08)] px-4 py-3 text-foreground"
                    : "message-ai-enter text-foreground"
                )}
                style={
                  isUser
                    ? { backgroundColor: "var(--color-user-message-bg)" }
                    : undefined
                }
              >
                {isUser ? (
                  <p className={cn("m-0 whitespace-pre-wrap break-words", messageTextClass)}>
                    {messageContent}
                  </p>
                ) : (
                  <div className={cn("min-w-0", showStreamingDots && "streaming-response-active")}>
                    <MarkdownContent
                      content={displayMessageContent}
                      className={messageTextClass}
                      isStreaming={isAssistantStreaming}
                    />
                    {showStreamingDots ? (
                      <span
                        className="streaming-dots"
                        aria-hidden="true"
                      >
                        <span className="streaming-dot" />
                        <span className="streaming-dot" />
                        <span className="streaming-dot" />
                      </span>
                    ) : null}
                  </div>
                )}
              </div>
              {!isUser && (
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => void handleCopyMessage()}
                    className="inline-flex items-center gap-1 rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.92)] px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
                    aria-label="Copy answer"
                  >
                    {copied ? (
                      <>
                        <Check size={13} />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy size={13} />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          )}

          {(showToolNarration || hasVisibleToolCalls) && (
            <div
              className={cn(
                "flex flex-col",
                hasContent ? "mt-2" : "mt-0",
                showToolNarration && hasVisibleToolCalls ? "gap-2" : "gap-0"
              )}
            >
              {showToolNarration && (
                <div className="flex flex-col gap-3 rounded-[16px] border border-[rgba(24,33,38,0.06)] bg-[rgba(248,247,244,0.78)] p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                    Working Through This
                  </p>
                  <div className="grid gap-2.5">
                    {toolNarrationItems.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-[12px] border border-[rgba(24,33,38,0.06)] bg-[rgba(255,255,255,0.72)] px-3 py-3"
                      >
                        <p className="text-[13px] font-medium text-foreground">
                          {item.title}
                        </p>
                        <p className="mt-1 text-[13px] leading-6 text-muted-foreground">
                          {item.subtitle}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {hasVisibleToolCalls && (
                <div className="flex flex-col gap-1.5">
                  {visibleToolCalls.map((toolCall: ToolCall, index) => {
                    const toolCallGenUiComponent = ui?.find(
                      (entry) => entry.metadata?.tool_call_id === toolCall.id
                    );
                    const actionRequest = actionRequestsMap?.get(toolCall.name);
                    const reviewConfig = reviewConfigsMap?.get(toolCall.name);

                    return (
                      <ToolCallBox
                        key={toolCall.id}
                        toolCall={toolCall}
                        uiComponent={toolCallGenUiComponent}
                        stream={stream}
                        graphId={graphId}
                        actionRequest={actionRequest}
                        reviewConfig={reviewConfig}
                        onResume={onResumeInterrupt}
                        isLoading={isLoading}
                        entryIndex={index}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {!isUser && subAgents.length > 0 && (
            <div className="mt-3 flex w-full flex-col gap-3">
              {subAgents.map((subAgent) => (
                <div
                  key={subAgent.id}
                  className="flex flex-col gap-2"
                >
                  <SubAgentIndicator
                    subAgent={subAgent}
                    onClick={() => toggleSubAgent(subAgent.id)}
                    isExpanded={isSubAgentExpanded(subAgent.id)}
                  />
                  {isSubAgentExpanded(subAgent.id) && (
                    <div className="rounded-[16px] border border-[rgba(24,33,38,0.08)] bg-white p-4">
                      <h4 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
                        Input
                      </h4>
                      <div className="mb-4">
                        <MarkdownContent
                          content={extractSubAgentContent(subAgent.input)}
                        />
                      </div>
                      {subAgent.output && (
                        <>
                          <h4 className="mb-2 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
                            Output
                          </h4>
                          <MarkdownContent
                            content={extractSubAgentContent(subAgent.output)}
                          />
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }
);

ChatMessage.displayName = "ChatMessage";
