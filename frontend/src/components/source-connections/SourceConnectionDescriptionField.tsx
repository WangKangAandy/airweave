import React from "react";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  SOURCE_CONNECTION_DESCRIPTION_MAX_LENGTH,
  getDefaultSourceConnectionDescription,
} from "@/lib/source-connection-defaults";

export interface SourceConnectionDescriptionFieldProps {
  value: string;
  onChange: (value: string) => void;
  sourceDisplayName: string;
  collectionDisplayName: string;
  disabled?: boolean;
  className?: string;
}

/**
 * Optional per-connection description (below Name). Shared across add-source flows.
 * When left empty, callers should use {@link getDefaultSourceConnectionDescription} on submit.
 */
export function SourceConnectionDescriptionField({
  value,
  onChange,
  sourceDisplayName,
  collectionDisplayName,
  disabled = false,
  className,
}: SourceConnectionDescriptionFieldProps) {
  const preview = getDefaultSourceConnectionDescription(sourceDisplayName, collectionDisplayName);

  return (
    <div className={cn("space-y-1.5", className)}>
      <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        Description <span className="normal-case text-muted-foreground font-normal">(optional)</span>
      </label>
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        maxLength={SOURCE_CONNECTION_DESCRIPTION_MAX_LENGTH}
        rows={2}
        placeholder="What is this connection for? (e.g. HR wiki, product docs)"
        className={cn(
          "resize-y min-h-[2.5rem] text-sm",
          "focus-visible:ring-1 focus-visible:ring-offset-0",
          "dark:bg-gray-800 dark:border-gray-700 dark:text-white dark:placeholder:text-gray-500",
          "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
        )}
      />
      <p className="text-[11px] text-muted-foreground leading-snug">
        If empty, we use: <span className="font-mono text-foreground/80">{preview}</span>
      </p>
    </div>
  );
}
