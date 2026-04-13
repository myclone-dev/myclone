import * as React from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface NumericInputProps
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement>,
    "onChange" | "value" | "type"
  > {
  value: number | null | undefined;
  onChange: (value: number | null) => void;
  allowNegative?: boolean;
  allowDecimal?: boolean;
  min?: number;
  max?: number;
  onValidationError?: (message: string | null) => void; // Callback when validation fails (null = cleared)
}

const NumericInput = React.forwardRef<HTMLInputElement, NumericInputProps>(
  (
    {
      value,
      onChange,
      allowNegative = false,
      allowDecimal = false,
      min,
      max,
      onValidationError,
      className,
      ...props
    },
    ref,
  ) => {
    const [internalValue, setInternalValue] = React.useState<string>("");

    // Update internal value when external value changes
    React.useEffect(() => {
      if (value === null || value === undefined) {
        setInternalValue("");
      } else {
        setInternalValue(String(value));
      }
    }, [value]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const inputValue = e.target.value;

      // Allow empty string (for backspace)
      if (inputValue === "") {
        setInternalValue("");
        onChange(null);
        return;
      }

      // Build regex pattern based on options
      let pattern: RegExp;
      if (allowDecimal) {
        pattern = allowNegative ? /^-?\d*\.?\d*$/ : /^\d*\.?\d*$/;
      } else {
        pattern = allowNegative ? /^-?\d*$/ : /^\d*$/;
      }

      // Only allow valid numeric input
      if (!pattern.test(inputValue)) {
        return;
      }

      // Update internal value (allows partial input like "1.")
      setInternalValue(inputValue);

      // Parse and validate
      const parsed = allowDecimal
        ? parseFloat(inputValue)
        : parseInt(inputValue, 10);

      if (!isNaN(parsed)) {
        // Check min/max constraints
        if (min !== undefined && parsed < min) {
          onValidationError?.(`Value must be at least ${min}`);
          return;
        }
        if (max !== undefined && parsed > max) {
          onValidationError?.(`Value must be at most ${max}`);
          return;
        }
        // Clear any previous validation errors
        onValidationError?.(null);
        onChange(parsed);
      }
    };

    return (
      <Input
        ref={ref}
        type="text"
        inputMode={allowDecimal ? "decimal" : "numeric"}
        pattern={allowDecimal ? "[0-9]*[.]?[0-9]*" : "[0-9]*"}
        value={internalValue}
        onChange={handleChange}
        className={cn(className)}
        {...props}
      />
    );
  },
);

NumericInput.displayName = "NumericInput";

export { NumericInput };
