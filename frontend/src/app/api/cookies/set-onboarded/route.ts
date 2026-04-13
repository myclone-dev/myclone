import { cookies } from "next/headers";
import { NextResponse } from "next/server";

/**
 * API endpoint to set the hasOnboarded cookie for cross-domain authentication
 * This cookie is shared across *.myclone.is domains to enable unified CTA experience
 *
 * Matches the implementation from rappo:
 * /home/rx/Desktop/rappo/rappo/app/api/cookies/set-onboarded/route.ts
 */
export async function POST() {
  const cookieStore = await cookies();
  const response = NextResponse.json(
    { message: "Cookie set successfully" },
    { status: 200 },
  );

  // Determine if we're in production
  const isProduction = process.env.NODE_ENV === "production";

  // Cookie configuration for cross-domain sharing
  const cookieOptions = {
    name: "hasOnboarded",
    value: "true",
    path: "/",
    secure: isProduction, // HTTPS only in production (false for localhost)
    // httpOnly: false - Allow JavaScript access for client-side cookie reading
    sameSite: "lax" as const,
    domain: isProduction ? ".myclone.is" : undefined, // Cross-domain: .myclone.is in production, localhost in dev
    expires: new Date(Date.now() + 1000 * 60 * 60 * 24 * 365 * 2), // 2 years
  };

  // Set cookie in both cookieStore and response
  cookieStore.set(cookieOptions);
  response.cookies.set(cookieOptions);

  return response;
}
