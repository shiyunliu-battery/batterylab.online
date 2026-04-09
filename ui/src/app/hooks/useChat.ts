"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import {
  type Message,
  type Assistant,
  type Checkpoint,
} from "@langchain/langgraph-sdk";
import { v4 as uuidv4 } from "uuid";
import type { UseStreamThread } from "@langchain/langgraph-sdk/react";
import type { TodoItem } from "@/app/types/types";
import { useClient } from "@/providers/ClientProvider";
import { useQueryState } from "nuqs";
import { toast } from "sonner";
import {
  isMissingThreadError,
  MISSING_THREAD_TOAST_MESSAGE,
} from "@/app/lib/threadErrors";
import {
  normalizeChatFiles,
  type ChatFileData,
  type ChatFileRecord,
  type ChatFileUpdate,
} from "@/app/lib/chatFiles";
import { buildThreadMetadata } from "@/app/lib/assistantScope";
import type { LabDefaultsConfig } from "@/lib/config";

export type StateType = {
  messages: Message[];
  todos: TodoItem[];
  files: ChatFileRecord;
  labDefaults?: LabDefaultsConfig;
  email?: {
    id?: string;
    subject?: string;
    page_content?: string;
  };
  ui?: any;
};

export function useChat({
  activeAssistant,
  onHistoryRevalidate,
  thread,
}: {
  activeAssistant: Assistant | null;
  onHistoryRevalidate?: () => void;
  thread?: UseStreamThread<StateType>;
}) {
  const [threadId, setThreadId] = useQueryState("threadId");
  const client = useClient();
  const [streamErrorTick, setStreamErrorTick] = useState(0);
  const [optimisticFiles, setOptimisticFiles] = useState<
    Record<string, ChatFileData> | null
  >(null);

  const handleStreamError = useCallback(
    async (error: unknown) => {
      onHistoryRevalidate?.();

      const message =
        error instanceof Error
          ? error.message
          : typeof error === "string"
          ? error
          : String(error ?? "");

      if (isMissingThreadError(error)) {
        if (threadId) {
          await setThreadId(null);
        }
        toast.error(MISSING_THREAD_TOAST_MESSAGE);
        setStreamErrorTick((current) => current + 1);
        return;
      }

      if (
        message.includes("HTTP 409") ||
        message.includes("in-flight runs") ||
        message.includes("already has a running task")
      ) {
        toast.message(
          "This thread is already running. Please wait for the current response or press Stop before sending again."
        );
      }
      setStreamErrorTick((current) => current + 1);
    },
    [onHistoryRevalidate, setThreadId, threadId]
  );

  const stream = useStream<StateType>({
    assistantId: activeAssistant?.assistant_id || "",
    client: client ?? undefined,
    reconnectOnMount: true,
    threadId: threadId ?? null,
    onThreadId: setThreadId,
    defaultHeaders: { "x-auth-scheme": "langsmith" },
    fetchStateHistory: true,
    // Revalidate thread list when stream finishes, errors, or creates new thread
    onFinish: onHistoryRevalidate,
    onError: handleStreamError,
    onCreated: onHistoryRevalidate,
    experimental_thread: thread,
  });

  const normalizedFiles = useMemo(
    () => normalizeChatFiles(stream.values.files ?? {}),
    [stream.values.files]
  );
  const effectiveFiles = useMemo(() => {
    if (!optimisticFiles) {
      return normalizedFiles;
    }

    return {
      ...normalizedFiles,
      ...optimisticFiles,
    };
  }, [normalizedFiles, optimisticFiles]);
  const latestFilesRef = useRef<ChatFileRecord>(effectiveFiles);

  useEffect(() => {
    latestFilesRef.current = effectiveFiles;
  }, [effectiveFiles, latestFilesRef]);

  useEffect(() => {
    setOptimisticFiles((current) => {
      if (!current) {
        return current;
      }

      const pendingEntries = Object.entries(current).filter(([filePath, fileValue]) => {
        const streamFile = normalizedFiles[filePath];
        return JSON.stringify(streamFile) !== JSON.stringify(fileValue);
      });

      return pendingEntries.length > 0
        ? Object.fromEntries(pendingEntries)
        : null;
    });
  }, [normalizedFiles]);

  useEffect(() => {
    setOptimisticFiles(null);
  }, [threadId]);

  const sendMessage = useCallback(
    (
      content: string,
      statePatch?: Partial<StateType>,
      displayContent?: string
    ) => {
      const normalizedStatePatch = statePatch?.files
        ? {
            ...statePatch,
            files: normalizeChatFiles(statePatch.files),
          }
        : statePatch;
      const newMessage = {
        id: uuidv4(),
        type: "human",
        content,
        metadata:
          typeof displayContent === "string" && displayContent.trim().length > 0
            ? { display_content: displayContent }
            : undefined,
      } as Message;
      stream.submit(
        {
          ...(normalizedStatePatch ?? {}),
          messages: [newMessage],
        },
        {
          optimisticValues: (prev) => ({
            ...(normalizedStatePatch?.files
              ? { files: normalizedStatePatch.files }
              : {}),
            ...(normalizedStatePatch?.todos
              ? { todos: normalizedStatePatch.todos }
              : {}),
            ...(normalizedStatePatch?.labDefaults
              ? { labDefaults: normalizedStatePatch.labDefaults }
              : {}),
            ...(normalizedStatePatch?.ui ? { ui: normalizedStatePatch.ui } : {}),
            messages: [...(prev.messages ?? []), newMessage],
          }),
          config: { ...(activeAssistant?.config ?? {}), recursion_limit: 100 },
          ...(threadId == null
            ? { metadata: buildThreadMetadata(activeAssistant) }
            : {}),
        }
      );
      // Update thread list immediately when sending a message
      onHistoryRevalidate?.();
    },
    [stream, activeAssistant, onHistoryRevalidate, threadId]
  );

  const runSingleStep = useCallback(
    (
      messages: Message[],
      checkpoint?: Checkpoint,
      isRerunningSubagent?: boolean,
      optimisticMessages?: Message[]
    ) => {
      if (checkpoint) {
        stream.submit(undefined, {
          ...(optimisticMessages
            ? { optimisticValues: { messages: optimisticMessages } }
            : {}),
          config: activeAssistant?.config,
          checkpoint: checkpoint,
          ...(isRerunningSubagent
            ? { interruptAfter: ["tools"] }
            : { interruptBefore: ["tools"] }),
        });
      } else {
        stream.submit(
          { messages },
          { config: activeAssistant?.config, interruptBefore: ["tools"] }
        );
      }
    },
    [stream, activeAssistant?.config]
  );

  const setFiles = useCallback(
    async (nextFilesOrUpdater: ChatFileUpdate) => {
      if (!threadId) return;
      const previousFiles = latestFilesRef.current;
      const nextFiles =
        typeof nextFilesOrUpdater === "function"
          ? nextFilesOrUpdater(previousFiles)
          : nextFilesOrUpdater;
      const normalized = normalizeChatFiles(nextFiles);
      latestFilesRef.current = normalized;
      setOptimisticFiles(normalized);
      try {
        await client.threads.updateState(threadId, {
          values: {
            files: normalized,
          } as Partial<StateType>,
        });
        onHistoryRevalidate?.();
      } catch (error) {
        latestFilesRef.current = previousFiles;
        setOptimisticFiles(previousFiles as Record<string, ChatFileData>);
        toast.error("Failed to save thread files. Please try again.");
        throw error;
      }
    },
    [client, onHistoryRevalidate, threadId]
  );

  const continueStream = useCallback(
    (hasTaskToolCall?: boolean) => {
      stream.submit(undefined, {
        config: {
          ...(activeAssistant?.config || {}),
          recursion_limit: 100,
        },
        ...(hasTaskToolCall
          ? { interruptAfter: ["tools"] }
          : { interruptBefore: ["tools"] }),
      });
      // Update thread list when continuing stream
      onHistoryRevalidate?.();
    },
    [stream, activeAssistant?.config, onHistoryRevalidate]
  );

  const markCurrentThreadAsResolved = useCallback(() => {
    stream.submit(null, { command: { goto: "__end__", update: null } });
    // Update thread list when marking thread as resolved
    onHistoryRevalidate?.();
  }, [stream, onHistoryRevalidate]);

  const resumeInterrupt = useCallback(
    (value: any) => {
      stream.submit(null, { command: { resume: value } });
      // Update thread list when resuming from interrupt
      onHistoryRevalidate?.();
    },
    [stream, onHistoryRevalidate]
  );

  const stopStream = useCallback(() => {
    stream.stop();
  }, [stream]);

  return {
    stream,
    todos: stream.values.todos ?? [],
    files: effectiveFiles,
    labDefaults: stream.values.labDefaults,
    email: stream.values.email,
    ui: stream.values.ui,
    setFiles,
    messages: stream.messages,
    isLoading: stream.isLoading,
    isThreadLoading: stream.isThreadLoading,
    interrupt: stream.interrupt,
    streamErrorTick,
    getMessagesMetadata: stream.getMessagesMetadata,
    sendMessage,
    runSingleStep,
    continueStream,
    stopStream,
    markCurrentThreadAsResolved,
    resumeInterrupt,
  };
}
