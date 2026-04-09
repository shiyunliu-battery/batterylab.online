"use client";

import React, {
  Suspense,
  useCallback,
  useEffect,
  useState,
} from "react";
import { useQueryState } from "nuqs";
import { Assistant } from "@langchain/langgraph-sdk";
import { Loader2, PanelLeftOpen } from "lucide-react";
import { toast } from "sonner";
import { ConfigDialog } from "@/app/components/ConfigDialog";
import { NotebookWorkspace } from "@/app/components/NotebookWorkspace";
import {
  isMissingThreadError,
  MISSING_THREAD_TOAST_MESSAGE,
} from "@/app/lib/threadErrors";
import {
  getConfig,
  getInitialConfig,
  saveConfig,
  StandaloneConfig,
} from "@/lib/config";
import {
  doesThreadMatchAssistantScope,
  isAssistantUuid,
} from "@/app/lib/assistantScope";
import { ClientProvider, useClient } from "@/providers/ClientProvider";
import { ChatProvider } from "@/providers/ChatProvider";

interface HomePageInnerProps {
  config: StandaloneConfig;
  configDialogOpen: boolean;
  setConfigDialogOpen: (open: boolean) => void;
  handleSaveConfig: (config: StandaloneConfig) => void;
}

const THREAD_VALIDATION_REQUESTS = new Map<string, Promise<void>>();
const THREAD_SCOPE_MISMATCH_TOAST_MESSAGE =
  "This thread belongs to a different assistant configuration. Switched back to a new chat.";

function HomePageInner({
  config,
  configDialogOpen,
  setConfigDialogOpen,
  handleSaveConfig,
}: HomePageInnerProps) {
  const client = useClient();
  const [threadId, setThreadId] = useQueryState("threadId");
  const [sidebar, setSidebar] = useQueryState("sidebar");
  const [assistant, setAssistant] = useState<Assistant | null>(null);
  const [mutateThreads, setMutateThreads] = useState<(() => void) | null>(null);
  const [interruptCount, setInterruptCount] = useState(0);
  const [validatedThreadId, setValidatedThreadId] = useState<string | null>(
    () => threadId ?? null
  );
  const [isValidatingThread, setIsValidatingThread] = useState(
    () => threadId != null
  );

  const fetchAssistant = useCallback(async () => {
    const configuredAssistantId = config.assistantId.trim();
    const syntheticAssistant: Assistant = {
      assistant_id: configuredAssistantId,
      graph_id: configuredAssistantId,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      config: {},
      metadata: {},
      version: 1,
      name: configuredAssistantId,
      context: {},
    };

    if (!configuredAssistantId) {
      setAssistant(null);
      return;
    }

    if (isAssistantUuid(configuredAssistantId)) {
      try {
        const data = await client.assistants.get(configuredAssistantId);
        setAssistant(data);
        return;
      } catch (error) {
        console.error("Failed to fetch configured assistant:", error);
        setAssistant(syntheticAssistant);
        return;
      }
    }

    try {
      const assistants = await client.assistants.search({
        graphId: configuredAssistantId,
        limit: 100,
      });
      const defaultAssistant = assistants.find(
        (candidate) => candidate.metadata?.["created_by"] === "system"
      ) ?? assistants[0];
      if (!defaultAssistant) {
        throw new Error("No assistant found for configured graph id");
      }
      setAssistant(defaultAssistant);
      return;
    } catch (error) {
      console.error("Failed to resolve assistant from configured graph id:", error);
      setAssistant(syntheticAssistant);
    }
  }, [client, config.assistantId]);

  useEffect(() => {
    fetchAssistant();
  }, [fetchAssistant]);

  useEffect(() => {
    let cancelled = false;

    if (!threadId) {
      setValidatedThreadId(null);
      setIsValidatingThread(false);
      return;
    }

    setIsValidatingThread(true);
    setValidatedThreadId((current) => (current === threadId ? current : null));

    const validationKey = `${config.assistantId}::${threadId}`;
    let validationRequest = THREAD_VALIDATION_REQUESTS.get(validationKey);

    if (!validationRequest) {
      validationRequest = client.threads.get(threadId).then((thread) => {
        if (!doesThreadMatchAssistantScope(thread, config.assistantId)) {
          throw new Error(THREAD_SCOPE_MISMATCH_TOAST_MESSAGE);
        }
      });
      THREAD_VALIDATION_REQUESTS.set(validationKey, validationRequest);
      void validationRequest
        .catch(() => undefined)
        .finally(() => {
          if (THREAD_VALIDATION_REQUESTS.get(validationKey) === validationRequest) {
            THREAD_VALIDATION_REQUESTS.delete(validationKey);
          }
        });
    }

    const validateThread = async () => {
      try {
        await validationRequest;
        if (cancelled) {
          return;
        }

        setValidatedThreadId(threadId);
        setIsValidatingThread(false);
      } catch (error) {
        if (cancelled) {
          return;
        }

        if (isMissingThreadError(error)) {
          toast.error(MISSING_THREAD_TOAST_MESSAGE);
          await setThreadId(null);
          return;
        }

        if (
          error instanceof Error &&
          error.message === THREAD_SCOPE_MISMATCH_TOAST_MESSAGE
        ) {
          toast.error(THREAD_SCOPE_MISMATCH_TOAST_MESSAGE);
          setValidatedThreadId(null);
          setIsValidatingThread(false);
          await setThreadId(null);
          return;
        }

        console.error("Failed to validate thread:", error);
        setValidatedThreadId(threadId);
        setIsValidatingThread(false);
      }
    };

    void validateThread();

    return () => {
      cancelled = true;
    };
  }, [client, config.assistantId, setThreadId, threadId]);

  const isValidatingSelectedThread =
    threadId != null && (isValidatingThread || validatedThreadId !== threadId);
  const sourcesPanelOpen = sidebar !== "0";

  return (
    <>
      <ConfigDialog
        open={configDialogOpen}
        onOpenChange={setConfigDialogOpen}
        onSave={handleSaveConfig}
        initialConfig={config}
      />
      <div className="min-h-screen p-4">
        <div className="app-shell flex h-[calc(100vh-2rem)] flex-col overflow-hidden rounded-[20px]">
          <header className="flex h-12 items-center justify-between border-b border-[rgba(24,33,38,0.08)] px-3 sm:px-4">
            <div className="flex items-center gap-2">
              {!sourcesPanelOpen && (
                <button
                  type="button"
                  title="Open history panel"
                  onClick={() => setSidebar("1")}
                  className="relative flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-[rgba(24,33,38,0.06)] hover:text-foreground lg:hidden"
                  aria-label="Open history panel"
                >
                  <PanelLeftOpen className="h-4 w-4" />
                  {interruptCount > 0 && (
                    <span className="absolute -right-1 -top-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[9px] text-destructive-foreground">
                      {interruptCount}
                    </span>
                  )}
                </button>
              )}
              <div className="min-w-0">
                <h1 className="text-[14px] font-semibold tracking-[-0.01em] text-foreground">
                  Battery Lab Assistant
                </h1>
              </div>
            </div>

          </header>

          <div className="relative min-h-0 flex-1 overflow-hidden bg-[rgba(255,255,255,0.4)]">
          <div className="flex h-full min-h-0 flex-col">
              <ChatProvider
                key={assistant?.assistant_id ?? "pending"}
                activeAssistant={assistant}
                onHistoryRevalidate={() => mutateThreads?.()}
              >
                <NotebookWorkspace
                  assistant={assistant}
                  assistantId={config.assistantId}
                  labDefaults={config.labDefaults}
                  uiPreferences={config.uiPreferences}
                  sourcesPanelOpen={sourcesPanelOpen}
                  onOpenSources={() => setSidebar("1")}
                  onCloseSources={() => setSidebar("0")}
                  onNewThread={async () => {
                    await setThreadId(null);
                  }}
                  onThreadSelect={async (id) => {
                    await setThreadId(id);
                  }}
                  onOpenSettings={() => setConfigDialogOpen(true)}
                  onMutateReady={(fn) => setMutateThreads(() => fn)}
                  onInterruptCountChange={setInterruptCount}
                />
              </ChatProvider>
            </div>
            {isValidatingSelectedThread ? (
              <div className="pointer-events-none absolute inset-x-0 top-3 z-20 flex justify-center">
                <div className="inline-flex items-center gap-2 rounded-full border border-[rgba(24,33,38,0.08)] bg-[rgba(255,255,255,0.92)] px-3 py-1 text-xs text-muted-foreground shadow-sm">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Loading thread…</span>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </>
  );
}

function HomePageContent() {
  const [config, setConfig] = useState<StandaloneConfig>(() =>
    getInitialConfig()
  );
  const [configDialogOpen, setConfigDialogOpen] = useState(false);

  useEffect(() => {
    setConfig(getConfig() ?? getInitialConfig());
  }, []);

  const handleSaveConfig = useCallback((newConfig: StandaloneConfig) => {
    saveConfig(newConfig);
    setConfig(newConfig);
  }, []);

  return (
    <ClientProvider deploymentUrl={config.deploymentUrl}>
      <HomePageInner
        config={config}
        configDialogOpen={configDialogOpen}
        setConfigDialogOpen={setConfigDialogOpen}
        handleSaveConfig={handleSaveConfig}
      />
    </ClientProvider>
  );
}

export default function HomePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
          Loading...
        </div>
      }
    >
      <HomePageContent />
    </Suspense>
  );
}
