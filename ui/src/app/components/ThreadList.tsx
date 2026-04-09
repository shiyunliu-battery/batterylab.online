"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { format } from "date-fns";
import {
  AlertTriangle,
  ChevronDown,
  FlaskConical,
  Loader2,
  MessageSquare,
  PanelLeftClose,
  Search,
  Settings,
  SquarePen,
} from "lucide-react";
import { useQueryState } from "nuqs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DEFAULT_UI_PREFERENCES,
  type UiPreferencesConfig,
} from "@/lib/config";
import { cn } from "@/lib/utils";
import { useThreads } from "@/app/hooks/useThreads";
import type { ThreadItem } from "@/app/hooks/useThreads";

type StatusFilter = "all" | "interrupted" | "busy";

const GROUP_LABELS = {
  interrupted: "Needs attention",
  today: "Today",
  yesterday: "Yesterday",
  week: "This week",
  older: "Older",
} as const;

const STATUS_DOT: Record<ThreadItem["status"], string | null> = {
  idle: null,
  busy: "bg-sky-400",
  interrupted: "bg-amber-400",
  error: "bg-rose-500",
};

function formatTime(date: Date, now = new Date()): string {
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  if (days === 0) return format(date, "HH:mm");
  if (days === 1) return "Yest";
  if (days < 7) return format(date, "EEE");
  return format(date, "MM/dd");
}

function LoadingState() {
  return (
    <div className="space-y-1 px-2 py-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-9 w-full rounded-lg" />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      <MessageSquare className="mb-3 h-8 w-8 text-muted-foreground/30" />
      <p className="text-[12px] text-muted-foreground">No sessions yet</p>
      <p className="mt-1 text-[11px] text-muted-foreground/60">Start a new planning session above</p>
    </div>
  );
}

interface ThreadListProps {
  assistantId: string;
  uiPreferences?: UiPreferencesConfig;
  onNewThread: () => void;
  onThreadSelect: (id: string) => void;
  onOpenSettings: () => void;
  onMutateReady?: (mutate: () => void) => void;
  onClose?: () => void;
  onInterruptCountChange?: (count: number) => void;
}

export function ThreadList({
  assistantId,
  uiPreferences,
  onNewThread,
  onThreadSelect,
  onOpenSettings,
  onMutateReady,
  onClose,
  onInterruptCountChange,
}: ThreadListProps) {
  const [currentThreadId] = useQueryState("threadId");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const effectiveUiPreferences = useMemo(
    () => ({ ...DEFAULT_UI_PREFERENCES, ...uiPreferences }),
    [uiPreferences]
  );

  const threads = useThreads({
    assistantId,
    status: statusFilter === "all" ? undefined : statusFilter,
    limit: 25,
  });

  const flattened = useMemo(() => threads.data?.flat() ?? [], [threads.data]);
  const isLoadingMore = threads.size > 0 && threads.data?.[threads.size - 1] == null;
  const isEmpty = threads.data?.at(0)?.length === 0;
  const isReachingEnd = isEmpty || (threads.data?.at(-1)?.length ?? 0) < 25;

  // Client-side search filter applied on top of server-side status filter
  const filteredFlattened = useMemo(() => {
    if (!searchQuery.trim()) return flattened;
    const q = searchQuery.toLowerCase();
    return flattened.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        (t.description ?? "").toLowerCase().includes(q)
    );
  }, [flattened, searchQuery]);

  const grouped = useMemo(() => {
    const now = new Date();
    const groups: Record<keyof typeof GROUP_LABELS, ThreadItem[]> = {
      interrupted: [],
      today: [],
      yesterday: [],
      week: [],
      older: [],
    };

    filteredFlattened.forEach((thread) => {
      if (thread.status === "interrupted") {
        groups.interrupted.push(thread);
        return;
      }
      const diff = now.getTime() - thread.updatedAt.getTime();
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      if (days === 0) groups.today.push(thread);
      else if (days === 1) groups.yesterday.push(thread);
      else if (days < 7) groups.week.push(thread);
      else groups.older.push(thread);
    });

    return groups;
  }, [filteredFlattened]);

  const interruptedCount = useMemo(
    () => flattened.filter((t) => t.status === "interrupted").length,
    [flattened]
  );

  const searchResultCount = searchQuery.trim() ? filteredFlattened.length : null;

  const onMutateReadyRef = useRef(onMutateReady);
  const mutateRef = useRef(threads.mutate);

  useEffect(() => { onMutateReadyRef.current = onMutateReady; }, [onMutateReady]);
  useEffect(() => { mutateRef.current = threads.mutate; }, [threads.mutate]);

  const mutateFn = useCallback(() => { mutateRef.current(); }, []);
  useEffect(() => { onMutateReadyRef.current?.(mutateFn); }, [mutateFn]);
  useEffect(() => { onInterruptCountChange?.(interruptedCount); }, [interruptedCount, onInterruptCountChange]);

  const compact = effectiveUiPreferences.conversationDensity === "compact";
  const showThreadSummary = effectiveUiPreferences.showThreadSummary;

  return (
    <TooltipProvider delayDuration={300}>
      <div className="absolute inset-0 flex flex-col">

        {/* ── Top bar ──────────────────────────────── */}
        <div className="flex h-14 shrink-0 items-center justify-between px-3">
          {/* Logo + name */}
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[rgba(24,87,93,0.1)]">
              <FlaskConical className="h-4 w-4 text-[#24575d]" />
            </span>
            <div className="min-w-0">
              <span className="block truncate text-[13px] font-semibold tracking-[-0.01em] text-foreground">
                Battery Lab
              </span>
              <span className="block truncate text-[10.5px] uppercase tracking-[0.12em] text-muted-foreground/70">
                Session history
              </span>
            </div>
          </div>

          {/* Collapse button */}
          {onClose && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={onClose}
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-[rgba(24,33,38,0.06)] hover:text-foreground"
                  aria-label="Collapse sidebar"
                >
                  <PanelLeftClose className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">Collapse sidebar</TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* ── New session CTA ──────────────────────── */}
        <div className="shrink-0 px-3 pb-2">
          <button
            type="button"
            onClick={onNewThread}
            className="flex w-full items-center gap-2 rounded-xl border border-[rgba(24,33,38,0.1)] bg-[rgba(24,87,93,0.06)] px-3 py-2.5 text-[13px] font-medium text-[#24575d] transition-colors hover:bg-[rgba(24,87,93,0.1)]"
          >
            <SquarePen className="h-3.5 w-3.5 shrink-0" />
            New session
          </button>
        </div>

        {/* ── Search input ─────────────────────────── */}
        <div className="shrink-0 px-3 pb-2">
          <div className="flex items-center gap-2 rounded-lg border border-[rgba(24,33,38,0.09)] bg-[rgba(255,255,255,0.6)] px-2.5 py-1.5">
            <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search sessions…"
              className="min-w-0 flex-1 bg-transparent text-[12.5px] text-foreground placeholder:text-muted-foreground/50 focus:outline-none"
              aria-label="Search conversation history"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="shrink-0 text-[10px] text-muted-foreground/60 hover:text-muted-foreground"
                aria-label="Clear search"
              >
                ✕
              </button>
            )}
          </div>
          {searchResultCount !== null && (
            <p className="mt-1 px-0.5 text-[11px] text-muted-foreground/60">
              {searchResultCount} result{searchResultCount !== 1 ? "s" : ""}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1.5 px-3 pb-2">
          {(["all", "interrupted", "busy"] as StatusFilter[]).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setStatusFilter(f)}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
                statusFilter === f
                  ? "border-[rgba(24,87,93,0.3)] bg-[rgba(24,87,93,0.1)] text-[#24575d]"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {f === "interrupted" && interruptedCount > 0 && (
                <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-500 text-[9px] font-semibold text-white">
                  {interruptedCount}
                </span>
              )}
              {f === "all" ? "All" : f === "busy" ? "Running" : "Attention"}
            </button>
          ))}
        </div>

        {/* ── Thread list ──────────────────────────── */}
        <ScrollArea className="h-0 flex-1">
          {threads.error && (
            <div className="px-3 py-4 text-center">
              <p className="text-[12px] text-rose-600">Failed to load history</p>
            </div>
          )}
          {!threads.error && !threads.data && threads.isLoading && <LoadingState />}
          {!threads.error && !threads.isLoading && isEmpty && <EmptyState />}

          {!threads.error && !isEmpty && (
            <div className="px-2 pb-2">
              {(Object.keys(GROUP_LABELS) as Array<keyof typeof GROUP_LABELS>).map((group) => {
                const groupThreads = grouped[group];
                if (!groupThreads || groupThreads.length === 0) return null;

                return (
                  <div key={group} className="mb-3">
                    <div className="flex items-center gap-1.5 px-2 pb-1 pt-2">
                      {group === "interrupted" && (
                        <AlertTriangle className="h-3 w-3 text-amber-500" />
                      )}
                      <span className="text-[10.5px] font-semibold uppercase tracking-[0.09em] text-muted-foreground/70">
                        {GROUP_LABELS[group]}
                      </span>
                    </div>

                    <div className="space-y-0.5">
                      {groupThreads.map((thread) => {
                        const dot = STATUS_DOT[thread.status];
                        const isActive = currentThreadId === thread.id;

                        return (
                          <button
                            key={thread.id}
                            type="button"
                            onClick={() => onThreadSelect(thread.id)}
                            aria-current={isActive}
                            className={cn(
                              "group relative w-full rounded-lg px-2.5 text-left transition-colors",
                              compact ? "py-1.5" : "py-2",
                              isActive
                                ? "bg-[rgba(24,33,38,0.07)]"
                                : "hover:bg-[rgba(24,33,38,0.04)]"
                            )}
                          >
                            {/* Active indicator bar */}
                            {isActive && (
                              <span className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-[#24575d]" />
                            )}

                            <div className="flex items-center justify-between gap-2">
                              <span
                                className={cn(
                                  "flex-1 truncate font-medium text-foreground",
                                  compact ? "text-[12px] leading-5" : "text-[12.5px] leading-5"
                                )}
                              >
                                {thread.title}
                              </span>

                              <div className="flex shrink-0 items-center gap-1.5">
                                {dot && (
                                  <span className={cn("h-2 w-2 rounded-full", dot)} />
                                )}
                                <span className="text-[10px] font-mono tabular-nums text-muted-foreground/60">
                                  {formatTime(thread.updatedAt)}
                                </span>
                              </div>
                            </div>

                            {showThreadSummary && thread.description && (
                              <p
                                className={cn(
                                  "mt-0.5 truncate text-muted-foreground",
                                  compact ? "text-[11px] leading-4" : "text-[11.5px] leading-4"
                                )}
                              >
                                {thread.description}
                              </p>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}

              {!isReachingEnd && (
                <button
                  type="button"
                  onClick={() => threads.setSize(threads.size + 1)}
                  disabled={isLoadingMore}
                  className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-lg py-2 text-[11.5px] text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                >
                  {isLoadingMore ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <>
                      <ChevronDown className="h-3.5 w-3.5" />
                      Load more
                    </>
                  )}
                </button>
              )}
            </div>
          )}
        </ScrollArea>

        {/* ── Bottom icon rail ──────────────────────── */}
        <div className="shrink-0 border-t border-[rgba(24,33,38,0.07)] px-2 py-2">
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={onOpenSettings}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-[rgba(24,33,38,0.06)] hover:text-foreground"
                  aria-label="Settings"
                >
                  <Settings className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top">Settings & Lab config</TooltipContent>
            </Tooltip>
          </div>
        </div>

      </div>
    </TooltipProvider>
  );
}
