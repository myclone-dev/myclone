# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development

```bash
bun dev          # Start development server with Turbopack
bun run build    # Production build with Turbopack
bun start        # Start production server
```

### Code Quality

```bash
bun type-check   # Run TypeScript compiler check (no emit)
bun lint         # Run ESLint
bun lint:fix     # Auto-fix ESLint errors
bun format       # Format code with Prettier
bun format:check # Check formatting without changes
```

**IMPORTANT:** Before adding code to staging, ALWAYS run these commands to ensure code quality:

```bash
# Run linter with auto-fix
bun lint:fix

# Run formatter
bun format

# Run type check
bun type-check
```

The project uses Husky with lint-staged to automatically run ESLint and Prettier on staged files during pre-commit. If the pre-commit hook fails, fix the errors and try committing again.

### UI Components (shadcn/ui)

```bash
bunx shadcn@latest add <component-name>  # Add new shadcn component
# Example: bunx shadcn@latest add toast
```

**IMPORTANT:** Never manually create shadcn/ui components. Always use the CLI to add them. Components are configured with:

- Style: new-york
- Base color: neutral
- CSS variables enabled
- Icon library: lucide-react

## Architecture Overview

### Tailwind CSS v4 Styling Rules (CRITICAL)

This project uses **Tailwind CSS v4** with a CSS-first configuration approach:

**IMPORTANT: Never hardcode color values in component code. Always use theme colors from globals.css.**

**Note:** This project uses Tailwind v4, which has NO `tailwind.config.js` file. All theme configuration is in `src/app/globals.css` using the `@theme` directive. Colors defined in `@theme` with `--color-` prefix automatically become Tailwind utility classes (e.g., `--color-ai-gold` → `bg-ai-gold`).

#### Defining Custom Colors

All custom colors must be defined in `src/app/globals.css` within the `@theme` directive:

```css
@theme {
  --color-yellow-bright: #ffe065;
  --color-yellow-light: #fff4cc;
  --color-peach-cream: #fff8f2;
}
```

#### Using Custom Colors

Once defined in `@theme`, colors become available as Tailwind utility classes:

```tsx
// ✅ CORRECT - Use theme color class
<div className="bg-peach-cream text-yellow-bright" />

// ❌ WRONG - Never hardcode color values
<div className="bg-[#fff8f2]" />
<div style={{ backgroundColor: "#fff8f2" }} />
```

#### Adding New Colors

1. Add color to `@theme` block in `src/app/globals.css` with `--color-` prefix
2. Use the color name (without `--color-` prefix) in Tailwind classes
3. Restart dev server to ensure Tailwind picks up the new color

**Example:**

```css
/* In src/app/globals.css */
@theme {
  --color-brand-blue: #1e40af;
}
```

```tsx
/* In your component */
<button className="bg-brand-blue hover:bg-brand-blue/80">Click me</button>
```

#### Theme Colors (CRITICAL)

**IMPORTANT: The primary brand color is GOLD/YELLOW (#FFC329), NOT brown.**

**Official Theme Color Palette:**

```css
/* From src/app/globals.css @theme directive */

/* Primary Brand Color - USE THIS FOR SELECTED STATES */
--color-ai-gold: #ffc329; /* Primary brand color */
--primary: oklch(0.82 0.15 85); /* Same as #ffc329 in OKLCH */

/* Supporting Brand Colors */
--color-yellow-bright: #ffe065; /* Bright accent */
--color-yellow-light: #fff4cc; /* Light background/hover */

/* Background Colors */
--color-peach-cream: #fff8f2; /* Soft background */
--color-peach-light: #fef6f0; /* Lighter background */
--color-peach-bright: #fff0e5; /* Bright background */

/* Secondary Colors (NOT PRIMARY) */
--color-ai-brown: #b06b30; /* Accent only, NEVER for primary UI */
```

**Usage Rules:**

1. **Selected/Active States** - ALWAYS use `bg-ai-gold`:

   ```tsx
   // ✅ CORRECT - Use theme class
   <button className={isActive ? "bg-ai-gold text-gray-900" : "bg-gray-100"} />

   // ❌ WRONG - Never hardcode hex
   <button className={isActive ? "bg-[#ffc329] text-gray-900" : "bg-gray-100"} />

   // ❌ WRONG - Never use black, brown, or slate-900 for selected states
   <button className={isActive ? "bg-black text-white" : "bg-gray-100"} />
   <button className={isActive ? "bg-ai-brown text-white" : "bg-gray-100"} />
   <button className={isActive ? "bg-slate-900 text-white" : "bg-gray-100"} />
   ```

2. **Tab Toggles** - Use `bg-ai-gold` with dark text:

   ```tsx
   <button
     className={
       isActive ? "bg-ai-gold text-gray-900 shadow-md" : "text-gray-600"
     }
   />
   ```

3. **Buttons** - Primary buttons use yellow-bright:

   ```tsx
   <button className="bg-yellow-bright hover:bg-yellow-bright/90 text-gray-900" />
   ```

4. **Backgrounds** - Use yellow-light or peach variants:

   ```tsx
   <div className="bg-yellow-light hover:bg-yellow-light/50" />
   <div className="bg-peach-cream" />
   ```

5. **Brown Usage** - ONLY for accents, NEVER for primary UI:

   ```tsx
   // ✅ OK - Used as accent in specific contexts
   <div className="border-ai-brown" />

   // ❌ WRONG - Never for selected states
   <button className="bg-ai-brown text-white" />
   ```

**Common Mistakes to Avoid:**

- ❌ Using `bg-black`, `bg-slate-900`, or `bg-gray-900` for selected states
- ❌ Using `bg-ai-brown` for primary UI elements (tabs, active buttons)
- ❌ Hardcoding hex values like `bg-[#ffc329]` instead of using `bg-ai-gold`
- ❌ Hardcoding `#b06b30` (brown) instead of using theme gold
- ✅ Always use `bg-ai-gold` for selected/active states (defined in `@theme`)
- ✅ Use `text-gray-900` for text on gold backgrounds (better contrast than white)

### State Management Strategy (CRITICAL)

This project uses a **strict separation** between client UI state and server data:

1. **Zustand** - Client UI state ONLY
   - Auth state (user, token, isAuthenticated) in `src/store/auth.store.ts`
   - UI state (modals, sidebar) in `src/store/ui.store.ts`
   - **Never use Zustand for server/API data**

2. **TanStack Query v5** - Server/API data ONLY
   - All server data fetching and caching
   - Mutations for POST/PUT/DELETE operations
   - Configured in `src/app/providers.tsx`
   - Organized in `src/lib/queries/{domain}/` structure
   - See `src/lib/queries/expert/` for example patterns

### Server vs Client Components

- **Default: Server Components** - No `'use client'` directive needed
- **Only use `'use client'` when you need:**
  - React hooks (useState, useEffect, etc.)
  - Event handlers (onClick, onChange, etc.)
  - Browser APIs (localStorage, window, etc.)
  - Zustand stores or TanStack Query hooks

### Environment Variables

- **Type-safe and validated** using `@t3-oss/env-nextjs` in `src/env.ts`
- **Never use `process.env` directly** - always import from `@/env`
- `next.config.ts` imports `src/env.ts` to validate at build time
- Client variables must start with `NEXT_PUBLIC_`
- Local environment: `.env.local` (git-ignored)
- Template: `.env.example` (committed)

**Adding new variables:**

1. Add schema to `src/env.ts` (server or client)
2. Add to `runtimeEnv` mapping
3. Add to `.env.local` with actual value
4. Add to `.env.example` without value

### API Client Architecture

Located in `src/lib/api/client.ts`:

- Axios instance with base URL from typed env
- **Request interceptor:** Auto-adds JWT token from localStorage
- **Response interceptor:** Auto-handles 401 (clears auth, redirects to /login)
- **Browser check:** Always checks `typeof window !== "undefined"` before localStorage access

**Usage pattern:**

```typescript
import { api } from "@/lib/api/client";

// In a TanStack Query hook
const { data } = await api.get("/endpoint");
```

### Authentication Flow

1. User logs in via `useLogin()` mutation (TanStack Query)
2. On success: Token stored in:
   - localStorage (key: `auth_token`) for API client
   - Zustand store (via `persist` middleware) for UI state
3. All subsequent API calls include token via interceptor
4. On 401: Auto-logout and redirect to /login

### File Structure Conventions

```
src/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Root layout (wraps with Providers)
│   ├── page.tsx           # Homepage (Server Component)
│   ├── error.tsx          # Error boundary (Client Component)
│   ├── loading.tsx        # Loading UI (Server Component)
│   └── providers.tsx      # Client providers (TanStack Query setup)
├── components/
│   ├── ui/                # shadcn/ui components (CLI-generated)
│   └── layouts/           # Layout components (Header, Footer)
├── lib/
│   ├── queries/           # TanStack Query hooks (domain-organized)
│   │   ├── error.ts      # ApiException class
│   │   └── expert/       # Expert domain queries
│   │       ├── index.ts              # Exports all hooks & types
│   │       ├── interface.ts          # TypeScript interfaces
│   │       ├── useLinkedInSearch.ts  # LinkedIn search query/mutation
│   │       └── useExpertOnboardingSubmit.ts
│   ├── utils.ts          # cn() utility for className merging
│   └── api/
│       └── client.ts     # Axios instance with interceptors
├── store/                # Zustand stores (client UI state only)
└── env.ts                # Environment validation (@t3-oss/env-nextjs)
```

### Import Aliases

- `@/components` → `src/components`
- `@/lib` → `src/lib`
- `@/store` → `src/store`
- `@/env` → `src/env.ts`

### TanStack Query Patterns

**IMPORTANT:** All TanStack Query hooks must be organized in `src/lib/queries/{domain}/` with the following structure:

```
lib/queries/{domain}/
├── index.ts              # Export all hooks and types
├── interface.ts          # All TypeScript interfaces
└── use{Feature}.ts       # Hooks with separate fetch functions
```

**Query keys convention:**

```typescript
['resource', id?, filters?]
// Examples:
['linkedin-search', { name, company, role }]
['expert-onboarding']
```

**Hook pattern (in `src/lib/queries/{domain}/use{Feature}.ts`):**

```typescript
import { useMutation, useQuery } from "@tanstack/react-query";
import { env } from "@/env";
import type { RequestType, ResponseType } from "./interface";

// 1. Separate fetch function (easier to test)
const fetchResource = async (params: RequestType): Promise<ResponseType> => {
  const response = await fetch(`${env.NEXT_PUBLIC_API_URL}/endpoint`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || "Failed to fetch resource");
  }

  return response.json();
};

// 2. Query key generator (for cache management)
export const getResourceQueryKey = (params: RequestType) => {
  return ["resource", params];
};

// 3. Query hook
export const useResourceQuery = (
  params: RequestType | null,
  options?: { enabled?: boolean },
) => {
  return useQuery({
    queryKey: params ? getResourceQueryKey(params) : ["resource", "disabled"],
    queryFn: () => {
      if (!params) throw new Error("Params required");
      return fetchResource(params);
    },
    enabled: options?.enabled !== false && !!params,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
};

// 4. Mutation hook (if needed)
export const useResourceMutation = () => {
  return useMutation({
    mutationFn: fetchResource,
    onError: (error: Error) => {
      console.error("Resource mutation failed:", error.message);
    },
  });
};
```

**Usage in components:**

```typescript
import { useResourceQuery, type RequestType } from "@/lib/queries/{domain}";

// All types and hooks from same import
const { data, isLoading } = useResourceQuery(params);
```

### UI Component Patterns

**shadcn/ui components** (in `src/components/ui/`):

- Generated via CLI: `pnpm dlx shadcn@latest add <name>`
- Use `cn()` utility from `@/lib/utils` for className merging
- All use Radix UI primitives
- Styled with Tailwind CSS using CSS variables

**Custom components:**

- Use forwardRef for form integration
- Accept `className` prop and merge with `cn()`
- Follow TypeScript best practices (type inference)

### Pre-commit Hooks

Configured with Husky + lint-staged:

- Auto-runs ESLint with `--fix`
- Auto-runs Prettier formatting
- Only on staged files
- Blocks commit if checks fail

## Key Dependencies

- **Next.js 15.5.4** - App Router with Turbopack
- **React 19.1.0** - Server Components enabled
- **TypeScript 5** - Strict mode
- **Tailwind CSS v4** - Utility-first CSS
- **shadcn/ui** - Radix UI + Tailwind components
- **TanStack Query v5** - Server state management
- **Zustand 5** - Client UI state management
- **@t3-oss/env-nextjs** - Type-safe environment variables
- **Zod 4** - Runtime validation
- **Axios** - HTTP client with interceptors
- **React Hook Form** - Form management
- **lucide-react** - Icon library

## Critical Rules

1. **Never hardcode color values** - Always define colors in `@theme` block in `globals.css` and use Tailwind classes (e.g., `bg-peach-cream` NOT `bg-[#fff8f2]`)
2. **Primary brand color is GOLD (#FFC329), NOT brown** - Selected/active states MUST use gold, never black/brown/slate-900. See "Theme Colors" section.
3. **Never use Zustand for server data** - Use TanStack Query
4. **Never manually create shadcn components** - Use CLI
5. **Never use `process.env` directly** - Import from `@/env`
6. **Never access localStorage without browser check** - `typeof window !== "undefined"`
7. **Default to Server Components** - Only add `'use client'` when necessary
8. **Always use `cn()` utility** - For className merging with Tailwind
9. **Environment validation happens at build time** - via `next.config.ts` import
10. **Always organize queries in `lib/queries/{domain}/`** - See `docs/QUERY_ARCHITECTURE.md`
11. **Always use React Hook Form + Zod for forms** - See "Form Management & Validation" section
12. **Keep components under 300 lines** - See "Component Architecture Best Practices" section

## Form Management & Validation (CRITICAL)

**ALWAYS use React Hook Form + Zod for:**

- Forms with 2+ fields
- Forms requiring validation
- Any form that submits to an API

**Pattern:**

- Define Zod schema first (infer types with `z.infer<typeof schema>`)
- Use `zodResolver` with `useForm`
- Use shadcn Form components (`FormField`, `FormItem`, `FormLabel`, `FormMessage`)
- Never mix manual `useState` with React Hook Form fields

**Common Zod Patterns:**

- Required: `z.string().min(1, "Required")`
- Email: `z.string().email()`
- URL: `z.string().url()`
- Number range: `z.number().min(1).max(100)`
- Optional with default: `z.string().optional().default("value")`
- Enum: `z.enum(["option1", "option2"])`
- Refinements: `.refine((data) => condition, { message: "Error", path: ["field"] })`

## Component Architecture Best Practices (CRITICAL)

**Rules:**

- Keep components under 300 lines (extract if larger)
- Extract complex state to custom hooks (`useFeatureState`)
- Extract save/mutation logic to hooks (`useFeatureSave`)
- Use feature-based folder structure for complex components
- Single Responsibility Principle - each file does ONE thing

**Complex Component Structure:**

```
components/MyFeature/
├── index.tsx                 # Main component
├── types.ts                  # All interfaces
├── hooks/
│   ├── useMyFeatureState.ts  # State management
│   └── useMyFeatureSave.ts   # Save/mutation logic
├── components/               # Sub-components
│   ├── SubComponent1.tsx
│   └── SubComponent2.tsx
└── utils/
    ├── validation.ts         # Validation functions
    ├── formatting.ts         # Formatting utilities
    └── constants.ts          # Magic numbers, defaults
```

**Reference Implementation:**

- See `src/components/dashboard/personas/PersonaSettingsDialog/`
- Refactored from 2,594 lines → 21 files (avg 134 lines each)
- Full details: `docs/refactoring/PERSONA_SETTINGS_REFACTORING.md`

**Code Quality Checklist (Before Committing):**

- [ ] No file over 300 lines
- [ ] All forms use React Hook Form + Zod
- [ ] Complex state in custom hooks
- [ ] Repeated UI patterns extracted to reusable components
- [ ] Constants, validation, formatting in separate files
- [ ] No `any` types
- [ ] Ran: `bun lint:fix && bun format && bun type-check`

## V1 Dashboard (NEW)

### Overview

Complete dashboard implementation for managing Expert Clone platform:

**Routes:**

- `/dashboard` - Dashboard home (redirects to Knowledge Library)
- `/dashboard/knowledge` - Knowledge Library (LinkedIn, Twitter, Website, PDF uploads)
- `/dashboard/widgets` - Widget Management (embed code generator, customizer, preview)
- `/dashboard/profile` - User Profile management
- `/dashboard/conversations` - Conversation Center (placeholder, needs backend API)

### Knowledge Library Features

- LinkedIn profile import with URL validation
- Twitter profile import with username handling
- Website scraping with configurable page limits (1-100 pages)
- PDF drag-and-drop upload (max 10MB)
- Real-time scraping job status with auto-polling (10s interval)
- Job history with status badges and statistics
- Toast notifications for all actions

### Widget Management Features

- **Embed Code Generator** - Ready-to-use script tag with expert username
- **Visual Customizer** - Interactive configuration with live code generation:
  - Position selector (4 corners)
  - Primary color picker with hex input
  - Bubble button text customization
  - Voice chat toggle
  - Welcome message and input placeholder
- **Preview & Testing** - Links to test page and public profile
- **Token Management** - Create, view, and revoke widget authentication tokens
- Copy-to-clipboard functionality for generated embed code
- Widget features overview (text chat, voice, email capture, responsive, etc.)
- Integration examples and use cases

### Widget/Embed System Architecture

The widget system consists of two main parts:

**1. SDK Loader** (`myclone-embed.js`)

- Loaded by customers on their website
- Creates iframe and manages postMessage communication
- Passes configuration via URL parameters
- Built with: `bun run build:embed` (Vite config: `vite.embed.config.ts`)
- Output: `public/embed/myclone-embed.js` (7KB minified)

**2. Embed App** (`assets/app.js`, `assets/app.css`)

- React app running inside iframe
- Contains full chat interface (text + voice)
- Receives config from parent via URL params
- Built with: `bun run build:embed` (Vite config: `vite.embed-app.config.ts`)
- Output: `public/embed/assets/app.js` (937KB minified)

**Environment Variables for Embed:**

- Env vars are injected at build time via `loadEnv()` in Vite configs
- At runtime, env values can be overridden via `window.EMBED_API_URL` and `window.EMBED_LIVEKIT_URL`
- The `src/env.ts` uses getters to check window globals first (for embed context)
- Shared config in `vite.embed.shared.ts` to avoid duplication

**Integration Examples:**

- Next.js: `src/embed/examples/nextjs-integration.tsx`
- React: `src/embed/examples/react-integration.tsx`
- Vanilla HTML: `src/embed/examples/vanilla-html.html`
- Astro: `src/embed/examples/astro-integration.astro`

**Widget Token Authentication:**

- Users create named tokens in dashboard (`/dashboard/widgets` → Tokens tab)
- Tokens are JWT-based and required for all widget API calls
- Backend endpoints: `/users/me/widget-tokens` (GET, POST, DELETE)
- See `src/lib/queries/users/useWidgetToken.ts` for implementation

### API Integration

**Knowledge Library** (`src/lib/queries/knowledge/`):

- `POST /api/v1/scraping/linkedin` - Queue LinkedIn scraping
- `POST /api/v1/scraping/twitter` - Queue Twitter scraping
- `POST /api/v1/scraping/website` - Queue website scraping
- `POST /api/v1/ingestion/process-pdf-data` - Upload and process PDF
- `GET /api/v1/scraping/status/{user_id}` - Get scraping jobs (polling)

**Webhooks** (`src/lib/queries/webhooks/`):

- `POST /api/v1/personas/{persona_id}/webhook` - Create/replace webhook config
- `GET /api/v1/personas/{persona_id}/webhook` - Get webhook config
- `PATCH /api/v1/personas/{persona_id}/webhook` - Update webhook (partial)
- `DELETE /api/v1/personas/{persona_id}/webhook` - Delete webhook
- `GET /api/v1/personas/webhook/health` - Health check (public endpoint)

**Webhook Features:**

- One webhook per persona (create replaces existing)
- HTTPS URLs only (HTTP blocked)
- Supported providers: Zapier, Make, n8n, Slack, Discord, custom endpoints
- Supported events: `conversation.finished` (sent when voice conversation ends)
- Optional webhook secret for signature verification
- SSRF protection blocks private IPs

**User & Profile** (`src/lib/queries/users/`):

- `GET /api/v1/users/me` - Get current user profile

### Missing Backend APIs (For Conversations)

These endpoints need to be implemented on the backend:

- `GET /api/v1/users/{user_email}/conversations` - List user conversations
- `GET /api/v1/conversations/{conversation_id}` - Get conversation details
- `GET /api/v1/personas/{persona_id}/conversations` - List persona conversations

See `docs/plan/V1_DASHBOARD_IMPLEMENTATION.md` for complete implementation details.

## Error Monitoring & Performance Tracking (Sentry)

### Overview

This project uses **Sentry** for comprehensive error monitoring, performance tracking, and user session replay. All errors from API calls, user actions, and critical flows are automatically tracked.

### Configuration Files

- `sentry.client.config.ts` - Client-side Sentry initialization
- `sentry.server.config.ts` - Server-side Sentry with Slack webhook integration
- `sentry.edge.config.ts` - Edge runtime Sentry configuration
- `instrumentation.ts` - Next.js instrumentation hook
- `next.config.ts` - Wrapped with `withSentryConfig()` for build-time integration

### Environment Variables

**Required for error tracking:**

```bash
NEXT_PUBLIC_SENTRY_DSN=https://your-dsn@sentry.io/project-id
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development  # development | staging | production
```

**Optional for source maps upload:**

```bash
SENTRY_ORG=your-org-slug
SENTRY_PROJECT=your-project-slug
SENTRY_AUTH_TOKEN=your-auth-token
```

**Optional for Slack notifications:**

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Automatic Error Tracking

**API Client Interceptor** (`src/lib/api/client.ts`):

- Automatically tracks all API errors (excluding 401 and 404)
- 5xx errors logged as `error` level
- 4xx errors logged as `warning` level
- Includes request/response context, endpoint, method, and status code

**Error Levels:**

- Server errors (5xx): `error` level → triggers Slack notification
- Client errors (4xx, except 401/404): `warning` level
- Auth errors (401): Not tracked (expected behavior)
- Not found (404): Not tracked (expected behavior)

### Manual Error Tracking

Use the monitoring utilities in `src/lib/monitoring/sentry.ts`:

#### Track User Actions

```typescript
import { trackUserAction } from "@/lib/monitoring/sentry";

trackUserAction("linkedin_profile_imported", {
  profileUrl: url,
  userId: user.id,
});
```

#### Track Dashboard Operations

```typescript
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

// Start operation
trackDashboardOperation("pdf_upload", "started", {
  fileName: file.name,
  fileSize: file.size,
});

// Success
trackDashboardOperation("pdf_upload", "success", {
  fileName: file.name,
  processingTime: 1234,
});

// Error
trackDashboardOperation("pdf_upload", "error", {
  fileName: file.name,
  error: error.message,
});
```

**Available operations:**

- `linkedin_import`
- `twitter_import`
- `website_scrape`
- `pdf_upload`
- `widget_token_create`
- `widget_token_revoke`
- `webhook_create`
- `webhook_update`
- `webhook_delete`
- `persona_create`
- `persona_update`
- `persona_delete`
- `profile_update`
- `voice_clone_create`
- `conversation_view`

#### Track API Operations with Performance

```typescript
import { trackApiOperation } from "@/lib/monitoring/sentry";

const result = await trackApiOperation(
  "linkedin_search",
  async () => {
    return await api.post("/linkedin/search", data);
  },
  { query: searchQuery },
);
```

#### Track File Uploads

```typescript
import { trackFileUpload } from "@/lib/monitoring/sentry";

trackFileUpload("pdf", "started", {
  fileName: file.name,
  fileSize: file.size,
});

trackFileUpload("pdf", "progress", {
  fileName: file.name,
  progress: 50,
});

trackFileUpload("pdf", "success", {
  fileName: file.name,
});

trackFileUpload("pdf", "error", {
  fileName: file.name,
  error: "Upload failed: Network error",
});
```

#### Track Form Events

```typescript
import { trackFormEvent } from "@/lib/monitoring/sentry";

// Form submission
trackFormEvent("persona_creation_form", "submit");

// Validation errors
trackFormEvent("persona_creation_form", "validation_error", {
  name: "Name is required",
  description: "Description must be at least 10 characters",
});

// Success
trackFormEvent("persona_creation_form", "success");
```

#### Track LiveKit Events

```typescript
import { trackLiveKitEvent } from "@/lib/monitoring/sentry";

trackLiveKitEvent("session_start", {
  roomName: room.name,
  personaId: persona.id,
});

trackLiveKitEvent("connection_error", {
  error: error.message,
  roomName: room.name,
});

trackLiveKitEvent("session_end", {
  duration: sessionDuration,
});
```

#### Set User Context

```typescript
import { setUserContext, clearUserContext } from "@/lib/monitoring/sentry";

// On login
setUserContext({
  id: user.id,
  email: user.email,
  username: user.username,
});

// On logout
clearUserContext();
```

### Best Practices

1. **Track Critical User Flows:**
   - Knowledge Library uploads (LinkedIn, Twitter, Website, PDF)
   - Widget token management (create, revoke)
   - Webhook configuration (create, update, delete)
   - Persona operations (create, update, delete)
   - Voice clone creation
   - Profile updates

2. **Use Appropriate Tracking Methods:**
   - `trackDashboardOperation()` for main dashboard features
   - `trackApiOperation()` for performance-sensitive API calls
   - `trackFileUpload()` for all file upload operations
   - `trackFormEvent()` for form submissions and validation
   - `trackLiveKitEvent()` for real-time voice/video sessions

3. **Don't Over-Track:**
   - API client already tracks all errors automatically
   - Don't manually track common errors (use auto-tracking)
   - Focus on business-critical operations and user flows

4. **Include Meaningful Metadata:**
   - Always include relevant context (user ID, file name, operation type)
   - Use consistent naming for operations
   - Include error messages and stack traces when available

5. **Slack Notifications:**
   - Only `error` level events trigger Slack notifications
   - Server errors (5xx) automatically notify Slack
   - Manual `trackDashboardOperation(..., "error")` sends to Slack
   - Includes error message, environment, event ID, and URL

### Session Replay

- **Production:** 10% of normal sessions, 100% of error sessions
- **Development:** 10% of sessions
- **Privacy:** All text masked, all media blocked
- View replays in Sentry dashboard to see user interactions before errors

### Performance Monitoring

- **Sample Rate:** 100% in development, 10% in production
- Tracks API response times, page load times, and custom operations
- Use `trackApiOperation()` for custom performance tracking

### Source Maps

- Automatically uploaded during production builds (requires `SENTRY_AUTH_TOKEN`)
- Maps are hidden from client bundles (`hideSourceMaps: true`)
- Provides readable stack traces in Sentry dashboard

### Tunneling

- All Sentry requests routed through `/monitoring` to bypass ad-blockers
- Configured in `next.config.ts` with `tunnelRoute: "/monitoring"`

### Adding Sentry to New Features

When adding a new dashboard feature, follow this pattern:

```typescript
"use client";

import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { useMutation } from "@tanstack/react-query";

export function useNewFeature() {
  return useMutation({
    mutationFn: async (data) => {
      // Track start
      trackDashboardOperation("new_feature", "started", {
        dataSize: data.length,
      });

      try {
        const result = await api.post("/new-feature", data);

        // Track success
        trackDashboardOperation("new_feature", "success", {
          resultId: result.id,
        });

        return result;
      } catch (error) {
        // Track error (also auto-tracked by API client)
        trackDashboardOperation("new_feature", "error", {
          error: error.message,
        });
        throw error;
      }
    },
  });
}
```

### Common Errors to Track

✅ **DO track these:**

- Knowledge source upload failures
- Widget token creation/revocation errors
- Webhook configuration errors (create, update, delete)
- Persona creation/update/deletion errors
- File upload failures (PDF, audio, images)
- LiveKit connection errors
- Form validation errors
- Payment/subscription errors

❌ **DON'T track these (auto-tracked):**

- API client errors (5xx, 4xx except 401/404)
- Network timeouts
- CORS errors
- General fetch failures

## Internationalization (i18n) - Public-Facing Pages (CRITICAL)

This project uses **i18next + react-i18next** for internationalization on public-facing pages only (persona pages and widget/embed pages). Dashboard pages are NOT translated.

### Supported Languages

14 languages are supported: `en`, `es`, `fr`, `ar`, `de`, `it`, `pt`, `nl`, `pl`, `hi`, `ja`, `ko`, `el`, `cs`

### Translation Files Location

All translation files are in `src/i18n/locales/`:

```
src/i18n/locales/
├── en.json  # English (default/fallback)
├── es.json  # Spanish
├── fr.json  # French
├── ar.json  # Arabic (RTL)
├── de.json  # German
├── it.json  # Italian
├── pt.json  # Portuguese
├── nl.json  # Dutch
├── pl.json  # Polish
├── hi.json  # Hindi
├── ja.json  # Japanese
├── ko.json  # Korean
├── el.json  # Greek
└── cs.json  # Czech
```

### Language Selection

- **Language is determined by persona settings only** (set by persona owner)
- **Default language is English** if not specified
- Dashboard/profile pages do NOT have language selection UI
- Widget receives language via URL parameter `lang`

### Adding New Strings to Public-Facing Pages (CRITICAL)

**IMPORTANT:** When adding ANY hardcoded strings to public-facing pages (persona pages, widget/embed components), you MUST:

1. **Never hardcode user-visible strings** - Always use translation keys
2. **Add the translation key to ALL 14 locale files** - Not just English
3. **Use the `useTranslation` hook** from react-i18next

**Pattern:**

```typescript
import { useTranslation } from "react-i18next";

function MyComponent() {
  const { t } = useTranslation();

  return (
    <div>
      {/* ✅ CORRECT - Use translation key */}
      <p>{t("widget.aiPowered")}</p>
      <button aria-label={t("common.close")}>{t("common.submit")}</button>

      {/* ❌ WRONG - Never hardcode strings */}
      <p>AI powered digital clone</p>
      <button aria-label="Close">Submit</button>
    </div>
  );
}
```

### Adding New Translation Keys

1. **Add key to `en.json` first** with the English text
2. **Add key to ALL other 13 locale files** with proper translations
3. **Follow existing key naming conventions:**
   - `common.*` - Shared UI strings (loading, error, cancel, etc.)
   - `chat.*` - Chat-related strings
   - `voice.*` - Voice chat strings
   - `session.*` - Session management strings
   - `email.*` - Email capture strings
   - `widget.*` - Widget/embed specific strings
   - `settings.*` - Settings strings

**Example - Adding a new key:**

```json
// en.json
{
  "widget": {
    "newFeature": "New Feature"
  }
}

// es.json
{
  "widget": {
    "newFeature": "Nueva Función"
  }
}

// fr.json
{
  "widget": {
    "newFeature": "Nouvelle Fonctionnalité"
  }
}
// ... and so on for all 14 locales
```

### Public-Facing Pages (Use Translations)

These pages/components MUST use translations:

- `src/app/[username]/page.tsx` - Public persona page
- `src/app/[username]/[persona]/page.tsx` - Specific persona page
- `src/embed/app/*` - All embed/widget components
- `src/components/expert/*` - Expert chat components (used in public pages)

### Dashboard Pages (No Translations Needed)

These pages are NOT translated (English only):

- `src/app/dashboard/*` - All dashboard pages
- `src/components/dashboard/*` - Dashboard components

### RTL Support

Arabic (`ar`) is a right-to-left language. The `I18nProvider` automatically adds `dir="rtl"` to the document when Arabic is selected.

## Documentation

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Application architecture patterns
- **[TECH_STACK.md](docs/TECH_STACK.md)** - Technology stack overview
- **[DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md)** - Development workflows
- **[QUERY_ARCHITECTURE.md](docs/QUERY_ARCHITECTURE.md)** - TanStack Query organization pattern
- **[I18N.md](docs/I18N.md)** - Internationalization (i18n) guide for translations
- **[V1_DASHBOARD_IMPLEMENTATION.md](docs/plan/V1_DASHBOARD_IMPLEMENTATION.md)** - V1 Dashboard implementation plan
- **[IMPLEMENTATION_COMPLETE.md](docs/plan/IMPLEMENTATION_COMPLETE.md)** - V1 Dashboard completion summary
