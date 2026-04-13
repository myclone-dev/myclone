import { getPasswordStrength } from "@/lib/utils/passwordValidation";

interface PasswordStrengthMeterProps {
  password: string;
  showLabel?: boolean;
}

export function PasswordStrengthMeter({
  password,
  showLabel = true,
}: PasswordStrengthMeterProps) {
  if (!password) {
    return null;
  }

  const strength = getPasswordStrength(password);

  const strengthConfig = {
    weak: {
      label: "Weak",
      color: "bg-red-500",
      textColor: "text-red-600",
      width: "w-1/3",
    },
    medium: {
      label: "Medium",
      color: "bg-yellow-500",
      textColor: "text-yellow-600",
      width: "w-2/3",
    },
    strong: {
      label: "Strong",
      color: "bg-green-500",
      textColor: "text-green-600",
      width: "w-full",
    },
  };

  const config = strengthConfig[strength];

  return (
    <div className="space-y-2">
      {/* Progress bar */}
      <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${config.color} transition-all duration-300 ${config.width}`}
        />
      </div>

      {/* Label */}
      {showLabel && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Password strength:</span>
          <span className={`font-medium ${config.textColor}`}>
            {config.label}
          </span>
        </div>
      )}
    </div>
  );
}
