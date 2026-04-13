import { PageLoader } from "@/components/ui/page-loader";

/**
 * Global loading UI (Server Component)
 * Shown while pages are loading
 */
export default function Loading() {
  return <PageLoader variant="minimal" />;
}
