import type { FC } from "react";
import { WordPressRequirementsWarning } from "./WordPressRequirementsWarning";

export const WordPressInstructions: FC = () => {
  return (
    <div className="space-y-4 mt-3">
      <WordPressRequirementsWarning />

      {/* Method 1 - Custom HTML Widget */}
      <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
        <div className="flex items-start gap-2 mb-3">
          <span className="text-lg" role="img" aria-label="Document">
            📝
          </span>
          <div className="flex-1">
            <h4 className="font-semibold text-slate-800 text-sm">
              METHOD 1 - Custom HTML Widget
            </h4>
            <p className="text-xs text-slate-600 mt-0.5">
              Easiest - No code editing required
            </p>
          </div>
        </div>
        <ol className="ml-7 list-decimal space-y-1.5 text-sm text-slate-700">
          <li>Go to WordPress Admin → Appearance → Widgets</li>
          <li>Add a "Custom HTML" widget to your footer area</li>
          <li>Paste the code above into the widget</li>
          <li>Replace YOUR_WIDGET_TOKEN with your actual token</li>
          <li>Click "Save"</li>
        </ol>
      </div>

      {/* Method 2 - Theme Editor */}
      <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
        <div className="flex items-start gap-2 mb-3">
          <span className="text-lg" role="img" aria-label="Tools">
            🔧
          </span>
          <div className="flex-1">
            <h4 className="font-semibold text-slate-800 text-sm">
              METHOD 2 - Theme Editor
            </h4>
            <p className="text-xs text-slate-600 mt-0.5">
              Edit theme files directly
            </p>
          </div>
        </div>
        <ol className="ml-7 list-decimal space-y-1.5 text-sm text-slate-700">
          <li>Go to Appearance → Theme File Editor</li>
          <li>Open footer.php</li>
          <li>
            Paste code before the closing{" "}
            <code className="bg-white px-1.5 py-0.5 rounded border border-slate-300 text-xs">
              &lt;/body&gt;
            </code>{" "}
            tag
          </li>
          <li>Click "Update File"</li>
        </ol>
      </div>

      {/* Method 3 - Plugin */}
      <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
        <div className="flex items-start gap-2 mb-3">
          <span className="text-lg" role="img" aria-label="Plugin">
            🔌
          </span>
          <div className="flex-1">
            <h4 className="font-semibold text-slate-800 text-sm">
              METHOD 3 - Plugin
            </h4>
            <p className="text-xs text-slate-600 mt-0.5">
              Using "Insert Headers and Footers" plugin
            </p>
          </div>
        </div>
        <ol className="ml-7 list-decimal space-y-1.5 text-sm text-slate-700">
          <li>Install "Insert Headers and Footers" plugin</li>
          <li>Go to Settings → Insert Headers and Footers</li>
          <li>Paste code in "Scripts in Footer" section</li>
          <li>Click "Save"</li>
        </ol>
      </div>
    </div>
  );
};
