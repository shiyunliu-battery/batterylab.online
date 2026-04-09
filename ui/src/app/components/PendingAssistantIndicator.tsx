"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type PendingAssistantPhase = "preparing" | "awaiting-stream" | "streaming";

interface PendingAssistantIndicatorProps {
  phase: PendingAssistantPhase;
  requestKey?: string;
}

const THINKING_STAGES = [
  {
    id: "read",
    shortLabel: "Read",
    label: "Reading your request",
    description: "Checking the latest prompt, thread context, and any files already attached.",
  },
  {
    id: "plan",
    shortLabel: "Plan",
    label: "Planning the next step",
    description: "Choosing whether to answer directly or route through tools and saved workflow context.",
  },
  {
    id: "reply",
    shortLabel: "Reply",
    label: "Preparing the first reply",
    description: "The assistant will start streaming as soon as the first useful chunk is ready.",
  },
] as const;

function formatElapsed(elapsedMs: number): string {
  if (elapsedMs < 1000) {
    return "<1s";
  }
  if (elapsedMs < 60000) {
    return `${(elapsedMs / 1000).toFixed(1)}s`;
  }
  const totalSeconds = Math.floor(elapsedMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

function getActiveStageIndex(
  phase: PendingAssistantPhase,
  elapsedMs: number
): number {
  if (phase === "preparing") {
    return 0;
  }
  if (phase === "awaiting-stream") {
    return Math.min(1, Math.floor(elapsedMs / 1200));
  }
  return Math.min(2, 1 + Math.floor(elapsedMs / 1200));
}

export function PendingAssistantIndicator({
  phase,
  requestKey,
}: PendingAssistantIndicatorProps) {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    setElapsedMs(0);
    const startedAt = Date.now();
    const interval = window.setInterval(() => {
      setElapsedMs(Date.now() - startedAt);
    }, 250);

    return () => window.clearInterval(interval);
  }, [requestKey]);

  const activeStageIndex = useMemo(
    () => getActiveStageIndex(phase, elapsedMs),
    [elapsedMs, phase]
  );
  const activeStage = THINKING_STAGES[activeStageIndex];
  const elapsedLabel = useMemo(() => formatElapsed(elapsedMs), [elapsedMs]);

  return (
    <div className="rounded-[18px] border border-[rgba(36,87,93,0.12)] bg-[linear-gradient(135deg,rgba(232,242,239,0.82),rgba(255,255,255,0.98))] px-4 py-3 shadow-[0_10px_28px_rgba(24,33,38,0.04)]">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/80 bg-white/85 text-[hsl(var(--primary))] shadow-sm">
          <Loader2 size={16} className="animate-spin" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-[rgba(24,33,38,0.58)]">
              Assistant Working
            </span>
            <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white/80 px-2 py-0.5 text-[10px] text-muted-foreground">
              {elapsedLabel}
            </span>
          </div>

          <p className="mt-1 text-sm font-medium text-foreground">
            {activeStage.label}
          </p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            {activeStage.description}
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            {THINKING_STAGES.map((stage, index) => {
              const status =
                index < activeStageIndex
                  ? "completed"
                  : index === activeStageIndex
                    ? "active"
                    : "pending";

              return (
                <div
                  key={stage.id}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] transition-colors",
                    status === "completed" &&
                      "border-[rgba(36,87,93,0.16)] bg-white/90 text-foreground",
                    status === "active" &&
                      "border-[rgba(36,87,93,0.28)] bg-[rgba(36,87,93,0.1)] text-foreground",
                    status === "pending" &&
                      "border-[rgba(24,33,38,0.08)] bg-[rgba(255,255,255,0.55)] text-muted-foreground"
                  )}
                >
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      status === "completed" && "bg-[hsl(var(--primary))]",
                      status === "active" && "bg-amber-500",
                      status === "pending" && "bg-[rgba(24,33,38,0.2)]"
                    )}
                  />
                  <span>{stage.shortLabel}</span>
                </div>
              );
            })}
          </div>

          <div className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--primary))] animate-pulse"
                style={{
                  animationDelay: `${dot * 180}ms`,
                  animationDuration: "1.2s",
                }}
              />
            ))}
            <span>
              {phase === "streaming"
                ? "Starting the visible response."
                : "This placeholder disappears as soon as the first response content arrives."}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
