import { env } from "@/env";
import { FIELD_URL_MAP } from "../constants";

export function usePromptDocumentation() {
  const openGuideLink = (fieldId?: string) => {
    const baseUrl = env.NEXT_PUBLIC_LANDING_PAGE_URL;
    const path = fieldId
      ? FIELD_URL_MAP[fieldId]
      : "/docs/user-guide/prompt-configuration";
    const url = `${baseUrl}${path || "/docs/user-guide/prompt-configuration"}`;
    window.open(url, "_blank");
  };

  return { openGuideLink };
}
