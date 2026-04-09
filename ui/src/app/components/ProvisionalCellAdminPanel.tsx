"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  ClipboardCheck,
  FileBadge2,
  Loader2,
  RefreshCw,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type RecordLike = Record<string, unknown>;

type ReviewStatus =
  | "all"
  | "draft_extracted"
  | "submitted_for_review"
  | "user_corrected"
  | "needs_changes"
  | "rejected"
  | "approved_for_promotion"
  | "promoted_to_manual_asset";

type AssetSummary = {
  provisional_id?: string;
  display_name?: string;
  manufacturer?: string;
  review_status?: string;
  promotion_readiness?: string;
  submitted_by?: string;
  source_file?: string;
  missing_required_fields?: string[];
  promoted_cell_id?: string;
};

type SearchResponse = {
  status?: string;
  assets?: AssetSummary[];
  asset_count?: number;
  review_status_counts?: Record<string, number>;
  message?: string;
};

type AssetDetailResponse = {
  status?: string;
  asset?: RecordLike;
  asset_summary?: AssetSummary;
  message?: string;
};

const REVIEW_STATUS_OPTIONS: Array<{ value: ReviewStatus; label: string }> = [
  { value: "all", label: "All assets" },
  { value: "draft_extracted", label: "Draft extracted" },
  { value: "submitted_for_review", label: "Submitted for review" },
  { value: "user_corrected", label: "User corrected" },
  { value: "needs_changes", label: "Needs changes" },
  { value: "rejected", label: "Rejected" },
  { value: "approved_for_promotion", label: "Approved for promotion" },
  { value: "promoted_to_manual_asset", label: "Promoted" },
];

function safeRecord(value: unknown): RecordLike {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as RecordLike)
    : {};
}

function toPrettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function readStringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item ?? "").trim()).filter(Boolean)
    : [];
}

function formatTag(value: unknown): string {
  return String(value || "unknown").replace(/_/g, " ");
}

function getStatusChipClasses(value: string | undefined): string {
  const normalized = String(value || "unknown").toLowerCase();
  if (normalized === "approved_for_promotion" || normalized === "promoted_to_manual_asset") {
    return "border-[rgba(52,126,95,0.18)] bg-[rgba(229,244,236,0.95)] text-[rgb(41,104,79)]";
  }
  if (normalized === "needs_changes" || normalized === "draft_extracted") {
    return "border-[rgba(176,115,28,0.18)] bg-[rgba(251,241,221,0.95)] text-[rgb(135,87,20)]";
  }
  if (normalized === "rejected") {
    return "border-[rgba(170,53,53,0.18)] bg-[rgba(252,236,236,0.95)] text-[rgb(146,43,43)]";
  }
  return "border-[rgba(24,33,38,0.08)] bg-[rgba(247,245,241,0.95)] text-muted-foreground";
}

interface ProvisionalCellAdminPanelProps {
  active: boolean;
}

export function ProvisionalCellAdminPanel({
  active,
}: ProvisionalCellAdminPanelProps) {
  const [query, setQuery] = useState("");
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>("all");
  const [assets, setAssets] = useState<AssetSummary[]>([]);
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<AssetDetailResponse | null>(null);
  const [reviewerName, setReviewerName] = useState("admin_reviewer");
  const [reviewNotes, setReviewNotes] = useState("");
  const [correctedFieldsText, setCorrectedFieldsText] = useState("{}");
  const [waiversText, setWaiversText] = useState("");
  const [promotionNotes, setPromotionNotes] = useState("");
  const [finalCellId, setFinalCellId] = useState("");
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [acting, setActing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedAsset = safeRecord(selectedDetail?.asset);
  const selectedSummary = selectedDetail?.asset_summary ?? null;
  const selectedSourceDocument = safeRecord(selectedAsset.source_document);
  const selectedPromotionPreview = safeRecord(selectedAsset.formal_promotion_preview);
  const selectedReviewEvents = Array.isArray(selectedAsset.review_events)
    ? selectedAsset.review_events
    : [];

  const fetchAssets = useCallback(async () => {
    if (!active) return;

    setLoadingList(true);
    setErrorMessage(null);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set("query", query.trim());
      if (reviewStatus !== "all") params.set("reviewStatus", reviewStatus);
      params.set("limit", "50");

      const response = await fetch(`/api/admin/provisional-cells?${params.toString()}`, {
        cache: "no-store",
      });
      const payload = (await response.json()) as SearchResponse;

      if (!response.ok || payload.status === "error") {
        throw new Error(payload.message || "Failed to load provisional cell assets.");
      }

      const nextAssets = payload.assets ?? [];
      setAssets(nextAssets);
      setStatusCounts(payload.review_status_counts ?? {});

      if (nextAssets.length === 0) {
        setSelectedId(null);
        setSelectedDetail(null);
        return;
      }

      const stillExists = nextAssets.some(
        (asset) => asset.provisional_id && asset.provisional_id === selectedId
      );
      const nextSelectedId =
        stillExists && selectedId
          ? selectedId
          : String(nextAssets[0].provisional_id || "");
      setSelectedId(nextSelectedId || null);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to load provisional cell assets."
      );
    } finally {
      setLoadingList(false);
    }
  }, [active, query, reviewStatus, selectedId]);

  const loadAsset = useCallback(async (provisionalId: string) => {
    if (!provisionalId) return;

    setLoadingDetail(true);
    setErrorMessage(null);
    try {
      const response = await fetch(
        `/api/admin/provisional-cells?provisionalId=${encodeURIComponent(provisionalId)}`,
        {
          cache: "no-store",
        }
      );
      const payload = (await response.json()) as AssetDetailResponse;

      if (!response.ok || payload.status === "error") {
        throw new Error(payload.message || "Failed to load provisional asset details.");
      }

      setSelectedDetail(payload);
      const previewCellId = String(
        safeRecord(safeRecord(payload.asset).formal_promotion_preview).proposed_cell_id || ""
      );
      setReviewNotes("");
      setCorrectedFieldsText("{}");
      setWaiversText(
        readStringList(safeRecord(payload.asset).waived_missing_required_fields).join("\n")
      );
      setPromotionNotes("");
      setFinalCellId(previewCellId);
      setReplaceExisting(false);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to load provisional asset details."
      );
      setSelectedDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (!active) return;
    void fetchAssets();
  }, [active, fetchAssets]);

  useEffect(() => {
    if (!active || !selectedId) return;
    void loadAsset(selectedId);
  }, [active, loadAsset, selectedId]);

  const summaryStatusText = useMemo(() => {
    return Object.entries(statusCounts)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([status, count]) => `${formatTag(status)}: ${count}`)
      .join(" · ");
  }, [statusCounts]);

  const parseNotes = useCallback((value: string) => {
    return value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  }, []);

  const parseWaivers = useCallback((value: string) => {
    return value
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  }, []);

  const parseCorrectionJson = useCallback((): Record<string, unknown> => {
    if (!correctedFieldsText.trim()) return {};
    const parsed = JSON.parse(correctedFieldsText) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Correction JSON must be a JSON object.");
    }
    return parsed as Record<string, unknown>;
  }, [correctedFieldsText]);

  const applyReviewDecision = useCallback(
    async (decision: string) => {
      if (!selectedId) return;

      try {
        const correctedFields = parseCorrectionJson();
        setActing(true);
        setErrorMessage(null);
        const response = await fetch("/api/admin/provisional-cells", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            action: "review",
            provisionalId: selectedId,
            decision,
            actor: reviewerName.trim() || "admin_reviewer",
            reviewNotes: parseNotes(reviewNotes),
            correctedFields,
            requiredFieldWaivers: parseWaivers(waiversText),
          }),
        });
        const payload = (await response.json()) as AssetDetailResponse;

        if (!response.ok || payload.status === "error") {
          throw new Error(payload.message || "Failed to apply review decision.");
        }

        await fetchAssets();
        await loadAsset(selectedId);
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to apply review decision."
        );
      } finally {
        setActing(false);
      }
    },
    [
      fetchAssets,
      loadAsset,
      parseCorrectionJson,
      parseNotes,
      parseWaivers,
      reviewNotes,
      reviewerName,
      selectedId,
      waiversText,
    ]
  );

  const promoteAsset = useCallback(async () => {
    if (!selectedId) return;

    try {
      setActing(true);
      setErrorMessage(null);
      const response = await fetch("/api/admin/provisional-cells", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action: "promote",
          provisionalId: selectedId,
          reviewer: reviewerName.trim() || "admin_reviewer",
          finalCellId: finalCellId.trim() || null,
          promotionNotes: parseNotes(promotionNotes),
          replaceExisting,
        }),
      });
      const payload = (await response.json()) as AssetDetailResponse;

      if (!response.ok || payload.status === "error") {
        throw new Error(payload.message || "Failed to promote provisional asset.");
      }

      await fetchAssets();
      await loadAsset(selectedId);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to promote provisional asset."
      );
    } finally {
      setActing(false);
    }
  }, [
    fetchAssets,
    finalCellId,
    loadAsset,
    parseNotes,
    promotionNotes,
    replaceExisting,
    reviewerName,
    selectedId,
  ]);

  return (
    <div className="flex h-[68vh] min-h-[560px] flex-col gap-3">
      <div className="rounded-[18px] border border-[rgba(24,33,38,0.08)] bg-[rgba(248,247,244,0.92)] px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-sm font-semibold text-foreground">Admin Review</div>
            <p className="text-xs leading-6 text-muted-foreground">
              Review provisional datasheet assets, correct extracted fields, approve
              exceptions, and promote only governed records into the formal manual catalog.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              value={reviewerName}
              onChange={(event) => setReviewerName(event.target.value)}
              placeholder="Reviewer name"
              className="w-full sm:w-[190px]"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void fetchAssets()}
              disabled={loadingList || acting}
              className="rounded-full"
            >
              {loadingList ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Refresh queue
            </Button>
          </div>
        </div>
      </div>

      {errorMessage && (
        <div className="rounded-[16px] border border-[rgba(170,53,53,0.18)] bg-[rgba(252,236,236,0.95)] px-4 py-3 text-sm text-[rgb(146,43,43)]">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        </div>
      )}

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="min-h-0 rounded-[18px] border border-[rgba(24,33,38,0.08)] bg-white">
          <div className="border-b border-[rgba(24,33,38,0.08)] px-4 py-3">
            <div className="flex flex-col gap-2">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search provisional assets"
              />
              <div className="flex items-center gap-2">
                <Select
                  value={reviewStatus}
                  onValueChange={(value) => setReviewStatus(value as ReviewStatus)}
                >
                  <SelectTrigger className="h-9 rounded-full border-[rgba(24,33,38,0.08)]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {REVIEW_STATUS_OPTIONS.map((option) => (
                      <SelectItem
                        key={option.value}
                        value={option.value}
                      >
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void fetchAssets()}
                  disabled={loadingList}
                  className="rounded-full px-3"
                >
                  Apply
                </Button>
              </div>
              <div className="text-[11px] leading-5 text-muted-foreground">
                {summaryStatusText || "No provisional assets yet."}
              </div>
            </div>
          </div>

          <ScrollArea className="h-[calc(68vh-170px)]">
            <div className="space-y-2 p-3">
              {loadingList && assets.length === 0 ? (
                <div className="flex items-center gap-2 px-2 py-6 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading review queue...
                </div>
              ) : assets.length === 0 ? (
                <div className="rounded-[14px] border border-dashed border-[rgba(24,33,38,0.12)] bg-[rgba(248,247,244,0.75)] px-3 py-4 text-sm text-muted-foreground">
                  No provisional assets match this filter.
                </div>
              ) : (
                assets.map((asset) => {
                  const assetId = String(asset.provisional_id || "");
                  const missingFields = readStringList(asset.missing_required_fields);
                  return (
                    <button
                      key={assetId}
                      type="button"
                      onClick={() => setSelectedId(assetId)}
                      className={cn(
                        "w-full rounded-[14px] border px-3 py-3 text-left transition-colors",
                        selectedId === assetId
                          ? "border-[rgba(36,87,93,0.24)] bg-[rgba(232,242,239,0.88)]"
                          : "border-[rgba(24,33,38,0.08)] bg-white hover:bg-[rgba(247,245,241,0.92)]"
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-foreground">
                            {asset.display_name || assetId}
                          </div>
                          <div className="truncate text-xs text-muted-foreground">
                            {asset.manufacturer || "Unknown manufacturer"}
                          </div>
                        </div>
                        <span
                          className={cn(
                            "rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.08em]",
                            getStatusChipClasses(asset.review_status)
                          )}
                        >
                          {formatTag(asset.review_status)}
                        </span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                        <span>{asset.promotion_readiness || "review pending"}</span>
                        <span>&middot;</span>
                        <span>{asset.submitted_by || "unknown submitter"}</span>
                      </div>
                      <div className="mt-2 text-[11px] text-muted-foreground">
                        {missingFields.length > 0
                          ? `Missing: ${missingFields.join(", ")}`
                          : "Required fields complete or waived."}
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </ScrollArea>
        </div>
        <div className="min-h-0 rounded-[18px] border border-[rgba(24,33,38,0.08)] bg-white">
          {!selectedId ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center text-sm text-muted-foreground">
              <FileBadge2 className="h-10 w-10 text-muted-foreground/40" />
              <p>Select a provisional asset to review its extracted fields and promotion status.</p>
            </div>
          ) : loadingDetail && !selectedDetail ? (
            <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading asset details...
            </div>
          ) : !selectedDetail ? (
            <div className="flex h-full items-center justify-center px-6 text-sm text-muted-foreground">
              Asset details are unavailable.
            </div>
          ) : (
            <ScrollArea className="h-[68vh]">
              <div className="space-y-4 p-4">
                <div className="rounded-[18px] border border-[rgba(24,33,38,0.08)] bg-[rgba(248,247,244,0.9)] p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div className="text-lg font-semibold text-foreground">
                        {selectedSummary?.display_name || selectedId}
                      </div>
                      <div className="mt-1 text-sm text-muted-foreground">
                        {selectedSummary?.manufacturer || "Unknown manufacturer"}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span
                          className={cn(
                            "rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.08em]",
                            getStatusChipClasses(selectedSummary?.review_status)
                          )}
                        >
                          {formatTag(selectedSummary?.review_status)}
                        </span>
                        <span className="rounded-full border border-[rgba(24,33,38,0.08)] bg-white px-2.5 py-1 text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                          {formatTag(selectedSummary?.promotion_readiness)}
                        </span>
                      </div>
                    </div>
                    <div className="space-y-1 text-right text-xs text-muted-foreground">
                      <div>Provisional id: {selectedSummary?.provisional_id || "unknown"}</div>
                      <div>Submitted by: {selectedSummary?.submitted_by || "unknown"}</div>
                      <div>Source: {String(selectedSourceDocument.original_filename || selectedSummary?.source_file || "unknown")}</div>
                    </div>
                  </div>
                </div>

                <div className="grid gap-3 xl:grid-cols-2">
                  <div className="rounded-[16px] border border-[rgba(24,33,38,0.08)] p-4">
                    <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                      <ClipboardCheck className="h-4 w-4" />
                      Extracted Summary
                    </div>
                    <dl className="grid gap-2 text-sm">
                      <div className="flex justify-between gap-4">
                        <dt className="text-muted-foreground">Display name</dt>
                        <dd className="text-right text-foreground">{String(selectedAsset.display_name || "n/a")}</dd>
                      </div>
                      <div className="flex justify-between gap-4">
                        <dt className="text-muted-foreground">Model</dt>
                        <dd className="text-right text-foreground">
                          {String(selectedAsset.model || selectedAsset.schema_name || "n/a")}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-4">
                        <dt className="text-muted-foreground">Chemistry</dt>
                        <dd className="text-right text-foreground">{String(selectedAsset.project_chemistry_hint || "unknown")}</dd>
                      </div>
                      <div className="flex justify-between gap-4">
                        <dt className="text-muted-foreground">Form factor</dt>
                        <dd className="text-right text-foreground">{String(selectedAsset.form_factor || "unknown")}</dd>
                      </div>
                      <div className="flex justify-between gap-4">
                        <dt className="text-muted-foreground">Missing required fields</dt>
                        <dd className="text-right text-foreground">
                          {readStringList(selectedSummary?.missing_required_fields).join(", ") || "none"}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-4">
                        <dt className="text-muted-foreground">Proposed final cell id</dt>
                        <dd className="text-right text-foreground">
                          {String(selectedPromotionPreview.proposed_cell_id || "n/a")}
                        </dd>
                      </div>
                    </dl>
                  </div>

                  <div className="rounded-[16px] border border-[rgba(24,33,38,0.08)] p-4">
                    <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                      <ArrowUpRight className="h-4 w-4" />
                      Source Document
                    </div>
                    <dl className="grid gap-2 text-sm">
                      <div className="flex justify-between gap-4">
                        <dt className="text-muted-foreground">Original filename</dt>
                        <dd className="text-right text-foreground">{String(selectedSourceDocument.original_filename || "n/a")}</dd>
                      </div>
                      <div className="flex justify-between gap-4">
                        <dt className="text-muted-foreground">Extraction mode</dt>
                        <dd className="text-right text-foreground">{String(selectedSourceDocument.extraction_mode || "n/a")}</dd>
                      </div>
                      <div className="flex justify-between gap-4">
                        <dt className="text-muted-foreground">Detected pages</dt>
                        <dd className="text-right text-foreground">{String(selectedSourceDocument.detected_pages || "n/a")}</dd>
                      </div>
                      <div className="flex justify-between gap-4">
                        <dt className="text-muted-foreground">Thread file</dt>
                        <dd className="max-w-[280px] break-all text-right text-foreground">
                          {String(selectedSourceDocument.thread_file_path || selectedSummary?.source_file || "n/a")}
                        </dd>
                      </div>
                    </dl>
                  </div>
                </div>
                <div className="grid gap-3 xl:grid-cols-2">
                  <div className="rounded-[16px] border border-[rgba(24,33,38,0.08)] p-4">
                    <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                      <ShieldCheck className="h-4 w-4" />
                      Review Actions
                    </div>
                    <div className="grid gap-3">
                      <div className="grid gap-2">
                        <label className="text-xs font-medium text-muted-foreground">
                          Review notes
                        </label>
                        <Textarea
                          value={reviewNotes}
                          onChange={(event) => setReviewNotes(event.target.value)}
                          placeholder="One note per line"
                          className="min-h-[88px]"
                        />
                      </div>
                      <div className="grid gap-2">
                        <label className="text-xs font-medium text-muted-foreground">
                          Corrected fields JSON
                        </label>
                        <Textarea
                          value={correctedFieldsText}
                          onChange={(event) => setCorrectedFieldsText(event.target.value)}
                          placeholder='{"electrical":{"nominal_capacity_ah":1.25}}'
                          className="min-h-[128px] font-mono text-[12px]"
                        />
                      </div>
                      <div className="grid gap-2">
                        <label className="text-xs font-medium text-muted-foreground">
                          Required field waivers
                        </label>
                        <Textarea
                          value={waiversText}
                          onChange={(event) => setWaiversText(event.target.value)}
                          placeholder="One waived field per line"
                          className="min-h-[88px]"
                        />
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => void applyReviewDecision("user_corrected")}
                          disabled={acting}
                          className="rounded-full"
                        >
                          <ClipboardCheck className="h-4 w-4" />
                          Save corrections
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => void applyReviewDecision("submit_for_review")}
                          disabled={acting}
                          className="rounded-full"
                        >
                          <FileBadge2 className="h-4 w-4" />
                          Submit for review
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => void applyReviewDecision("needs_changes")}
                          disabled={acting}
                          className="rounded-full"
                        >
                          <AlertCircle className="h-4 w-4" />
                          Needs changes
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => void applyReviewDecision("reject")}
                          disabled={acting}
                          className="rounded-full"
                        >
                          <ShieldX className="h-4 w-4" />
                          Reject
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          onClick={() => void applyReviewDecision("approve_for_promotion")}
                          disabled={acting}
                          className="rounded-full"
                        >
                          {acting ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <CheckCircle2 className="h-4 w-4" />
                          )}
                          Approve for promotion
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-[16px] border border-[rgba(24,33,38,0.08)] p-4">
                    <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                      <ArrowUpRight className="h-4 w-4" />
                      Promotion
                    </div>
                    <div className="grid gap-3">
                      <div className="grid gap-2">
                        <label className="text-xs font-medium text-muted-foreground">
                          Final cell id
                        </label>
                        <Input
                          value={finalCellId}
                          onChange={(event) => setFinalCellId(event.target.value)}
                          placeholder={String(selectedPromotionPreview.proposed_cell_id || "ACME_LFP21700")}
                        />
                      </div>
                      <div className="grid gap-2">
                        <label className="text-xs font-medium text-muted-foreground">
                          Promotion notes
                        </label>
                        <Textarea
                          value={promotionNotes}
                          onChange={(event) => setPromotionNotes(event.target.value)}
                          placeholder="One promotion note per line"
                          className="min-h-[96px]"
                        />
                      </div>
                      <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                        <input
                          type="checkbox"
                          checked={replaceExisting}
                          onChange={(event) => setReplaceExisting(event.target.checked)}
                          className="h-4 w-4 rounded border-[rgba(24,33,38,0.18)]"
                        />
                        Replace an existing manual cell asset if the final cell id already exists
                      </label>
                      <Button
                        type="button"
                        onClick={() => void promoteAsset()}
                        disabled={acting || selectedSummary?.review_status !== "approved_for_promotion"}
                        className="w-fit rounded-full"
                      >
                        {acting ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <ArrowUpRight className="h-4 w-4" />
                        )}
                        Promote to manual asset
                      </Button>
                    </div>
                  </div>
                </div>

                <div className="grid gap-3 xl:grid-cols-2">
                  <div className="rounded-[16px] border border-[rgba(24,33,38,0.08)] p-4">
                    <div className="mb-3 text-sm font-semibold text-foreground">
                      Field Evidence
                    </div>
                    <pre className="overflow-x-auto rounded-[12px] bg-[rgba(248,247,244,0.92)] p-3 text-[11px] leading-5 text-[rgb(41,50,56)]">
                      {toPrettyJson(selectedAsset.field_evidence)}
                    </pre>
                  </div>
                  <div className="rounded-[16px] border border-[rgba(24,33,38,0.08)] p-4">
                    <div className="mb-3 text-sm font-semibold text-foreground">
                      Review History
                    </div>
                    {selectedReviewEvents.length === 0 ? (
                      <div className="text-sm text-muted-foreground">No review events yet.</div>
                    ) : (
                      <div className="space-y-2">
                        {selectedReviewEvents.map((event, index) => {
                          const record = safeRecord(event);
                          const notes = readStringList(record.notes);
                          return (
                            <div
                              key={`${String(record.at || index)}-${index}`}
                              className="rounded-[12px] bg-[rgba(248,247,244,0.92)] px-3 py-2 text-sm"
                            >
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-medium text-foreground">
                                  {String(record.decision || "unknown")}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                  {String(record.actor || "unknown")}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                  {String(record.at || "")}
                                </span>
                              </div>
                              {notes.length > 0 && (
                                <div className="mt-1 text-xs leading-5 text-muted-foreground">
                                  {notes.join(" · ")}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </ScrollArea>
          )}
        </div>
      </div>
    </div>
  );
}
