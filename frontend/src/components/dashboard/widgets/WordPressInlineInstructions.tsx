import type { FC } from "react";
import { WordPressRequirementsWarning } from "./WordPressRequirementsWarning";

export const WordPressInlineInstructions: FC = () => {
  return (
    <div className="space-y-4 mt-3">
      <WordPressRequirementsWarning />

      {/* Method 1 - HTML Block */}
      <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
        <div className="flex items-start gap-2 mb-3">
          <span className="text-lg" role="img" aria-label="Document">
            📝
          </span>
          <div className="flex-1">
            <h4 className="font-semibold text-slate-800 text-sm">
              METHOD 1 - HTML Block (Gutenberg Editor)
            </h4>
            <p className="text-xs text-slate-600 mt-0.5">
              Easiest - No code editing required
            </p>
          </div>
        </div>
        <ol className="ml-7 list-decimal space-y-1.5 text-sm text-slate-700">
          <li>Edit your page or post in the WordPress editor</li>
          <li>Click the "+" button to add a new block</li>
          <li>Search for and select "Custom HTML" block</li>
          <li>Paste the code above into the block</li>
          <li>Replace YOUR_WIDGET_TOKEN with your actual token</li>
          <li>Update/Publish your page</li>
        </ol>
      </div>

      {/* Method 2 - Shortcode */}
      <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
        <div className="flex items-start gap-2 mb-3">
          <span className="text-lg" role="img" aria-label="Code">
            💻
          </span>
          <div className="flex-1">
            <h4 className="font-semibold text-slate-800 text-sm">
              METHOD 2 - Custom Shortcode
            </h4>
            <p className="text-xs text-slate-600 mt-0.5">
              Reusable across multiple pages
            </p>
          </div>
        </div>
        <ol className="ml-7 list-decimal space-y-1.5 text-sm text-slate-700">
          <li>Go to Appearance → Theme File Editor</li>
          <li>Open functions.php (or create a custom plugin)</li>
          <li>
            Copy the shortcode function from the code above (lines starting with
            "php")
          </li>
          <li>Save the file</li>
          <li>
            In your page/post, add a shortcode block and use:{" "}
            <code className="bg-white px-1.5 py-0.5 rounded border border-slate-300 text-xs">
              [myclone_inline height="600px" token="YOUR_TOKEN"]
            </code>
          </li>
        </ol>
      </div>

      {/* Method 3 - Page Template */}
      <div className="rounded-lg bg-slate-50 border border-slate-200 p-4">
        <div className="flex items-start gap-2 mb-3">
          <span className="text-lg" role="img" aria-label="Tools">
            🔧
          </span>
          <div className="flex-1">
            <h4 className="font-semibold text-slate-800 text-sm">
              METHOD 3 - Page Template
            </h4>
            <p className="text-xs text-slate-600 mt-0.5">
              For dedicated contact/support pages
            </p>
          </div>
        </div>
        <ol className="ml-7 list-decimal space-y-1.5 text-sm text-slate-700">
          <li>Go to Appearance → Theme File Editor</li>
          <li>
            Create a new template file (e.g., template-contact.php) or edit an
            existing page template
          </li>
          <li>
            Add the HTML code from above where you want the chat to appear
          </li>
          <li>Save the template</li>
          <li>
            Create/Edit a page and select this template from Page Attributes
          </li>
        </ol>
      </div>
    </div>
  );
};
