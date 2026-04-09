"use client";

import React from "react";
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export type ToolExecutionStepStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed";

export interface ToolExecutionStep {
  id: string;
  label: string;
  description?: string;
  status: ToolExecutionStepStatus;
}

interface ToolExecutionProgressProps {
  title: string;
  description: string;
  steps: ToolExecutionStep[];
  elapsedMs?: number;
}

function formatElapsed(elapsedMs?: number): string | null {
  if (!elapsedMs || elapsedMs < 0) return null;
  if (elapsedMs < 60000) {
    return `${(elapsedMs / 1000).toFixed(1)}s`;
  }
  const totalSeconds = Math.floor(elapsedMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

function getStepIcon(status: ToolExecutionStepStatus) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />;
    case "in_progress":
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-600" />;
    case "failed":
      return <XCircle className="h-3.5 w-3.5 text-rose-600" />;
    default:
      return <Circle className="h-3.5 w-3.5 text-muted-foreground" />;
  }
}

export function ToolExecutionProgress({
  title,
  description,
  steps,
  elapsedMs,
}: ToolExecutionProgressProps) {
  const completedCount = steps.filter((step) => step.status === "completed").length;
  const activeCount = steps.filter((step) => step.status === "in_progress").length;
  const progressPercent =
    steps.length > 0 ? ((completedCount + activeCount * 0.5) / steps.length) * 100 : 0;
  const elapsedLabel = formatElapsed(elapsedMs);

  return (
    <div className="mt-3 rounded-[14px] border border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.8)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-medium text-foreground">{title}</div>
          <p className="mt-0.5 text-[11px] leading-5 text-muted-foreground">
            {description}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-2 py-0.5 text-[10px] text-muted-foreground">
            {completedCount}/{steps.length}
          </span>
          {elapsedLabel && (
            <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-2 py-0.5 text-[10px] text-muted-foreground">
              {elapsedLabel}
            </span>
          )}
        </div>
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[rgba(24,33,38,0.08)]">
        <div
          className="h-full rounded-full bg-[hsl(var(--primary))] transition-[width] duration-300"
          style={{ width: `${Math.min(progressPercent, 100)}%` }}
        />
      </div>

      <ol className="mt-3 space-y-2">
        {steps.map((step) => (
          <li
            key={step.id}
            className={cn(
              "rounded-[12px] border px-2.5 py-2",
              step.status === "completed" &&
                "border-[rgba(16,185,129,0.15)] bg-[rgba(16,185,129,0.05)]",
              step.status === "in_progress" &&
                "border-[rgba(201,139,51,0.18)] bg-[rgba(201,139,51,0.08)]",
              step.status === "failed" &&
                "border-[rgba(239,68,68,0.18)] bg-[rgba(239,68,68,0.06)]",
              step.status === "pending" &&
                "border-[rgba(24,33,38,0.08)] bg-white"
            )}
          >
            <div className="flex items-start gap-2">
              <div className="mt-0.5">{getStepIcon(step.status)}</div>
              <div className="min-w-0">
                <div className="text-xs font-medium text-foreground">
                  {step.label}
                </div>
                {step.description && (
                  <p className="mt-0.5 text-[11px] leading-5 text-muted-foreground">
                    {step.description}
                  </p>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
