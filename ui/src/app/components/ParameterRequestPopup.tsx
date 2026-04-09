"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  ParameterRequestPayload,
  ParameterRequestQuestion,
} from "@/app/types/types";
import { humanizeInternalIdentifier } from "@/app/utils/utils";
import { cn } from "@/lib/utils";

interface ParameterRequestPopupProps {
  instanceId: string;
  request: ParameterRequestPayload;
  onDismiss: (instanceId: string) => void;
  onComplete: (
    instanceId: string,
    requestId: string,
    answers: Record<string, unknown>,
    source: "interrupt" | "tool_result"
  ) => void;
  source: "interrupt" | "tool_result";
  isLoading?: boolean;
}

function toDisplayValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function normalizeAnswer(
  question: ParameterRequestQuestion,
  value: string
): unknown {
  const trimmed = value.trim();
  if (
    question.input_kind === "number" &&
    trimmed.length > 0 &&
    Number.isFinite(Number(trimmed))
  ) {
    return Number(trimmed);
  }
  return trimmed;
}

function formatTagLabel(value: string | undefined): string {
  if (!value) {
    return "";
  }
  return humanizeInternalIdentifier(value);
}

export function ParameterRequestPopup({
  instanceId,
  request,
  onDismiss,
  onComplete,
  source,
  isLoading,
}: ParameterRequestPopupProps) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const currentQuestion = request.questions[index];

  useEffect(() => {
    setIndex(0);
    setAnswers({});
  }, [request.request_id]);

  const currentValue = useMemo(() => {
    if (!currentQuestion) return "";
    if (currentQuestion.key in answers) {
      return toDisplayValue(answers[currentQuestion.key]);
    }
    if (currentQuestion.current_value !== undefined) {
      return toDisplayValue(currentQuestion.current_value);
    }
    if (currentQuestion.can_use_default) {
      return toDisplayValue(currentQuestion.recommended_value);
    }
    return "";
  }, [answers, currentQuestion]);

  const [draftValue, setDraftValue] = useState(currentValue);

  useEffect(() => {
    setDraftValue(currentValue);
  }, [currentValue, currentQuestion?.key]);

  if (!currentQuestion) {
    return null;
  }

  const total = request.questions.length;
  const progressLabel = `${index + 1} / ${total}`;

  const commitAnswer = (value: unknown) => {
    const nextAnswers = {
      ...answers,
      [currentQuestion.key]: value,
    };
    setAnswers(nextAnswers);

    if (index >= total - 1) {
      onComplete(instanceId, request.request_id, nextAnswers, source);
      return;
    }

    setIndex((current) => current + 1);
  };

  const handleNext = () => {
    const normalized = normalizeAnswer(currentQuestion, draftValue);
    if (
      typeof normalized === "string" &&
      normalized.trim().length === 0 &&
      currentQuestion.can_use_default &&
      currentQuestion.recommended_value !== undefined
    ) {
      commitAnswer(currentQuestion.recommended_value);
      return;
    }
    if (typeof normalized === "string" && normalized.trim().length === 0) {
      return;
    }
    commitAnswer(normalized);
  };

  const renderInput = () => {
    if (currentQuestion.input_kind === "select" && currentQuestion.options?.length) {
      return (
        <Select
          value={draftValue}
          onValueChange={(value) => setDraftValue(value)}
          disabled={isLoading}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select a value" />
          </SelectTrigger>
          <SelectContent>
            {currentQuestion.options.map((option) => (
              <SelectItem
                key={option}
                value={option}
              >
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    }

    if (currentQuestion.input_kind === "textarea") {
      return (
        <Textarea
          value={draftValue}
          onChange={(event) => setDraftValue(event.target.value)}
          rows={3}
          disabled={isLoading}
          placeholder={currentQuestion.label}
        />
      );
    }

    return (
      <Input
        type={currentQuestion.input_kind === "number" ? "number" : "text"}
        value={draftValue}
        onChange={(event) => setDraftValue(event.target.value)}
        disabled={isLoading}
        placeholder={currentQuestion.label}
      />
    );
  };

  return (
    <div className="rounded-[18px] border border-[rgba(24,33,38,0.12)] bg-[rgba(255,250,242,0.98)] p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-800">
            <AlertCircle size={14} />
            <span>Parameter Check</span>
          </div>
          <p className="mt-1 text-sm font-medium text-foreground">
            {currentQuestion.label}
          </p>
          <p className="mt-1 text-xs leading-6 text-muted-foreground">
            {currentQuestion.why_needed}
          </p>
        </div>
        <div className="shrink-0 rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-2.5 py-1 text-[11px] text-muted-foreground">
          {progressLabel}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
        <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-2.5 py-1 text-muted-foreground">
          {formatTagLabel(request.release_status)}
        </span>
        {currentQuestion.severity && (
          <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-2.5 py-1 text-muted-foreground">
            {formatTagLabel(currentQuestion.severity)}
          </span>
        )}
        {currentQuestion.lock_status && (
          <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-2.5 py-1 text-muted-foreground">
            {formatTagLabel(currentQuestion.lock_status)}
          </span>
        )}
      </div>

      <div className="mt-3">{renderInput()}</div>

      {(currentQuestion.allowed_units?.length || currentQuestion.recommended_value !== undefined) && (
        <div className="mt-2 space-y-1 text-[11px] text-muted-foreground">
          {currentQuestion.allowed_units?.length ? (
            <p>Allowed units: {currentQuestion.allowed_units.join(", ")}</p>
          ) : null}
          {currentQuestion.recommended_value !== undefined ? (
            <p>
              Recommended:{" "}
              <span className="font-medium text-foreground">
                {toDisplayValue(currentQuestion.recommended_value)}
              </span>
            </p>
          ) : null}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        {source === "tool_result" ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onDismiss(instanceId)}
            disabled={isLoading}
          >
            Later
          </Button>
        ) : (
          <p className="text-[11px] text-muted-foreground">
            This run is paused until these values are provided.
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {currentQuestion.can_use_default &&
            currentQuestion.recommended_value !== undefined && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => commitAnswer(currentQuestion.recommended_value)}
                disabled={isLoading}
                className={cn(
                  "border-[rgba(24,33,38,0.08)] bg-white text-foreground"
                )}
              >
                Use Recommended
              </Button>
            )}
          <Button
            type="button"
            size="sm"
            onClick={handleNext}
            disabled={isLoading}
          >
            {index >= total - 1 ? "Apply & Continue" : "Next"}
          </Button>
        </div>
      </div>
    </div>
  );
}
