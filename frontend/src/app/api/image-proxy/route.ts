import { NextRequest, NextResponse } from "next/server";
import * as Sentry from "@sentry/nextjs";

/**
 * Image Proxy API Route
 * Proxies external images to bypass CORS and hotlink protection
 * Primarily used for LinkedIn profile images
 */
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const imageUrl = searchParams.get("url");

  if (!imageUrl) {
    return NextResponse.json(
      { error: "Missing url parameter" },
      { status: 400 },
    );
  }

  // Validate URL is from allowed domains
  const allowedDomains = [
    "media.licdn.com",
    "*.s3.amazonaws.com",
    "*.s3.*.amazonaws.com",
  ];

  try {
    const url = new URL(imageUrl);
    const isAllowed = allowedDomains.some((domain) => {
      if (domain.startsWith("*.")) {
        const baseDomain = domain.slice(2);
        // Match wildcard patterns like *.s3.*.amazonaws.com
        if (baseDomain.includes("*")) {
          const pattern = baseDomain.replace(/\*/g, ".*");
          const regex = new RegExp(`^${pattern}$`);
          return regex.test(url.hostname);
        }
        return url.hostname.endsWith(baseDomain);
      }
      return url.hostname === domain;
    });

    if (!isAllowed) {
      console.error(`[Image Proxy] Domain not allowed: ${url.hostname}`);
      return NextResponse.json(
        { error: "Domain not allowed" },
        { status: 403 },
      );
    }

    // Fetch the image with appropriate headers
    const response = await fetch(imageUrl, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        Referer: "https://www.linkedin.com/",
        Accept:
          "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to fetch image" },
        { status: response.status },
      );
    }

    const imageBuffer = await response.arrayBuffer();
    const contentType = response.headers.get("content-type") || "image/jpeg";

    // Return the image with appropriate headers
    return new NextResponse(imageBuffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=31536000, immutable",
        "Access-Control-Allow-Origin": "*",
      },
    });
  } catch (error) {
    Sentry.captureException(error, {
      tags: { operation: "image_proxy" },
      contexts: {
        proxy: {
          imageUrl,
          error: error instanceof Error ? error.message : "Unknown error",
        },
      },
    });
    return NextResponse.json(
      { error: "Invalid URL or fetch failed" },
      { status: 400 },
    );
  }
}
