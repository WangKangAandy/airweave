import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Check, Copy, Key, Plus } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api";
import { APIKey, useAPIKeysStore } from "@/lib/stores/apiKeys";
import { useOrganizationContext } from "@/hooks/use-organization-context";

export const ApiKeyCard = () => {
  const { canManageOrganization } = useOrganizationContext();
  const canManage = canManageOrganization();
  const [copySuccess, setCopySuccess] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const {
    apiKeys,
    isLoading,
    fetchAPIKeys,
    createAPIKey
  } = useAPIKeysStore();

  useEffect(() => {
    if (canManage) {
      fetchAPIKeys();
    }
  }, [canManage, fetchAPIKeys]);

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

  const copyToClipboard = async (value: string): Promise<boolean> => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        return true;
      }
    } catch {
      // Fall back to execCommand when Clipboard API is blocked/insecure.
    }

    return fallbackCopyText(value);
  };

  const handleCopyApiKey = async (apiKey: APIKey) => {
    let keyToCopy = apiKey.decrypted_key?.trim() ?? "";

    // Dashboard list can contain masked values; fetch by id to get full key before copying.
    if (!keyToCopy || keyToCopy.includes("*")) {
      const response = await apiClient.get(`/api-keys/${apiKey.id}`);
      if (response.ok) {
        const latest = await response.json();
        keyToCopy = typeof latest?.decrypted_key === "string" ? latest.decrypted_key.trim() : "";
      }
    }

    if (!keyToCopy || keyToCopy.includes("*")) {
      toast.error("Unable to copy full API key. Please create or rotate a key from API Keys.");
      return;
    }

    const copied = await copyToClipboard(keyToCopy);
    if (copied) {
      setCopySuccess(true);
      toast.success("API key copied to clipboard");
      setTimeout(() => setCopySuccess(false), 2000);
      return;
    }

    toast.error("Clipboard access failed. Please copy from API Keys page.");
  };

  const handleCreateAPIKey = async () => {
    setIsCreating(true);
    try {
      await createAPIKey();
      toast.success("API key created successfully");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to create API key";
      toast.error(errorMessage);
    } finally {
      setIsCreating(false);
    }
  };

  // Get the most recent API key
  const latestApiKey = apiKeys.length > 0 ? apiKeys[0] : null;

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
      <div className="p-5">
        <div className="flex items-center mb-1">
          <Key className="h-4 w-4 mr-1.5 text-muted-foreground" />
          <h3 className="text-sm font-medium">API Key</h3>
        </div>
        <p className="text-xs text-muted-foreground mb-4">Store your API keys securely</p>

        {!canManage ? (
          <div className="text-center py-2">
            <p className="text-xs text-muted-foreground">
              Only admins and owners can manage API keys
            </p>
          </div>
        ) : isLoading ? (
          <div className="flex items-center justify-center py-4">
            <div className="text-xs text-muted-foreground">Loading...</div>
          </div>
        ) : latestApiKey ? (
          <>
            <div className="flex items-center">
              <Input
                // Temporary debug mode: show full API key directly instead of masked value.
                value={latestApiKey.decrypted_key ?? ""}
                className="text-xs font-mono h-9 bg-background border-border"
                readOnly
              />
              <Button
                variant="ghost"
                size="icon"
                className="ml-1 h-9 w-9 relative"
                onClick={() => void handleCopyApiKey(latestApiKey)}
              >
                <div className="relative">
                  <Copy className={`h-3.5 w-3.5 transition-all duration-200 ${copySuccess ? 'opacity-0 scale-75' : 'opacity-100 scale-100'}`} />
                  <Check className={`h-3.5 w-3.5 absolute inset-0 transition-all duration-200 ${copySuccess ? 'opacity-100 scale-100' : 'opacity-0 scale-75'}`} />
                </div>
              </Button>
            </div>
            <div className="mt-2 text-right">
              <Link
                to="/api-keys"
                className="text-xs text-primary hover:underline"
              >
                Need another API key?
              </Link>
            </div>
          </>
        ) : (
          <div className="text-center py-2">
            <p className="text-xs text-muted-foreground mb-3">No API keys yet</p>
            <Button
              size="sm"
              onClick={handleCreateAPIKey}
              disabled={isCreating}
              className="h-8 px-3 text-xs"
            >
              {isCreating ? (
                "Creating..."
              ) : (
                <>
                  <Plus className="h-3 w-3 mr-1" />
                  Create your first API key
                </>
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ApiKeyCard;
