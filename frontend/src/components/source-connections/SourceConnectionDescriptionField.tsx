import React from "react";
import { Textarea } from "@/components/ui/textarea";
import { DESIGN_SYSTEM } from "@/lib/design-system";
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
  const defaultDescriptionPlaceholder = getDefaultSourceConnectionDescription(
    sourceDisplayName,
    collectionDisplayName
  );

  return (
    <div className={cn("space-y-1.5", className)}>
      <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        Description
      </label>
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        maxLength={SOURCE_CONNECTION_DESCRIPTION_MAX_LENGTH}
        rows={1}
        placeholder={defaultDescriptionPlaceholder}
        className={cn(
          DESIGN_SYSTEM.forms.validatedField,
          DESIGN_SYSTEM.forms.singleLineMinHeight,
          "resize-y overflow-y-auto",
          "focus-visible:ring-1 focus-visible:ring-offset-0",
          "dark:bg-gray-800 dark:border-gray-700 dark:text-white dark:placeholder:text-gray-500",
          "bg-white border-gray-200 text-gray-900 placeholder:text-gray-400"
        )}
      />
    </div>
  );
}
