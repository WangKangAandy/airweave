import React, { useRef, useState, type ChangeEvent } from "react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/theme-provider";
import { toast } from "@/hooks/use-toast";
import { apiClient } from "@/lib/api";
import {
    YAML_SOURCE_IMPORT_TEMPLATE,
    YAML_SOURCE_IMPORT_TEMPLATE_FILENAME,
} from "@/lib/yaml-source-import-template";
import { FileText, Loader2, Upload } from "lucide-react";

interface SourceImportResponse {
    summary?: {
        total?: number;
        valid?: number;
        created?: number;
        failed?: number;
    };
    results?: Array<{
        index: number;
        source_type: string;
        name: string;
        status: string;
        message?: string;
    }>;
}

export interface SourceYamlImportPanelProps {
    collectionReadableId: string;
    /** Called after a successful import (at least one connection created). */
    onImportSuccess?: () => void;
    className?: string;
}

export const SourceYamlImportPanel: React.FC<SourceYamlImportPanelProps> = ({
    collectionReadableId,
    onImportSuccess,
    className,
}) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === "dark";
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [yamlText, setYamlText] = useState("");
    const [showYamlTemplateDialog, setShowYamlTemplateDialog] = useState(false);
    const [isValidatingYaml, setIsValidatingYaml] = useState(false);
    const [isImportingYaml, setIsImportingYaml] = useState(false);
    const [yamlImportResult, setYamlImportResult] = useState<SourceImportResponse | null>(null);

    const runYamlImport = async (dryRun: boolean) => {
        if (!collectionReadableId) return;
        if (!yamlText.trim()) {
            toast({
                title: "YAML is required",
                description: "Please paste YAML content before continuing.",
                variant: "destructive",
            });
            return;
        }

        if (dryRun) {
            setIsValidatingYaml(true);
        } else {
            setIsImportingYaml(true);
        }

        try {
            const response = await apiClient.post("/source-connections/import-yaml", {
                collection_id: collectionReadableId,
                yaml: yamlText,
                dry_run: dryRun,
            });

            let payload: SourceImportResponse | null = null;
            try {
                payload = await response.json();
            } catch {
                payload = null;
            }

            if (!response.ok) {
                const detail = (payload as { detail?: string })?.detail || `Request failed (HTTP ${response.status})`;
                throw new Error(String(detail));
            }

            if (payload) {
                setYamlImportResult(payload);
            }

            if (dryRun) {
                toast({
                    title: "YAML validated",
                    description: "Validation completed. Review results before importing.",
                });
            } else {
                const created = payload?.summary?.created ?? 0;
                const failed = payload?.summary?.failed ?? 0;
                toast({
                    title: "YAML import completed",
                    description: `Created ${created} source(s), failed ${failed}.`,
                    variant: failed > 0 ? "destructive" : "default",
                });
                if (created > 0) {
                    onImportSuccess?.();
                }
            }
        } catch (error) {
            toast({
                title: dryRun ? "Validation failed" : "Import failed",
                description: error instanceof Error ? error.message : String(error),
                variant: "destructive",
            });
        } finally {
            setIsValidatingYaml(false);
            setIsImportingYaml(false);
        }
    };

    const handleYamlFileSelected = async (event: ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;
        try {
            const content = await file.text();
            setYamlText(content);
            toast({
                title: "YAML loaded",
                description: `${file.name} has been loaded into the editor.`,
            });
        } catch {
            toast({
                title: "Failed to read file",
                description: "Please try again with a valid .yaml/.yml file.",
                variant: "destructive",
            });
        } finally {
            event.target.value = "";
        }
    };

    const handleDownloadYamlTemplate = () => {
        const blob = new Blob([YAML_SOURCE_IMPORT_TEMPLATE], {
            type: "text/yaml;charset=utf-8",
        });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = YAML_SOURCE_IMPORT_TEMPLATE_FILENAME;
        anchor.rel = "noopener";
        anchor.click();
        URL.revokeObjectURL(url);
        toast({
            title: "Download started",
            description: YAML_SOURCE_IMPORT_TEMPLATE_FILENAME,
        });
    };

    const handleApplyYamlTemplateToEditor = () => {
        setYamlText(YAML_SOURCE_IMPORT_TEMPLATE);
        setShowYamlTemplateDialog(false);
        toast({
            title: "Template applied",
            description: "The example YAML has been copied into the editor. Replace placeholders before importing.",
        });
    };

    return (
        <div
            className={cn(
                "flex flex-col h-full min-h-0 px-6 pt-6 pb-4",
                isDark ? "bg-gray-950" : "bg-gray-50",
                className
            )}
        >
            <div className="shrink-0 space-y-2 mb-3">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Import sources from YAML</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                    Paste YAML using grouped structure{" "}
                    <code className="text-xs bg-muted px-1 rounded">sources.&lt;type&gt;.&lt;name&gt;</code>, then
                    validate or import. Use 示例模板 for a full sample (download or apply to editor).
                </p>
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                    <p className="text-xs text-muted-foreground">
                        Target collection: <span className="font-mono">{collectionReadableId}</span>
                    </p>
                    <div className="flex flex-wrap items-center justify-end gap-2">
                        <Button type="button" variant="outline" size="sm" onClick={() => setShowYamlTemplateDialog(true)}>
                            <FileText className="h-3.5 w-3.5 mr-1.5" />
                            示例模板
                        </Button>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".yaml,.yml,text/yaml,text/x-yaml"
                            className="hidden"
                            onChange={handleYamlFileSelected}
                        />
                        <Button type="button" variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                            <Upload className="h-3.5 w-3.5 mr-1.5" />
                            Load file
                        </Button>
                    </div>
                </div>
            </div>

            <Textarea
                value={yamlText}
                onChange={(e) => setYamlText(e.target.value)}
                placeholder={`version: 1\n\nsources:\n  github:\n    Airweave Main:\n      personal_access_token: \${GITHUB_PAT}\n      repo_name: airweave-ai/airweave`}
                className="flex-1 min-h-[240px] font-mono text-xs resize-none"
            />

            {yamlImportResult && (
                <div className="shrink-0 rounded-md border border-border p-3 text-sm space-y-1 mt-3 max-h-32 overflow-y-auto">
                    <p>
                        Total: {yamlImportResult.summary?.total ?? 0} | Valid: {yamlImportResult.summary?.valid ?? 0} |
                        Created: {yamlImportResult.summary?.created ?? 0} | Failed:{" "}
                        {yamlImportResult.summary?.failed ?? 0}
                    </p>
                    {(yamlImportResult.results ?? [])
                        .filter((item) => item.status === "failed")
                        .slice(0, 8)
                        .map((item) => (
                            <p
                                key={`${item.source_type}-${item.name}-${item.index}`}
                                className="text-destructive text-xs"
                            >
                                [{item.source_type}] {item.name}: {item.message || "Failed"}
                            </p>
                        ))}
                </div>
            )}

            <div className="shrink-0 flex justify-end gap-2 mt-4 pt-2 border-t border-gray-200 dark:border-gray-800">
                <Button
                    type="button"
                    variant="outline"
                    onClick={() => runYamlImport(true)}
                    disabled={isValidatingYaml || isImportingYaml}
                >
                    {isValidatingYaml ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                    Validate YAML
                </Button>
                <Button type="button" onClick={() => runYamlImport(false)} disabled={isValidatingYaml || isImportingYaml}>
                    {isImportingYaml ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                    Import Sources
                </Button>
            </div>

            <Dialog open={showYamlTemplateDialog} onOpenChange={setShowYamlTemplateDialog}>
                <DialogContent className="flex max-h-[90vh] w-[min(96vw,1280px)] max-w-[min(96vw,1280px)] flex-col gap-0 overflow-hidden p-0 sm:max-w-[min(96vw,1280px)]">
                    <DialogHeader className="px-6 pt-6 pb-3 shrink-0">
                        <DialogTitle>示例模板</DialogTitle>
                        <DialogDescription>
                            Full example for YAML bulk import (github, gitlab, local_git, dingtalk, confluence).
                            Download the file or apply to the editor, then replace secrets and URLs before validating.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="flex min-h-0 flex-1 flex-col gap-3 px-6 pb-4">
                        <div
                            className={cn(
                                "max-h-[min(55vh,560px)] min-h-0 overflow-x-auto overflow-y-auto rounded-md border border-border",
                                "bg-muted/30",
                            )}
                        >
                            <pre
                                className="m-0 min-w-max p-3 font-mono text-xs whitespace-pre"
                                tabIndex={0}
                            >
                                {YAML_SOURCE_IMPORT_TEMPLATE}
                            </pre>
                        </div>
                    </div>
                    <DialogFooter className="px-6 py-4 border-t border-border shrink-0 gap-2 sm:gap-2">
                        <Button type="button" variant="outline" onClick={handleDownloadYamlTemplate}>
                            Download .yaml
                        </Button>
                        <Button type="button" variant="outline" onClick={() => setShowYamlTemplateDialog(false)}>
                            Close
                        </Button>
                        <Button type="button" onClick={handleApplyYamlTemplateToEditor}>
                            Apply to editor
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
