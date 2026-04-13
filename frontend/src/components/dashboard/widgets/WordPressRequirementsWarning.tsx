import type { FC } from "react";

export const WordPressRequirementsWarning: FC = () => {
  return (
    <div className="rounded-lg bg-red-50 border-2 border-red-300 p-4">
      <div className="flex items-start gap-2">
        <span className="text-xl" role="img" aria-label="Warning">
          ⚠️
        </span>
        <div className="flex-1">
          <h4 className="font-semibold text-red-900 text-sm mb-3">
            WordPress Requirements
          </h4>
          <div className="space-y-3 text-xs text-red-800">
            <div className="bg-white/50 rounded p-4 border border-red-200">
              <p className="font-semibold mb-2">WordPress.com (Hosted):</p>
              <p className="mb-2">
                <span role="img" aria-label="Not supported">
                  ❌
                </span>{" "}
                Free/Personal/Premium plans:{" "}
                <strong>CANNOT run JavaScript widgets</strong>
              </p>
              <p>
                <span role="img" aria-label="Supported">
                  ✅
                </span>{" "}
                Business plan: All methods below work
              </p>
            </div>
            <div className="bg-white/50 rounded p-4 border border-red-200">
              <p className="font-semibold mb-2">WordPress.org (Self-hosted):</p>
              <p>
                <span role="img" aria-label="Supported">
                  ✅
                </span>{" "}
                All methods work with any hosting provider - No restrictions
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
