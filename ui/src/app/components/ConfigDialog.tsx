"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Github } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  LabDefaultsConfig,
  StandaloneConfig,
} from "@/lib/config";
import {
  EMPTY_LAB_DEFAULT_OPTIONS,
  findLabDefaultOption,
  type LabDefaultOptionsPayload,
} from "@/lib/labDefaults";
import { ProvisionalCellAdminPanel } from "@/app/components/ProvisionalCellAdminPanel";

const PUBLIC_SITE_URL =
  process.env.NEXT_PUBLIC_PUBLIC_SITE_URL?.trim() || "https://batterylab.online";
const DOCS_URL =
  process.env.NEXT_PUBLIC_DOCS_URL?.trim() || "https://doc.batterylab.online";
const GITHUB_URL =
  process.env.NEXT_PUBLIC_GITHUB_URL?.trim() ||
  "https://github.com/shiyunliu-battery/batterylab.online";
const ADMIN_REVIEW_ENABLED =
  process.env.NEXT_PUBLIC_ENABLE_ADMIN_REVIEW?.trim()?.toLowerCase() === "true";

interface ConfigDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (config: StandaloneConfig) => void;
  initialConfig?: StandaloneConfig;
}

export function ConfigDialog({
  open,
  onOpenChange,
  onSave,
  initialConfig,
}: ConfigDialogProps) {
  const [activeTab, setActiveTab] = useState("general");
  const [defaultInstrumentId, setDefaultInstrumentId] = useState(
    initialConfig?.labDefaults?.defaultInstrumentId || ""
  );
  const [defaultThermalChamberId, setDefaultThermalChamberId] = useState(
    initialConfig?.labDefaults?.defaultThermalChamberId || ""
  );
  const [defaultEisInstrumentId, setDefaultEisInstrumentId] = useState(
    initialConfig?.labDefaults?.defaultEisInstrumentId || ""
  );
  const [defaultEisInstrumentLabel, setDefaultEisInstrumentLabel] = useState(
    initialConfig?.labDefaults?.defaultEisInstrumentLabel || ""
  );
  const [defaultEisSetupNotes, setDefaultEisSetupNotes] = useState(
    initialConfig?.labDefaults?.defaultEisSetupNotes ||
      (initialConfig?.labDefaults?.defaultEisInstrumentId
        ? ""
        : initialConfig?.labDefaults?.defaultEisInstrumentLabel || "")
  );
  const [labDefaultOptions, setLabDefaultOptions] = useState<LabDefaultOptionsPayload>(
    EMPTY_LAB_DEFAULT_OPTIONS
  );
  const [labDefaultsLoading, setLabDefaultsLoading] = useState(false);
  const [labDefaultsError, setLabDefaultsError] = useState<string | null>(null);

  useEffect(() => {
    if (open && initialConfig) {
      setDefaultInstrumentId(initialConfig.labDefaults?.defaultInstrumentId || "");
      setDefaultThermalChamberId(
        initialConfig.labDefaults?.defaultThermalChamberId || ""
      );
      setDefaultEisInstrumentId(
        initialConfig.labDefaults?.defaultEisInstrumentId || ""
      );
      setDefaultEisInstrumentLabel(
        initialConfig.labDefaults?.defaultEisInstrumentLabel || ""
      );
      setDefaultEisSetupNotes(
        initialConfig.labDefaults?.defaultEisSetupNotes ||
          (initialConfig.labDefaults?.defaultEisInstrumentId
            ? ""
            : initialConfig.labDefaults?.defaultEisInstrumentLabel || "")
      );
    }
  }, [open, initialConfig]);

  useEffect(() => {
    if (open) {
      setActiveTab("general");
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    let cancelled = false;
    setLabDefaultsLoading(true);
    setLabDefaultsError(null);

    void fetch("/api/lab-default-options")
      .then(async (response) => {
        const payload = (await response.json()) as
          | LabDefaultOptionsPayload
          | { error?: string };
        if (!response.ok || !("cyclers" in payload)) {
          throw new Error(
            ("error" in payload && payload.error) ||
              "Failed to load approved lab equipment options."
          );
        }
        if (cancelled) {
          return;
        }
        setLabDefaultOptions(payload);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        console.error("Failed to load lab default options:", error);
        setLabDefaultsError(
          error instanceof Error
            ? error.message
            : "Failed to load approved lab equipment options."
        );
        setLabDefaultOptions(EMPTY_LAB_DEFAULT_OPTIONS);
      })
      .finally(() => {
        if (!cancelled) {
          setLabDefaultsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [open]);

  const buildLabDefaults = (): LabDefaultsConfig | undefined => {
    const selectedCycler = findLabDefaultOption(
      labDefaultOptions.cyclers,
      defaultInstrumentId
    );
    const selectedChamber = findLabDefaultOption(
      labDefaultOptions.thermalChambers,
      defaultThermalChamberId
    );
    const selectedEisInstrument = findLabDefaultOption(
      labDefaultOptions.eisInstruments,
      defaultEisInstrumentId
    );

    const labDefaults: LabDefaultsConfig = {
      defaultInstrumentId: defaultInstrumentId || undefined,
      defaultInstrumentLabel: defaultInstrumentId
        ? selectedCycler?.label || initialConfig?.labDefaults?.defaultInstrumentLabel
        : undefined,
      defaultThermalChamberId: defaultThermalChamberId || undefined,
      defaultThermalChamberLabel: defaultThermalChamberId
        ? selectedChamber?.label ||
          initialConfig?.labDefaults?.defaultThermalChamberLabel
        : undefined,
      defaultEisInstrumentId: defaultEisInstrumentId || undefined,
      defaultEisInstrumentLabel: defaultEisInstrumentId
        ? selectedEisInstrument?.label ||
          defaultEisInstrumentLabel ||
          initialConfig?.labDefaults?.defaultEisInstrumentLabel
        : undefined,
      defaultEisSetupNotes: defaultEisSetupNotes.trim() || undefined,
    };

    if (
      !labDefaults.defaultInstrumentId &&
      !labDefaults.defaultInstrumentLabel &&
      !labDefaults.defaultThermalChamberId &&
      !labDefaults.defaultThermalChamberLabel &&
      !labDefaults.defaultEisInstrumentId &&
      !labDefaults.defaultEisInstrumentLabel &&
      !labDefaults.defaultEisSetupNotes
    ) {
      return undefined;
    }

    return labDefaults;
  };

  const handleSave = () => {
    if (!initialConfig) {
      return;
    }

    onSave({
      ...initialConfig,
      labDefaults: buildLabDefaults(),
      uiPreferences: initialConfig.uiPreferences,
    });
    onOpenChange(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
    >
      <DialogContent className="flex h-[88vh] max-h-[88vh] min-h-0 flex-col overflow-hidden sm:max-w-[1100px]">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Keep only the core controls for lab defaults and public project links.
          </DialogDescription>
        </DialogHeader>
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="flex min-h-0 flex-1 flex-col"
        >
          <TabsList
            className={`grid h-auto rounded-[6px] bg-slate-100 p-1 ${
              ADMIN_REVIEW_ENABLED ? "grid-cols-2" : "grid-cols-1"
            }`}
          >
            <TabsTrigger
              value="general"
              className="rounded-[4px] font-medium"
            >
              General
            </TabsTrigger>
            {ADMIN_REVIEW_ENABLED ? (
              <TabsTrigger
                value="admin-review"
                className="rounded-[4px] font-medium"
              >
                Admin Review
              </TabsTrigger>
            ) : null}
          </TabsList>

          <TabsContent
            value="general"
            className="mt-4 min-h-0 flex-1 overflow-hidden"
          >
            <div className="flex h-full min-h-0 flex-col overflow-hidden">
              <div className="min-h-0 flex-1 overflow-y-auto pr-1">
                <div className="space-y-4 pb-1">
                  <div className="rounded-[6px] border border-slate-200 bg-slate-50 p-5">
                    <div className="space-y-1">
                      <h3 className="text-sm font-semibold text-foreground">
                        Public Links
                      </h3>
                      <p className="text-sm leading-6 text-muted-foreground">
                        Jump to the live site, docs, and the public source repository.
                      </p>
                    </div>

                    <div className="mt-5 flex flex-wrap gap-3">
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                      >
                        <a
                          href={PUBLIC_SITE_URL}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Website
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </Button>
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                      >
                        <a
                          href={DOCS_URL}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Docs
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </Button>
                      <Button
                        asChild
                        variant="outline"
                        size="sm"
                      >
                        <a
                          href={GITHUB_URL}
                          target="_blank"
                          rel="noreferrer"
                        >
                          GitHub
                          <Github className="h-4 w-4" />
                        </a>
                      </Button>
                    </div>
                  </div>

                  <div className="rounded-[6px] border border-slate-200 bg-slate-50 p-5">
                    <div className="space-y-1">
                      <h3 className="text-sm font-semibold text-foreground">
                        Lab Defaults
                      </h3>
                      <p className="text-sm leading-6 text-muted-foreground">
                        Save the fallback cycler, chamber, and EIS hardware your
                        planner can reuse safely.
                      </p>
                    </div>

                    {labDefaultsError && (
                      <div className="mt-4 rounded-[6px] border border-red-200 bg-red-50 p-3 text-xs font-mono leading-6 text-red-900">
                        {labDefaultsError}
                      </div>
                    )}

                    <div className="mt-5 grid gap-4 md:grid-cols-2">
                      <div className="grid gap-2">
                        <Label htmlFor="defaultInstrumentId">Default Cycler</Label>
                        <Select
                          disabled={labDefaultsLoading}
                          value={defaultInstrumentId || "__none__"}
                          onValueChange={(value) =>
                            setDefaultInstrumentId(value === "__none__" ? "" : value)
                          }
                        >
                          <SelectTrigger id="defaultInstrumentId">
                            <SelectValue placeholder="Select a default cycler" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__none__">Not set</SelectItem>
                            {labDefaultOptions.cyclers.map((option) => (
                              <SelectItem
                                key={option.value}
                                value={option.value}
                              >
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                          Used as the planner fallback when the request does not
                          name a specific cycler.
                        </p>
                      </div>

                      <div className="grid gap-2">
                        <Label htmlFor="defaultThermalChamberId">
                          Default Thermal Chamber
                        </Label>
                        <Select
                          disabled={labDefaultsLoading}
                          value={defaultThermalChamberId || "__none__"}
                          onValueChange={(value) =>
                            setDefaultThermalChamberId(
                              value === "__none__" ? "" : value
                            )
                          }
                        >
                          <SelectTrigger id="defaultThermalChamberId">
                            <SelectValue placeholder="Select a default chamber" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__none__">Not set</SelectItem>
                            {labDefaultOptions.thermalChambers.map((option) => (
                              <SelectItem
                                key={option.value}
                                value={option.value}
                              >
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                          Used when temperature-controlled planning needs a chamber
                          and the current request does not override it.
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div className="grid gap-2">
                        <Label htmlFor="defaultEisInstrumentId">
                          Default EIS / Potentiostat
                        </Label>
                        <Select
                          disabled={labDefaultsLoading}
                          value={defaultEisInstrumentId || "__none__"}
                          onValueChange={(value) => {
                            const nextValue = value === "__none__" ? "" : value;
                            setDefaultEisInstrumentId(nextValue);
                            const option = findLabDefaultOption(
                              labDefaultOptions.eisInstruments,
                              nextValue
                            );
                            setDefaultEisInstrumentLabel(option?.label || "");
                          }}
                        >
                          <SelectTrigger id="defaultEisInstrumentId">
                            <SelectValue placeholder="Select an approved EIS asset" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__none__">Not set</SelectItem>
                            {labDefaultOptions.eisInstruments.map((option) => (
                              <SelectItem
                                key={option.value}
                                value={option.value}
                              >
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                          Keeps impedance-related planning anchored to approved
                          hardware assets instead of free-text device names.
                        </p>
                      </div>

                      <div className="grid gap-2">
                        <Label htmlFor="defaultEisSetupNotes">
                          Default EIS Setup Notes{" "}
                          <span className="text-muted-foreground">(Optional)</span>
                        </Label>
                        <Input
                          id="defaultEisSetupNotes"
                          placeholder="e.g. 5 A booster installed, 4-wire cell leads, pouch jig A"
                          value={defaultEisSetupNotes}
                          onChange={(event) =>
                            setDefaultEisSetupNotes(event.target.value)
                          }
                        />
                        <p className="text-xs text-muted-foreground">
                          Use this only for fixture, wiring, or booster details
                          that are not yet modeled as structured assets.
                        </p>
                      </div>
                    </div>

                    <div className="mt-5 rounded-[6px] border border-slate-200 bg-slate-100/50 p-4 text-xs font-mono leading-5 text-slate-500">
                      Explicit equipment in the current request always wins. These
                      values are only fallback context for planning.
                    </div>
                  </div>
                </div>
              </div>

              <DialogFooter className="mt-4 shrink-0">
                <Button
                  variant="outline"
                  onClick={() => onOpenChange(false)}
                >
                  Cancel
                </Button>
                <Button onClick={handleSave}>Save</Button>
              </DialogFooter>
            </div>
          </TabsContent>

          {ADMIN_REVIEW_ENABLED ? (
            <TabsContent
              value="admin-review"
              className="mt-4 min-h-0 flex-1"
            >
              <ProvisionalCellAdminPanel
                active={open && activeTab === "admin-review"}
              />
            </TabsContent>
          ) : null}
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
