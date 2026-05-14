import { useState, useEffect, useRef, useCallback, type ChangeEvent } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { Alert } from "@/components/ui/alert";
import { AlertCircle, Pencil, Trash, Plus, Plug, Copy, Check, Loader2, RotateCw, AlertTriangle, FolderTree, FileText, Upload, Download } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useUsageStore } from "@/lib/stores/usage";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";
import { cn } from "@/lib/utils";
import { StatusBadge, statusConfig } from "@/components/ui/StatusBadge";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import SourceConnectionStateView from "@/components/collection/SourceConnectionStateView";
import { emitCollectionEvent, onCollectionEvent, COLLECTION_DELETED, SOURCE_CONNECTION_UPDATED } from "@/lib/events";
import { Search } from '@/search/Search';
// import { DialogFlow } from '@/components/shared'; // TODO: Implement DialogFlow component
import { protectedPaths } from "@/constants/paths";
import { useEntityStateStore } from "@/stores/entityStateStore";
import { useSidePanelStore } from "@/lib/stores/sidePanelStore";
import { useCollectionCreationStore } from "@/stores/collectionCreationStore";
import { redirectWithError } from "@/lib/error-utils";
import { SingleActionCheckResponse } from "@/types";
import { DESIGN_SYSTEM } from "@/lib/design-system";
import { Textarea } from "@/components/ui/textarea";
import {
    YAML_SOURCE_IMPORT_TEMPLATE,
    YAML_SOURCE_IMPORT_TEMPLATE_FILENAME,
} from "@/lib/yaml-source-import-template";


interface DeleteCollectionDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void;
    collectionReadableId: string;
    confirmText: string;
    setConfirmText: (text: string) => void;
}

const DeleteCollectionDialog = ({
    open,
    onOpenChange,
    onConfirm,
    collectionReadableId,
    confirmText,
    setConfirmText
}: DeleteCollectionDialogProps) => {
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const isConfirmValid = confirmText === collectionReadableId;

    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent className={cn(
                "border-border max-w-md",
                isDark ? "bg-card-solid text-foreground" : "bg-white"
            )}>
                <AlertDialogHeader className="space-y-4">
                    {/* Header with warning icon */}
                    <div className="flex items-center gap-3">
                        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-destructive/10 flex items-center justify-center">
                            <AlertTriangle className="w-5 h-5 text-destructive" />
                        </div>
                        <div>
                            <AlertDialogTitle className="text-lg font-semibold text-foreground">
                                Delete Collection
                            </AlertDialogTitle>
                            <p className="text-sm text-muted-foreground mt-1">
                                This action cannot be undone
                            </p>
                        </div>
                    </div>

                    {/* Warning content */}
                    <AlertDialogDescription className="space-y-4">
                        <div className="bg-destructive/5 border border-destructive/20 rounded-lg p-4">
                            <p className="font-medium text-foreground mb-3">
                                This will permanently delete:
                            </p>
                            <ul className="space-y-2 text-sm text-muted-foreground">
                                <li className="flex items-start gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                                    <span>The collection and all its source connections</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                                    <span>All synced data from the knowledge base</span>
                                </li>
                                <li className="flex items-start gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-destructive/60 mt-2 flex-shrink-0" />
                                    <span>All sync history and configuration</span>
                                </li>
                            </ul>
                        </div>

                        {/* Confirmation input */}
                        <div className="space-y-3">
                            <div>
                                <label htmlFor="confirm-delete" className="text-sm font-medium text-foreground block mb-2">
                                    Type <span className="font-mono font-semibold text-destructive bg-destructive/10 px-1.5 py-0.5 rounded">
                                        {collectionReadableId}
                                    </span> to confirm deletion
                                </label>
                                <Input
                                    id="confirm-delete"
                                    value={confirmText}
                                    onChange={(e) => setConfirmText(e.target.value)}
                                    className={cn(
                                        "w-full transition-colors",
                                        isConfirmValid && confirmText.length > 0
                                            ? "border-green-500 focus:border-green-500 focus:ring-green-500/20"
                                            : confirmText.length > 0
                                                ? "border-destructive focus:border-destructive focus:ring-destructive/20"
                                                : ""
                                    )}
                                    placeholder={collectionReadableId}
                                />
                            </div>

                            {/* Validation feedback */}
                            {confirmText.length > 0 && (
                                <div className="flex items-center gap-2 text-sm">
                                    {isConfirmValid ? (
                                        <>
                                            <Check className="w-4 h-4 text-green-500" />
                                            <span className="text-green-600 dark:text-green-400">
                                                Confirmation matches
                                            </span>
                                        </>
                                    ) : (
                                        <>
                                            <AlertCircle className="w-4 h-4 text-destructive" />
                                            <span className="text-destructive">
                                                Confirmation does not match
                                            </span>
                                        </>
                                    )}
                                </div>
                            )}
                        </div>
                    </AlertDialogDescription>
                </AlertDialogHeader>

                <AlertDialogFooter className="gap-3">
                    <AlertDialogCancel className="flex-1">
                        Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction
                        onClick={onConfirm}
                        disabled={!isConfirmValid}
                        className={cn(
                            "flex-1 bg-destructive text-destructive-foreground hover:bg-destructive/90",
                            "disabled:opacity-50 disabled:cursor-not-allowed",
                            "transition-all duration-200"
                        )}
                    >
                        <Trash className="w-4 h-4 mr-2" />
                        Delete Collection
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
};

interface Collection {
    name: string;
    readable_id: string;
    id: string;
    created_at: string;
    modified_at: string;
    organization_id: string;
    created_by_email: string;
    modified_by_email: string;
    status?: string;
}

interface SourceConnection {
    id: string;
    name: string;
    description?: string;
    short_name: string;
    readable_collection_id: string;
    config_fields?: Record<string, any>;
    sync_id?: string;
    organization_id: string;
    created_at: string;
    modified_at: string;
    connection_id?: string;
    collection: string;
    created_by_email: string;
    modified_by_email: string;
    auth_fields?: Record<string, any> | string;
    status?: string;
    is_authenticated?: boolean;
    authentication_url?: string;
    last_sync_job_status?: string;
    last_sync_job_id?: string;
    last_sync_job_started_at?: string;
    last_sync_job_completed_at?: string;
    cron_schedule?: string;
    federated_search?: boolean;  // Whether this source uses federated search
}

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

const Collections = () => {
    /********************************************
     * COMPONENT STATE
     ********************************************/
    const { readable_id } = useParams();
    const { resolvedTheme } = useTheme();
    const isDark = resolvedTheme === 'dark';
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams(); // Use setSearchParams to clean URL
    const isFromOAuthSuccess = searchParams.get("status") === "success";

    // Entity state store for new architecture
    const entityStateStore = useEntityStateStore();

    // Side panel store
    const { isOpen: isPanelOpen, openPanel } = useSidePanelStore();

    // Collection creation store to track modal state
    const { isOpen: isCreationModalOpen } = useCollectionCreationStore();

    // Page state
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isReloading, setIsReloading] = useState(false);

    // Collection state
    const [collection, setCollection] = useState<Collection | null>(null);
    const [isEditingName, setIsEditingName] = useState(false);
    const nameInputRef = useRef<HTMLDivElement>(null);

    // Source connection state
    const [sourceConnections, setSourceConnections] = useState<SourceConnection[]>([]);
    const [selectedConnection, setSelectedConnection] = useState<SourceConnection | null>(null);

    // Add state for delete dialog
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);
    const [confirmText, setConfirmText] = useState('');
    const [isDeleting, setIsDeleting] = useState(false);

    // Add state for copy animation
    const [isCopied, setIsCopied] = useState(false);

    // Add state for refreshing all sources
    const [isRefreshingAll, setIsRefreshingAll] = useState(false);
    const [refreshingSourceIds, setRefreshingSourceIds] = useState<string[]>([]);

    // Browse tree capability for selected connection
    const [selectedScSupportsBrowseTree, setSelectedScSupportsBrowseTree] = useState(false);
    const [showYamlImportDialog, setShowYamlImportDialog] = useState(false);
    const [showYamlTemplateDialog, setShowYamlTemplateDialog] = useState(false);
    const [yamlText, setYamlText] = useState("");
    const [isValidatingYaml, setIsValidatingYaml] = useState(false);
    const [isImportingYaml, setIsImportingYaml] = useState(false);
    const [yamlImportResult, setYamlImportResult] = useState<SourceImportResponse | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Usage check from store (read-only, checking happens at app level)
    const actionChecks = useUsageStore(state => state.actionChecks);
    const isCheckingUsage = useUsageStore(state => state.isLoading);

    // Derived states from usage store
    const sourceConnectionsAllowed = actionChecks.source_connections?.allowed ?? true;
    const sourceConnectionCheckDetails = actionChecks.source_connections ?? null;
    const entitiesAllowed = actionChecks.entities?.allowed ?? true;
    const entitiesCheckDetails = actionChecks.entities ?? null;

    /********************************************
     * API AND DATA FETCHING FUNCTIONS
     ********************************************/

    // Fetch source connections for a collection with detailed sync job status
    const fetchSourceConnections = async (collectionId: string) => {
        try {
            console.log("Fetching source connections for collection:", collectionId);
            const response = await apiClient.get(`/source-connections/?collection=${collectionId}`);

            if (response.ok) {
                const listData = await response.json();
                console.log("Loaded source connection list:", listData);

                // Fetch detailed data for each connection to get sync job status
                const detailedConnections = await Promise.all(
                    listData.map(async (connection: any) => {
                        try {
                            const detailResponse = await apiClient.get(`/source-connections/${connection.id}`);
                            if (detailResponse.ok) {
                                const detailedData = await detailResponse.json();
                                console.log(`📝 Fetched detailed data for ${connection.name}:`, {
                                    last_sync_job_status: detailedData.last_sync_job_status,
                                    last_sync_job_id: detailedData.last_sync_job_id
                                });
                                return detailedData;
                            } else {
                                console.warn(`Failed to fetch details for connection ${connection.id}`);
                                return connection; // fallback to list data
                            }
                        } catch (err) {
                            console.warn(`Error fetching details for connection ${connection.id}:`, err);
                            return connection; // fallback to list data
                        }
                    })
                );

                setSourceConnections(detailedConnections);

                // Entity state mediator will handle subscriptions automatically

                // Always select the first connection when loading a new collection
                if (detailedConnections.length > 0) {
                    // if a source connection was just added, select that one
                    const newSourceId = searchParams.get("source_connection_id");
                    const newConnection = newSourceId ? detailedConnections.find(c => c.id === newSourceId) : null;
                    if (newConnection) {
                        setSelectedConnection(newConnection);
                    } else {
                        setSelectedConnection(detailedConnections[0]);
                    }
                } else {
                    // If no connections, ensure selectedConnection is null
                    setSelectedConnection(null);
                    console.log("No connections to select");
                }
            } else {
                console.error("Failed to load source connections:", await response.text());
                setSourceConnections([]);
                setSelectedConnection(null);
            }
        } catch (err) {
            console.error("Error fetching source connections:", err);
            setSourceConnections([]);
            setSelectedConnection(null);
        } finally {
            setIsLoading(false);
        }
    };

    // Update the existing fetchCollection function to use our new function
    const fetchCollection = async () => {
        if (!readable_id) return;

        setIsLoading(true);
        setError(null);

        try {
            const response = await apiClient.get(`/collections/${readable_id}`);

            if (response.ok) {
                const data = await response.json();
                setCollection(data);
                // After successful collection fetch, fetch source connections
                fetchSourceConnections(data.readable_id);
            } else {
                if (response.status === 404) {
                    setError("Collection not found");
                } else {
                    const errorText = await response.text();
                    setError(`Failed to load collection: ${errorText}`);
                }
                setIsLoading(false);
            }
        } catch (err) {
            setError(`An error occurred: ${err instanceof Error ? err.message : String(err)}`);
            setIsLoading(false);
        }
    };

    // After browser OAuth, backend defers Temporal until verify-oauth (claim token).
    const oauthReturnHandledKey = useRef<string | null>(null);

    useEffect(() => {
        if (!isFromOAuthSuccess) {
            oauthReturnHandledKey.current = null;
        }
    }, [isFromOAuthSuccess]);

    // ** Handle OAuth callback: verify claim token and trigger deferred sync **
    useEffect(() => {
        if (!isFromOAuthSuccess || !readable_id) return;

        const newSourceId = searchParams.get("source_connection_id");
        if (!newSourceId) return;

        // One success navigation (status=success&source_connection_id=...) per URL
        const dedupeKey = `${newSourceId}:${searchParams.toString()}`;
        if (oauthReturnHandledKey.current === dedupeKey) return;
        oauthReturnHandledKey.current = dedupeKey;

        (async () => {
            let verifyFailed = false;
            const storageKey = `oauth_claim_token:${newSourceId}`;
            // Remove before POST so React Strict Mode / double effect cannot call verify twice
            const claimToken = sessionStorage.getItem(storageKey);
            if (claimToken) {
                sessionStorage.removeItem(storageKey);
            }

            if (claimToken) {
                try {
                    const resp = await apiClient.post(
                        `/source-connections/${newSourceId}/verify-oauth`,
                        { claim_token: claimToken }
                    );
                    if (!resp.ok) {
                        let detail: string = "";
                        try {
                            const errBody = await resp.json();
                            if (errBody && typeof errBody.detail === "string") {
                                detail = errBody.detail;
                            } else if (errBody && typeof errBody.message === "string") {
                                detail = errBody.message;
                            }
                        } catch {
                            // ignore
                        }
                        sessionStorage.setItem(storageKey, claimToken);
                        verifyFailed = true;
                        toast({
                            title: "Connection could not be finalized",
                            description: detail || `Request failed (HTTP ${resp.status}). Try \"Connect now\" again.`,
                            variant: "destructive",
                        });
                    }
                } catch (err) {
                    sessionStorage.setItem(storageKey, claimToken);
                    verifyFailed = true;
                    toast({
                        title: "Connection could not be finalized",
                        description: err instanceof Error ? err.message : String(err),
                        variant: "destructive",
                    });
                }
            } else {
                console.warn(
                    "OAuth return: no claim token in sessionStorage; if sync never starts, re-open Connect from the source card."
                );
                oauthReturnHandledKey.current = null;
            }

            // Always refresh from route (do not wait for `collection` state) so status updates
            // even when this effect runs before the first /collections fetch finishes.
            try {
                const collResp = await apiClient.get(`/collections/${readable_id}`);
                if (collResp.ok) {
                    setCollection(await collResp.json());
                }
            } catch {
                // non-fatal
            }
            await fetchSourceConnections(readable_id);

            if (verifyFailed) {
                oauthReturnHandledKey.current = null;
            } else if (claimToken) {
                toast({
                    title: "Source connected",
                    description: "Initial sync is starting. Documents will show up as they are indexed.",
                });
                const newSearchParams = new URLSearchParams(searchParams);
                newSearchParams.delete("status");
                newSearchParams.delete("source_connection_id");
                newSearchParams.delete("collection");
                setSearchParams(newSearchParams, { replace: true });
            }
        })();
        // fetchSourceConnections is intentionally omitted: it is not stable across renders
        // and would retrigger this effect every paint.
    }, [isFromOAuthSuccess, readable_id, searchParams, setSearchParams, toast]);

    // OAuth callback failed (backend 303 to collection with oauth_status=error&reason=...)
    const oauthCallbackErrorHandledKey = useRef<string | null>(null);
    useEffect(() => {
        if (searchParams.get("oauth_status") !== "error") {
            oauthCallbackErrorHandledKey.current = null;
            return;
        }
        const dedupeKey = searchParams.toString();
        if (oauthCallbackErrorHandledKey.current === dedupeKey) return;
        oauthCallbackErrorHandledKey.current = dedupeKey;

        const reasonRaw = searchParams.get("reason");
        const reason =
            reasonRaw && reasonRaw.trim().length > 0 ? reasonRaw.trim() : "OAuth callback failed";

        toast({
            title: "Connection could not be authorized",
            description: reason,
            variant: "destructive",
        });
        const next = new URLSearchParams(searchParams);
        next.delete("oauth_status");
        next.delete("reason");
        setSearchParams(next, { replace: true });
    }, [searchParams, setSearchParams, toast]);

    // ** NEW: Refresh connections when panel or creation modal closes, in case a new one was added **
    useEffect(() => {
        if (!isPanelOpen && !isCreationModalOpen) {
            if (collection?.readable_id) {
                fetchSourceConnections(collection.readable_id);
            }
        }
    }, [isPanelOpen, isCreationModalOpen, collection?.readable_id]);


    useEffect(() => {
        if (!selectedConnection) {
            setSelectedScSupportsBrowseTree(false);
            return;
        }
        const checkBrowseTree = async () => {
            try {
                const resp = await apiClient.get(`/sources/${selectedConnection.short_name}`);
                if (resp.ok) {
                    const source = await resp.json();
                    setSelectedScSupportsBrowseTree(!!source.supports_browse_tree);
                } else {
                    setSelectedScSupportsBrowseTree(false);
                }
            } catch {
                setSelectedScSupportsBrowseTree(false);
            }
        };
        checkBrowseTree();
    }, [selectedConnection?.id]);

    /********************************************
     * UI EVENT HANDLERS
     ********************************************/

    // ** MODIFIED: Trigger the modal for adding source to existing collection **
    const handleAddSource = () => {
        if (collection) {
            const store = useCollectionCreationStore.getState();
            store.openForAddToCollection(collection.readable_id, collection.name);
        }
    };

    const handleOpenYamlImport = () => {
        setYamlImportResult(null);
        setShowYamlImportDialog(true);
    };

    const runYamlImport = async (dryRun: boolean) => {
        if (!readable_id) return;
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
                collection_id: readable_id,
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
                const detail = (payload as any)?.detail || `Request failed (HTTP ${response.status})`;
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
                await fetchSourceConnections(readable_id);
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

    const handleSelectConnection = (connection: SourceConnection) => {
        console.log("Manually selecting connection:", connection.id);
        setSelectedConnection(connection);
    };

    // Handle name editing
    const startEditingName = () => {
        setIsEditingName(true);
        setTimeout(() => {
            if (nameInputRef.current) {
                nameInputRef.current.innerText = collection?.name || "";
                // Place cursor at the end of text
                const range = document.createRange();
                const selection = window.getSelection();
                const textNode = nameInputRef.current.firstChild || nameInputRef.current;
                const textLength = nameInputRef.current.innerText.length;

                // Position at the end of text
                range.setStart(textNode, textLength);
                range.setEnd(textNode, textLength);

                if (selection) {
                    selection.removeAllRanges();
                    selection.addRange(range);
                }
                nameInputRef.current.focus();
            }
        }, 0);
    };

    const handleSaveNameChange = async () => {
        const newName = nameInputRef.current?.innerText.trim() || "";

        if (!newName || newName === collection?.name) {
            setIsEditingName(false);
            return;
        }

        try {
            const response = await apiClient.patch(`/collections/${readable_id}`, { name: newName });
            if (!response.ok) throw new Error("Failed to update collection name");

            // Update local state after successful API call
            setCollection(prev => prev ? { ...prev, name: newName } : null);
            setIsEditingName(false);

            toast({
                title: "Success",
                description: "Collection name updated successfully"
            });
        } catch (error) {
            console.error("Error updating collection name:", error);
            toast({
                title: "Error",
                description: "Failed to update collection name",
                variant: "destructive"
            });
            setIsEditingName(false);
        }
    };

    const fallbackCopyText = (value: string): boolean => {
        const textArea = document.createElement("textarea");
        textArea.value = value;
        textArea.setAttribute("readonly", "");
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        document.body.appendChild(textArea);
        textArea.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(textArea);
        return copied;
    };

    // Handle copy to clipboard
    const handleCopyId = async () => {
        const readableId = collection?.readable_id?.trim();
        if (!readableId) return;

        let copied = false;
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(readableId);
                copied = true;
            }
        } catch {
            copied = false;
        }

        if (!copied) {
            copied = fallbackCopyText(readableId);
        }

        if (!copied) {
            toast({
                title: "Copy failed",
                description: "Unable to access clipboard. Please copy manually.",
                variant: "destructive"
            });
            return;
        }

        setIsCopied(true);
        setTimeout(() => {
            setIsCopied(false);
        }, 1500);

        toast({
            title: "Copied",
            description: "ID copied to clipboard"
        });
    };

    /********************************************
     * UTILITY FUNCTIONS
     ********************************************/

    // Reload data
    const reloadData = async () => {
        if (!readable_id) return;

        setIsReloading(true);
        try {
            await fetchCollection();
        } finally {
            setIsReloading(false);
        }
    };

    /********************************************
     * SIDE EFFECTS
     ********************************************/

    // Initial data loading
    useEffect(() => {
        console.log(`\nFetching collection because of readable id change\n`)
        setSelectedConnection(null);
        fetchCollection();
    }, [readable_id]); // Only depend on readable_id

    // Usage is now checked at app level by UsageChecker component

    // Handle collection deletion
    const handleDeleteCollection = async () => {
        if (!readable_id || confirmText !== readable_id) return;

        setIsDeleting(true);
        try {
            const response = await apiClient.delete(`/collections/${readable_id}`);

            if (response.ok) {
                // Emit event that collection was deleted
                emitCollectionEvent(COLLECTION_DELETED, { id: readable_id });

                toast({
                    title: "Success",
                    description: "Collection and all associated data deleted successfully"
                });
                // Navigate back to dashboard after successful deletion
                navigate(protectedPaths.dashboard);
            } else {
                const errorText = await response.text();
                throw new Error(`Failed to delete collection: ${errorText}`);
            }
        } catch (err) {
            console.error("Error deleting collection:", err);
            toast({
                title: "Error",
                description: err instanceof Error ? err.message : "Failed to delete collection",
                variant: "destructive"
            });
        } finally {
            setIsDeleting(false);
            setShowDeleteDialog(false);
            setConfirmText(''); // Reset confirm text
        }
    };

    // Entity state mediator handles its own cleanup

    // Listen for source connection updates
    useEffect(() => {
        const unsubscribe = onCollectionEvent(SOURCE_CONNECTION_UPDATED, (data) => {
            console.log("Source connection updated:", data);

            // Always refresh the list from server to ensure consistency
            if (collection?.readable_id) {
                fetchSourceConnections(collection.readable_id);
            }

            // If the deleted connection was selected, clear the selection
            // The fetchSourceConnections will auto-select the first connection if any remain
            if (data.deleted && selectedConnection?.id === data.id) {
                setSelectedConnection(null);
            }
        });

        return unsubscribe;
    }, [collection?.readable_id, selectedConnection?.id]);

    // Add right before the source connections section in render
    useEffect(() => {
        console.log("Source connections state:", {
            count: sourceConnections.length,
            connections: sourceConnections,
            selectedId: selectedConnection?.id
        });
    }, [sourceConnections, selectedConnection]);

    // Add this in the Source Connections Section right above the mapping
    console.log("Rendering source connections section", {
        count: sourceConnections.length,
        selectedId: selectedConnection?.id
    });

    // Get connection status indicator based on connection state
    const getConnectionStatusIndicator = (connection: SourceConnection) => {
        // Detect federated sources based on the federated_search field
        const isFederated = connection.federated_search === true;

        // Use the connection's status directly from the API response
        let colorClass = "bg-gray-400";
        let status = "unknown";
        let isAnimated = false;

        // Federated sources have simpler status logic
        if (isFederated) {
            switch (connection.status) {
                case 'pending_auth':
                    colorClass = "bg-cyan-500";
                    status = "Authentication required";
                    break;
                case 'error':
                    colorClass = "bg-red-500";
                    status = "Connection error";
                    break;
                case 'inactive':
                    colorClass = "bg-gray-400";
                    status = "Inactive";
                    break;
                case 'active':
                default:
                    colorClass = "bg-green-500";
                    status = "Ready for real-time search";
                    break;
            }
        } else {
            // Map the backend SourceConnectionStatus enum values for regular sources
            switch (connection.status) {
                case 'pending_auth':
                    colorClass = "bg-cyan-500";
                    status = "Authentication required";
                    break;
                case 'syncing':
                    colorClass = "bg-blue-500";
                    status = "Syncing";
                    isAnimated = true;
                    break;
                case 'error':
                    colorClass = "bg-red-500";
                    status = "Sync failed";
                    break;
                case 'active':
                    colorClass = "bg-green-500";
                    status = "Active";
                    break;
                case 'inactive':
                    colorClass = "bg-gray-400";
                    status = "Inactive";
                    break;
                default:
                    // Fallback for unknown status
                    colorClass = "bg-gray-400";
                    status = "Unknown";
            }
        }

        return (
            <span
                className={cn(
                    "inline-flex h-2 w-2 rounded-full opacity-80",
                    colorClass,
                    isAnimated && "animate-pulse"
                )}
                title={status}
            />
        );
    };

    if (error) {
        return (
            <div className="container mx-auto py-6">
                <h1 className="text-3xl font-bold mb-6 text-foreground">Collection Error</h1>
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <div className="font-medium">Error</div>
                    <div>{error}</div>
                </Alert>
                <div className="mt-4">
                    <Button onClick={() => navigate(protectedPaths.dashboard)}>
                        Return to Dashboard
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className={cn(
            "container mx-auto py-6 flex flex-col items-center",
            isDark ? "text-foreground" : ""
        )}>
            {/* Show loading state when isLoading or no collection data yet */}
            {(isLoading || !collection) && !error ? (
                <div className="w-full h-48 flex flex-col items-center justify-center space-y-4">
                    <Loader2 className="h-10 w-10 animate-spin text-primary" />
                    <p className="text-muted-foreground">Loading collection data...</p>
                </div>
            ) : (
                <>
                    {/* Header with Title and Status Badge */}
                    <div className="w-full max-w-[1000px] flex items-center justify-between py-4">
                        <div className="flex items-center gap-3">
                            {/* Source Icons */}
                            <div className="flex justify-start items-center" style={{ minWidth: "3.5rem" }}>
                                {sourceConnections.slice(0, 3).map((connection, index) => (
                                    <div
                                        key={connection.id}
                                        className={cn(
                                            "w-12 h-12 rounded-md border p-1 flex items-center justify-center overflow-hidden",
                                            isDark ? "bg-gray-900 border-border" : "bg-white border-border"
                                        )}
                                        style={{
                                            marginLeft: index > 0 ? `-${Math.min(index * 8, 24)}px` : "0px",
                                            zIndex: 3 - index
                                        }}
                                    >
                                        <img
                                            src={getAppIconUrl(connection.short_name, resolvedTheme)}
                                            alt={connection.name}
                                            className="max-w-full max-h-full w-auto h-auto object-contain"
                                        />
                                    </div>
                                ))}
                                {sourceConnections.length > 3 && (
                                    <div className="ml-2 text-sm font-medium text-slate-500 dark:text-slate-400">
                                        +{sourceConnections.length - 3}
                                    </div>
                                )}
                            </div>

                            <div className="flex flex-col justify-center">
                                {isEditingName ? (
                                    <div className="flex items-center gap-2">
                                        <div
                                            ref={nameInputRef}
                                            contentEditable
                                            className="text-3xl font-bold tracking-tight text-foreground outline-none p-1 pl-0 pr-3 rounded border border-border/40 transition-all duration-150"
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') {
                                                    e.preventDefault();
                                                    handleSaveNameChange();
                                                }
                                                if (e.key === 'Escape') {
                                                    e.preventDefault();
                                                    setIsEditingName(false);
                                                }
                                            }}
                                            onBlur={handleSaveNameChange}
                                        />
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-2">
                                        <h1 className="text-2xl font-bold tracking-tight text-foreground py-1 pl-0">{collection?.name}</h1>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className={cn(
                                                DESIGN_SYSTEM.buttons.heights.compact,
                                                "w-6 text-muted-foreground hover:text-foreground"
                                            )}
                                            onClick={startEditingName}
                                        >
                                            <Pencil className={DESIGN_SYSTEM.icons.inline} />
                                        </Button>
                                        {collection?.status && (
                                            <StatusBadge status={collection.status} showTooltip={true} tooltipContext="collection" />
                                        )}
                                    </div>
                                )}
                                <p className="text-muted-foreground text-sm group relative flex items-center">
                                    {collection?.readable_id}
                                    <button
                                        className="ml-1.5 opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100 focus:outline-none"
                                        onClick={handleCopyId}
                                        title="Copy ID"
                                    >
                                        {isCopied ? (
                                            <Check className="h-3.5 w-3.5 text-muted-foreground  transition-all" />
                                        ) : (
                                            <Copy className="h-3.5 w-3.5 text-muted-foreground transition-all" />
                                        )}
                                    </button>
                                </p>
                            </div>
                        </div>

                        {/* Header action buttons */}
                        <div className="flex gap-1.5 items-center">
                            {/* Refresh Page Button - EXACT match to refresh source button */}
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <button
                                            type="button"
                                            onClick={reloadData}
                                            disabled={isReloading}
                                            className={cn(
                                                "h-8 w-8 rounded-md border shadow-sm flex items-center justify-center transition-all duration-200",
                                                isReloading
                                                    ? isDark
                                                        ? "bg-gray-900 border-border cursor-not-allowed"
                                                        : "bg-white border-border cursor-not-allowed"
                                                    : isDark
                                                        ? "bg-gray-900 border-border hover:bg-muted cursor-pointer"
                                                        : "bg-white border-border hover:bg-muted cursor-pointer"
                                            )}
                                        >
                                            <RotateCw className={cn(
                                                "h-3 w-3 text-muted-foreground",
                                                "transition-transform duration-500",
                                                isReloading && "animate-spin"
                                            )} />
                                        </button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>Reload page</p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>

                            {/* Delete Collection Button - EXACT match to refresh button styling */}
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <button
                                            type="button"
                                            onClick={() => setShowDeleteDialog(true)}
                                            className={cn(
                                                "h-8 w-8 rounded-md border shadow-sm flex items-center justify-center transition-all duration-200",
                                                isDark
                                                    ? "bg-gray-900 border-border hover:bg-muted cursor-pointer"
                                                    : "bg-white border-border hover:bg-muted cursor-pointer"
                                            )}
                                        >
                                            <Trash className="h-3 w-3 text-muted-foreground" />
                                        </button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p>Delete collection</p>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        </div>
                    </div>



                    {/* Add Search component when collection has any synced data */}
                    {collection?.readable_id && (
                        <div className="w-full max-w-[1000px] mt-10">
                            <Search
                                collectionReadableId={collection.readable_id}
                                disabled={sourceConnections.length === 0}
                            />
                        </div>
                    )}



                    {/* Source Connections Section */}
                    <div className="w-full max-w-[1000px] mt-8">
                        {sourceConnections.length > 0 && (
                            <div className={cn("flex flex-wrap", DESIGN_SYSTEM.spacing.gaps.standard)}>
                                {sourceConnections.map((connection) => (
                                    <div
                                        key={connection.id}
                                        className={cn(
                                            DESIGN_SYSTEM.buttons.heights.primary,
                                            "flex items-center overflow-hidden flex-shrink-0 flex-grow-0 cursor-pointer",
                                            DESIGN_SYSTEM.spacing.gaps.standard,
                                            DESIGN_SYSTEM.buttons.padding.secondary,
                                            "py-2",
                                            DESIGN_SYSTEM.radius.button,
                                            DESIGN_SYSTEM.transitions.standard,
                                            selectedConnection?.id === connection.id
                                                ? isDark
                                                    ? "border border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/20 ring-2 ring-blue-500/30"
                                                    : "border border-blue-500 bg-blue-50 shadow-lg shadow-blue-500/20 ring-2 ring-blue-500/30"
                                                : isDark
                                                    ? "border border-gray-800/50 bg-gray-900 hover:bg-muted"
                                                    : "border border-gray-200/60 bg-white hover:bg-muted"
                                        )}
                                        onClick={() => handleSelectConnection(connection)}
                                    >
                                        {getConnectionStatusIndicator(connection)}

                                        <div className={cn(
                                            "rounded-md flex items-center justify-center overflow-hidden flex-shrink-0",
                                        )}>
                                            <img
                                                src={getAppIconUrl(connection.short_name, resolvedTheme)}
                                                alt={connection.name}
                                                className={cn(DESIGN_SYSTEM.icons.large, "object-contain")}
                                            />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <span className={cn(
                                                DESIGN_SYSTEM.typography.sizes.header,
                                                DESIGN_SYSTEM.typography.weights.medium,
                                                "truncate block text-foreground"
                                            )}>{connection.name}</span>
                                        </div>
                                    </div>
                                ))}

                                {/* Add Source Button - Row (main UI + usage gating) */}
                                <TooltipProvider delayDuration={100}>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <div
                                                className={cn(
                                                    DESIGN_SYSTEM.buttons.heights.primary,
                                                    "flex items-center overflow-hidden flex-shrink-0 flex-grow-0 cursor-pointer",
                                                    DESIGN_SYSTEM.spacing.gaps.standard,
                                                    DESIGN_SYSTEM.buttons.padding.secondary,
                                                    "py-2",
                                                    DESIGN_SYSTEM.radius.button,
                                                    DESIGN_SYSTEM.transitions.standard,
                                                    "border border-dashed",
                                                    (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                                                        ? "opacity-50 cursor-not-allowed border-gray-300 dark:border-gray-700"
                                                        : isDark
                                                            ? "border-blue-500/30 bg-blue-500/5 hover:bg-blue-500/15 hover:border-blue-400/40"
                                                            : "border-blue-400/40 bg-blue-50/30 hover:bg-blue-50/70 hover:border-blue-400/50"
                                                )}
                                                onClick={(!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage) ? undefined : handleAddSource}
                                            >
                                                <Plus className={cn(
                                                    DESIGN_SYSTEM.icons.large,
                                                    (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                                                        ? "text-gray-400"
                                                        : isDark ? "text-blue-400" : "text-blue-500"
                                                )} strokeWidth={1.5} />
                                                <span className={cn(
                                                    DESIGN_SYSTEM.typography.sizes.header,
                                                    DESIGN_SYSTEM.typography.weights.medium,
                                                    "text-foreground"
                                                )}>Add Source</span>
                                            </div>
                                        </TooltipTrigger>
                                        {(!entitiesAllowed || !sourceConnectionsAllowed) && (
                                            <TooltipContent className="max-w-xs">
                                                <p className={DESIGN_SYSTEM.typography.sizes.body}>
                                                    {(!entitiesAllowed && entitiesCheckDetails?.reason === 'usage_limit_exceeded') && (
                                                        <>Entity processing limit reached.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Upgrade your plan</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                    {(!entitiesAllowed && entitiesCheckDetails?.reason === 'payment_required') && (
                                                        <>Billing issue detected.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Update billing</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                    {(entitiesAllowed && !sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'usage_limit_exceeded') && (
                                                        <>Source connection limit reached.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Upgrade your plan</a>
                                                            {' '}for more connections.
                                                        </>
                                                    )}
                                                    {(entitiesAllowed && !sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'payment_required') && (
                                                        <>Billing issue detected.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Update billing</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                </p>
                                            </TooltipContent>
                                        )}
                                    </Tooltip>
                                </TooltipProvider>

                                <TooltipProvider delayDuration={100}>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <div
                                                className={cn(
                                                    DESIGN_SYSTEM.buttons.heights.primary,
                                                    "flex items-center overflow-hidden flex-shrink-0 flex-grow-0 cursor-pointer",
                                                    DESIGN_SYSTEM.spacing.gaps.standard,
                                                    DESIGN_SYSTEM.buttons.padding.secondary,
                                                    "py-2",
                                                    DESIGN_SYSTEM.radius.button,
                                                    DESIGN_SYSTEM.transitions.standard,
                                                    "border",
                                                    (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                                                        ? "opacity-50 cursor-not-allowed border-gray-300 dark:border-gray-700"
                                                        : isDark
                                                            ? "border-gray-600 bg-gray-900 hover:bg-gray-800"
                                                            : "border-gray-300 bg-white hover:bg-gray-50"
                                                )}
                                                onClick={(!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage) ? undefined : handleOpenYamlImport}
                                            >
                                                <FileText
                                                    className={cn(
                                                        DESIGN_SYSTEM.icons.large,
                                                        (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                                                            ? "text-gray-400"
                                                            : isDark
                                                                ? "text-gray-300"
                                                                : "text-gray-600"
                                                    )}
                                                    strokeWidth={1.5}
                                                />
                                                <span
                                                    className={cn(
                                                        DESIGN_SYSTEM.typography.sizes.header,
                                                        DESIGN_SYSTEM.typography.weights.medium,
                                                        "text-foreground"
                                                    )}
                                                >
                                                    Import YAML
                                                </span>
                                            </div>
                                        </TooltipTrigger>
                                        {(!entitiesAllowed || !sourceConnectionsAllowed) && (
                                            <TooltipContent className="max-w-xs">
                                                <p className={DESIGN_SYSTEM.typography.sizes.body}>
                                                    {(!entitiesAllowed && entitiesCheckDetails?.reason === 'usage_limit_exceeded') && (
                                                        <>Entity processing limit reached.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Upgrade your plan</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                    {(!entitiesAllowed && entitiesCheckDetails?.reason === 'payment_required') && (
                                                        <>Billing issue detected.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Update billing</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                    {(entitiesAllowed && !sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'usage_limit_exceeded') && (
                                                        <>Source connection limit reached.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Upgrade your plan</a>
                                                            {' '}for more connections.
                                                        </>
                                                    )}
                                                    {(entitiesAllowed && !sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'payment_required') && (
                                                        <>Billing issue detected.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Update billing</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                </p>
                                            </TooltipContent>
                                        )}
                                    </Tooltip>
                                </TooltipProvider>
                            </div>
                        )}

                        {sourceConnections.length === 0 && (
                            <div className={cn(
                                "flex flex-col items-center justify-center py-12 rounded-lg border-2 border-dashed",
                                isDark
                                    ? "border-gray-700 bg-gray-900/30"
                                    : "border-gray-200 bg-gray-50/50"
                            )}>
                                <div className={cn(
                                    "w-12 h-12 rounded-full flex items-center justify-center mb-4",
                                    isDark
                                        ? "bg-gray-800 border border-gray-700"
                                        : "bg-white border border-gray-200"
                                )}>
                                    <Plug className={cn(
                                        "h-6 w-6",
                                        isDark ? "text-gray-400" : "text-gray-500"
                                    )} strokeWidth={1.5} />
                                </div>

                                <h3 className={cn(
                                    "text-base font-medium mb-1",
                                    isDark ? "text-gray-200" : "text-gray-900"
                                )}>
                                    No sources connected
                                </h3>
                                <p className={cn(
                                    "text-sm mb-6 max-w-sm text-center",
                                    isDark ? "text-gray-400" : "text-gray-600"
                                )}>
                                    Connect your first data source to start syncing and searching your data
                                </p>

                                <TooltipProvider delayDuration={100}>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <div className="flex items-center gap-3">
                                                <span tabIndex={0}>
                                                    <button
                                                        type="button"
                                                        className={cn(
                                                            "inline-flex items-center justify-center",
                                                            "h-9 px-4 py-2",
                                                            "text-sm font-medium",
                                                            "rounded-md",
                                                            "transition-all duration-200",
                                                            "border",
                                                            (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                                                                ? "opacity-50 cursor-not-allowed border-gray-300 bg-gray-100 text-gray-400"
                                                                : isDark
                                                                    ? "border-blue-500 bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 hover:border-blue-400"
                                                                    : "border-blue-500 bg-blue-50 text-blue-600 hover:bg-blue-100 hover:border-blue-600"
                                                        )}
                                                        onClick={(!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage) ? undefined : handleAddSource}
                                                        disabled={!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage}
                                                    >
                                                        <Plus className="h-4 w-4 mr-1.5" strokeWidth={2} />
                                                        Connect a source
                                                    </button>
                                                </span>
                                                <span tabIndex={0}>
                                                    <button
                                                        type="button"
                                                        className={cn(
                                                            "inline-flex items-center justify-center",
                                                            "h-9 px-4 py-2",
                                                            "text-sm font-medium rounded-md border transition-all duration-200",
                                                            (!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage)
                                                                ? "opacity-50 cursor-not-allowed border-gray-300 bg-gray-100 text-gray-400"
                                                                : isDark
                                                                    ? "border-gray-600 bg-gray-800 text-gray-200 hover:bg-gray-700"
                                                                    : "border-gray-300 bg-white text-gray-700 hover:bg-gray-100"
                                                        )}
                                                        onClick={(!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage) ? undefined : handleOpenYamlImport}
                                                        disabled={!sourceConnectionsAllowed || !entitiesAllowed || isCheckingUsage}
                                                    >
                                                        <FileText className="h-4 w-4 mr-1.5" strokeWidth={2} />
                                                        Import YAML
                                                    </button>
                                                </span>
                                            </div>
                                        </TooltipTrigger>
                                        {(!entitiesAllowed || !sourceConnectionsAllowed) && (
                                            <TooltipContent className="max-w-xs">
                                                <p className={DESIGN_SYSTEM.typography.sizes.body}>
                                                    {(!entitiesAllowed && entitiesCheckDetails?.reason === 'usage_limit_exceeded') && (
                                                        <>Entity processing limit reached.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Upgrade your plan</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                    {(!entitiesAllowed && entitiesCheckDetails?.reason === 'payment_required') && (
                                                        <>Billing issue detected.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Update billing</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                    {(entitiesAllowed && !sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'usage_limit_exceeded') && (
                                                        <>Source connection limit reached.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Upgrade your plan</a>
                                                            {' '}for more connections.
                                                        </>
                                                    )}
                                                    {(entitiesAllowed && !sourceConnectionsAllowed && sourceConnectionCheckDetails?.reason === 'payment_required') && (
                                                        <>Billing issue detected.{' '}
                                                            <a href="/organization/settings?tab=billing" className="underline" onClick={(e) => e.stopPropagation()}>Update billing</a>
                                                            {' '}to add new sources.
                                                        </>
                                                    )}
                                                </p>
                                            </TooltipContent>
                                        )}
                                    </Tooltip>
                                </TooltipProvider>
                            </div>
                        )}
                    </div>

                    {/* Browse-tree action buttons for browse-tree capable sources */}
                    {selectedConnection && selectedScSupportsBrowseTree && (
                        <div className="mt-3 w-full max-w-[1000px] flex gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => navigate(`/collections/${readable_id}/browse-tree?sc=${selectedConnection.id}`)}
                            >
                                <FolderTree className="w-3.5 h-3.5 mr-1.5" />
                                Re-select Nodes
                            </Button>
                        </div>
                    )}

                    {/* NEW: Render SourceConnectionStateView instead of the old DAG view */}
                    {selectedConnection && (
                        <div className="mt-4 w-full max-w-[1000px]">
                            <SourceConnectionStateView
                                key={selectedConnection.id}
                                sourceConnectionId={selectedConnection.id}
                                sourceConnectionData={selectedConnection}
                                collectionId={collection?.readable_id}
                                collectionName={collection?.name}
                                onConnectionDeleted={() => {
                                    // Clear selection and reload connections
                                    setSelectedConnection(null);
                                    if (collection?.readable_id) {
                                        fetchSourceConnections(collection.readable_id);
                                    }
                                }}
                                onConnectionUpdated={() => {
                                    // Refresh the connection data
                                    if (collection?.readable_id) {
                                        fetchSourceConnections(collection.readable_id);
                                    }
                                }}
                            />
                        </div>
                    )}

                    {/* Delete Collection Dialog */}
                    <DeleteCollectionDialog
                        open={showDeleteDialog}
                        onOpenChange={setShowDeleteDialog}
                        onConfirm={handleDeleteCollection}
                        collectionReadableId={collection?.readable_id || ''}
                        confirmText={confirmText}
                        setConfirmText={setConfirmText}
                    />

                    <Dialog
                        open={showYamlImportDialog}
                        onOpenChange={(open) => {
                            setShowYamlImportDialog(open);
                            if (!open) {
                                setShowYamlTemplateDialog(false);
                            }
                        }}
                    >
                        <DialogContent className="max-w-2xl">
                            <DialogHeader>
                                <DialogTitle>Import sources from YAML</DialogTitle>
                                <DialogDescription>
                                    {
                                        "Paste YAML using grouped structure sources.<type>.<name>, then validate or import. Use 示例模板 for a full sample covering all supported source types (download or apply to editor)."
                                    }
                                </DialogDescription>
                            </DialogHeader>

                            <div className="space-y-3">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-xs text-muted-foreground">
                                        Target collection: <span className="font-mono">{readable_id}</span>
                                    </p>
                                    <div className="flex flex-wrap items-center justify-end gap-2">
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setShowYamlTemplateDialog(true)}
                                        >
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
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={() => fileInputRef.current?.click()}
                                        >
                                            <Upload className="h-3.5 w-3.5 mr-1.5" />
                                            Load file
                                        </Button>
                                    </div>
                                </div>
                                <Textarea
                                    value={yamlText}
                                    onChange={(e) => setYamlText(e.target.value)}
                                    placeholder={`version: 1\n\nsources:\n  github:\n    Airweave Main:\n      personal_access_token: \${GITHUB_PAT}\n      repo_name: airweave-ai/airweave`}
                                    className="min-h-[280px] font-mono text-xs"
                                />
                            </div>

                            {yamlImportResult && (
                                <div className="rounded-md border border-border p-3 text-sm space-y-1">
                                    <p>
                                        Total: {yamlImportResult.summary?.total ?? 0} | Valid: {yamlImportResult.summary?.valid ?? 0} | Created: {yamlImportResult.summary?.created ?? 0} | Failed: {yamlImportResult.summary?.failed ?? 0}
                                    </p>
                                    {(yamlImportResult.results ?? [])
                                        .filter((item) => item.status === "failed")
                                        .slice(0, 5)
                                        .map((item) => (
                                            <p key={`${item.source_type}-${item.name}-${item.index}`} className="text-destructive text-xs">
                                                [{item.source_type}] {item.name}: {item.message || "Failed"}
                                            </p>
                                        ))}
                                </div>
                            )}

                            <DialogFooter>
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => runYamlImport(true)}
                                    disabled={isValidatingYaml || isImportingYaml}
                                >
                                    {isValidatingYaml ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                                    Validate YAML
                                </Button>
                                <Button
                                    type="button"
                                    onClick={() => runYamlImport(false)}
                                    disabled={isValidatingYaml || isImportingYaml}
                                >
                                    {isImportingYaml ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                                    Import Sources
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>

                    <Dialog open={showYamlTemplateDialog} onOpenChange={setShowYamlTemplateDialog}>
                        <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col gap-0 p-0 overflow-hidden">
                            <DialogHeader className="px-6 pt-6 pb-3 shrink-0">
                                <DialogTitle>示例模板</DialogTitle>
                                <DialogDescription>
                                    Full example for YAML bulk import (github, gitlab, local_git, dingtalk,
                                    confluence). Download the file or apply to the editor, then replace secrets and
                                    URLs before validating.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="px-6 flex-1 min-h-0 flex flex-col gap-3 pb-4">
                                <div
                                    className={cn(
                                        "rounded-md border border-border overflow-y-auto max-h-[50vh]",
                                        "bg-muted/30",
                                    )}
                                >
                                    <pre
                                        className="p-3 text-xs font-mono whitespace-pre-wrap break-words m-0"
                                        tabIndex={0}
                                    >
                                        {YAML_SOURCE_IMPORT_TEMPLATE}
                                    </pre>
                                </div>
                            </div>
                            <DialogFooter className="px-6 py-4 border-t border-border shrink-0 gap-2 sm:gap-2">
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => setShowYamlTemplateDialog(false)}
                                >
                                    Close
                                </Button>
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={handleDownloadYamlTemplate}
                                >
                                    <Download className="h-4 w-4 mr-2" />
                                    Download .yaml
                                </Button>
                                <Button type="button" onClick={handleApplyYamlTemplateToEditor}>
                                    Apply to editor
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>

                </>
            )}
        </div>
    );
};

export default Collections;
