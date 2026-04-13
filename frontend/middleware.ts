import { NextRequest, NextResponse } from "next/server";
import {
  isCustomDomain as checkIsCustomDomain,
  PLATFORM_DOMAINS,
} from "@/lib/constants/domains";

/**
 * Logging utility for middleware debugging
 * Logs are prefixed with timestamp and level for easy filtering
 */
function log(
  level: "INFO" | "WARN" | "ERROR" | "DEBUG",
  category: string,
  message: string,
  data?: Record<string, unknown>,
) {
  const timestamp = new Date().toISOString();
  const prefix = `[${timestamp}] [${level}] [${category}]`;

  if (data) {
    console.log(`${prefix} ${message}`, JSON.stringify(data, null, 2));
  } else {
    console.log(`${prefix} ${message}`);
  }
}

/**
 * Check if a hostname is a custom domain (not our platform)
 * Wrapper around shared isCustomDomain with logging
 */
function isCustomDomainWithLogging(hostname: string): boolean {
  const host = hostname.split(":")[0].toLowerCase();

  log("DEBUG", "CustomDomain", `Checking if "${host}" is a custom domain`, {
    originalHostname: hostname,
    hostWithoutPort: host,
    platformDomains: [...PLATFORM_DOMAINS],
  });

  const isCustom = checkIsCustomDomain(hostname);

  if (isCustom) {
    log(
      "INFO",
      "CustomDomain",
      `"${host}" IS a custom domain (not in platform list)`,
    );
  } else {
    log("DEBUG", "CustomDomain", `"${host}" is a platform domain`);
  }

  return isCustom;
}

/**
 * Cache for custom domain lookups to avoid repeated API calls
 * Key: domain, Value: { username, expiresAt }
 * USER-LEVEL: domains map to usernames, not personas
 */
const domainCache = new Map<string, { username: string; expiresAt: number }>();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Lookup custom domain from backend API
 * USER-LEVEL: Returns username for routing (no persona binding)
 */
async function lookupCustomDomain(
  domain: string,
): Promise<{ username: string } | null> {
  const startTime = Date.now();

  log("INFO", "Lookup", `Starting domain lookup for: ${domain}`);

  // Check cache first
  const cached = domainCache.get(domain);
  if (cached) {
    const isExpired = cached.expiresAt <= Date.now();
    const ttlRemaining = Math.max(0, cached.expiresAt - Date.now());

    log("DEBUG", "Lookup", `Cache entry found for ${domain}`, {
      username: cached.username || "(not found entry)",
      isExpired,
      ttlRemainingMs: ttlRemaining,
      expiresAt: new Date(cached.expiresAt).toISOString(),
    });

    if (!isExpired) {
      if (!cached.username) {
        log(
          "INFO",
          "Lookup",
          `Cache HIT (not found): ${domain} - returning null`,
          {
            duration: `${Date.now() - startTime}ms`,
          },
        );
        return null;
      }
      log("INFO", "Lookup", `Cache HIT: ${domain} -> ${cached.username}`, {
        duration: `${Date.now() - startTime}ms`,
      });
      return { username: cached.username };
    } else {
      log(
        "DEBUG",
        "Lookup",
        `Cache entry EXPIRED for ${domain}, will fetch fresh`,
      );
    }
  } else {
    log("DEBUG", "Lookup", `No cache entry for ${domain}`);
  }

  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;

    log("DEBUG", "Lookup", `Environment check`, {
      NEXT_PUBLIC_API_URL: apiUrl || "(not set)",
      nodeEnv: process.env.NODE_ENV,
    });

    if (!apiUrl) {
      log("ERROR", "Lookup", `NEXT_PUBLIC_API_URL is not configured!`, {
        availableEnvVars: Object.keys(process.env).filter((k) =>
          k.startsWith("NEXT_"),
        ),
      });
      return null;
    }

    // Remove trailing /api/v1 if present to avoid duplication
    const baseUrl = apiUrl.replace(/\/api\/v1\/?$/, "");
    const lookupUrl = `${baseUrl}/api/v1/custom-domains/lookup/${encodeURIComponent(domain)}`;

    log("INFO", "Lookup", `Making API request`, {
      domain,
      originalApiUrl: apiUrl,
      baseUrl,
      lookupUrl,
    });

    const fetchStartTime = Date.now();
    const response = await fetch(lookupUrl, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      // Short timeout for middleware
      signal: AbortSignal.timeout(3000),
    });
    const fetchDuration = Date.now() - fetchStartTime;

    log("DEBUG", "Lookup", `API response received`, {
      status: response.status,
      statusText: response.statusText,
      ok: response.ok,
      fetchDurationMs: fetchDuration,
      headers: {
        contentType: response.headers.get("content-type"),
        contentLength: response.headers.get("content-length"),
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        // Domain not found - cache this to avoid repeated lookups
        log(
          "INFO",
          "Lookup",
          `Domain NOT FOUND (404): ${domain} - caching negative result`,
          {
            cacheTtlMs: CACHE_TTL_MS,
            duration: `${Date.now() - startTime}ms`,
          },
        );
        domainCache.set(domain, {
          username: "",
          expiresAt: Date.now() + CACHE_TTL_MS,
        });
        return null;
      }

      // Try to get error details from response
      let errorBody = "";
      try {
        errorBody = await response.text();
      } catch {
        errorBody = "(could not read response body)";
      }

      log("ERROR", "Lookup", `API returned error status`, {
        domain,
        status: response.status,
        statusText: response.statusText,
        errorBody,
        duration: `${Date.now() - startTime}ms`,
      });
      return null;
    }

    const data = await response.json();

    log("DEBUG", "Lookup", `API response body`, {
      data,
    });

    // Backend returns: { domain, user_id, username }
    if (data && data.username) {
      // Cache successful lookup (USER-LEVEL: no persona_name, just username)
      log("INFO", "Lookup", `SUCCESS: ${domain} -> ${data.username}`, {
        userId: data.user_id,
        cacheTtlMs: CACHE_TTL_MS,
        duration: `${Date.now() - startTime}ms`,
      });

      domainCache.set(domain, {
        username: data.username,
        expiresAt: Date.now() + CACHE_TTL_MS,
      });

      return { username: data.username };
    }

    // Handle edge case: response OK but no username (shouldn't happen with new backend)
    log("WARN", "Lookup", `Unexpected response: 200 OK but no username`, {
      domain,
      responseData: data,
      duration: `${Date.now() - startTime}ms`,
    });
    return null;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    const errorName = error instanceof Error ? error.name : "Unknown";

    log("ERROR", "Lookup", `Exception during lookup`, {
      domain,
      errorName,
      errorMessage,
      isTimeout:
        errorName === "TimeoutError" || errorMessage.includes("timeout"),
      isNetworkError:
        errorMessage.includes("fetch") || errorMessage.includes("ECONNREFUSED"),
      duration: `${Date.now() - startTime}ms`,
    });
    return null;
  }
}

export async function middleware(request: NextRequest) {
  const startTime = Date.now();
  const requestId = Math.random().toString(36).substring(7);
  const { pathname, search } = request.nextUrl;
  const hostname = request.headers.get("host") || "";
  const method = request.method;

  log("INFO", "Middleware", `>>> Request START [${requestId}]`, {
    method,
    hostname,
    pathname,
    search: search || "(none)",
    fullUrl: request.url,
    userAgent: request.headers.get("user-agent")?.substring(0, 100),
  });

  // ============================================
  // CUSTOM DOMAIN ROUTING
  // ============================================
  const isCustom = isCustomDomainWithLogging(hostname);

  log("INFO", "Middleware", `Custom domain check result`, {
    requestId,
    hostname,
    isCustomDomain: isCustom,
  });

  if (isCustom) {
    // Skip API routes, static files, and Next.js internals
    const shouldSkip =
      pathname.startsWith("/api") ||
      pathname.startsWith("/_next") ||
      pathname.startsWith("/embed") ||
      pathname.includes(".");

    if (shouldSkip) {
      log(
        "DEBUG",
        "Middleware",
        `Skipping custom domain routing (static/api path)`,
        {
          requestId,
          pathname,
          reason: pathname.startsWith("/api")
            ? "API route"
            : pathname.startsWith("/_next")
              ? "Next.js internal"
              : pathname.startsWith("/embed")
                ? "Embed route"
                : "Has file extension",
        },
      );
      return NextResponse.next();
    }

    log("INFO", "Middleware", `Processing custom domain request`, {
      requestId,
      hostname,
      pathname,
    });

    // Lookup the custom domain to get the associated username
    const domainToLookup = hostname.split(":")[0].toLowerCase();
    log("DEBUG", "Middleware", `Looking up domain`, {
      requestId,
      originalHostname: hostname,
      domainToLookup,
    });

    const lookupResult = await lookupCustomDomain(domainToLookup);

    if (lookupResult) {
      // USER-LEVEL ROUTING:
      // - example.com/ → /username (shows default persona chat)
      // - example.com/persona-name → /username/persona-name (specific persona chat)

      let targetPath: string;
      if (pathname === "/" || pathname === "") {
        targetPath = `/${lookupResult.username}`;
      } else {
        targetPath = `/${lookupResult.username}${pathname}`;
      }

      log("INFO", "Middleware", `REWRITING URL for custom domain`, {
        requestId,
        originalHostname: hostname,
        originalPathname: pathname,
        username: lookupResult.username,
        targetPath,
        duration: `${Date.now() - startTime}ms`,
      });

      const url = request.nextUrl.clone();
      url.pathname = targetPath;

      // Add custom domain headers for the page to know context
      const response = NextResponse.rewrite(url);
      response.headers.set("x-custom-domain", hostname);
      response.headers.set("x-custom-domain-username", lookupResult.username);
      response.headers.set("x-request-id", requestId);

      log("INFO", "Middleware", `<<< Request END [${requestId}] - REWRITE`, {
        targetPath,
        duration: `${Date.now() - startTime}ms`,
      });

      return response;
    }

    // Domain not found or not active - let the page handle it
    // The OnboardingGuard will recognize custom domains and not redirect
    log("WARN", "Middleware", `Custom domain lookup FAILED - passing through`, {
      requestId,
      hostname,
      pathname,
      result: "Domain not configured or not active",
      duration: `${Date.now() - startTime}ms`,
    });

    // Pass through - the page will show appropriate content
    // OnboardingGuard won't redirect because it detects custom domain
    return NextResponse.next();
  }

  // ============================================
  // STANDARD AUTH MIDDLEWARE
  // ============================================
  const isAuthPage =
    pathname.startsWith("/login") || pathname.startsWith("/signup");
  const isDashboardRoute = pathname.startsWith("/dashboard");

  log("DEBUG", "Middleware", `Auth check`, {
    requestId,
    pathname,
    isAuthPage,
    isDashboardRoute,
  });

  // Try to get token from any possible cookie name
  const tokenSources = {
    myclone_token: request.cookies.get("myclone_token")?.value,
    access_token: request.cookies.get("access_token")?.value,
    token: request.cookies.get("token")?.value,
    auth_token: request.cookies.get("auth_token")?.value,
  };

  const token =
    tokenSources.myclone_token ||
    tokenSources.access_token ||
    tokenSources.token ||
    tokenSources.auth_token;

  log("DEBUG", "Middleware", `Token check`, {
    requestId,
    hasToken: !!token,
    tokenSource: token
      ? Object.entries(tokenSources).find(([, v]) => v === token)?.[0]
      : "none",
    tokenPreview: token ? `${token.substring(0, 10)}...` : "(none)",
  });

  // Redirect unauthenticated users from protected routes to login
  if (isDashboardRoute && !token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);

    log(
      "INFO",
      "Middleware",
      `<<< Request END [${requestId}] - REDIRECT to login (unauthenticated)`,
      {
        from: pathname,
        to: loginUrl.toString(),
        duration: `${Date.now() - startTime}ms`,
      },
    );

    return NextResponse.redirect(loginUrl);
  }

  // Redirect authenticated users away from auth pages to dashboard
  if (token && isAuthPage) {
    log(
      "INFO",
      "Middleware",
      `<<< Request END [${requestId}] - REDIRECT to dashboard (already authenticated)`,
      {
        from: pathname,
        to: "/dashboard",
        duration: `${Date.now() - startTime}ms`,
      },
    );

    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  log("INFO", "Middleware", `<<< Request END [${requestId}] - PASS THROUGH`, {
    pathname,
    duration: `${Date.now() - startTime}ms`,
  });

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files (public folder)
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\..*|public).*)",
  ],
};
