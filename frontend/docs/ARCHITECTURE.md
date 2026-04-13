# Architecture Documentation

## Overview

ConvoxAI is a modern full-stack web application built with Next.js 15, following enterprise-level best practices for scalability, maintainability, and performance.

---

## Technology Stack

### Core Framework

- **Next.js 15.5.4** - React framework with App Router
- **React 19.1.0** - UI library with Server Components
- **TypeScript 5** - Type-safe JavaScript with strict mode enabled
- **Turbopack** - Next-generation bundler for faster builds

### Styling & UI

- **Tailwind CSS v4** - Utility-first CSS framework
- **shadcn/ui** - High-quality React components built on Radix UI
- **Radix UI** - Unstyled, accessible UI primitives
- **lucide-react** - Beautiful & consistent icon library
- **class-variance-authority** - Component variant management
- **tailwind-merge** - Intelligent Tailwind class merging

### State Management

- **Zustand 5.0.8** - Lightweight client-side state management
- **TanStack Query v5.90.2** - Powerful server state management & data fetching
- **zustand/persist** - Persist state to localStorage

### Data Fetching & API

- **Axios 1.12.2** - HTTP client with interceptors
- **TanStack Query** - Caching, synchronization, and server state

### Form Handling & Validation

- **React Hook Form 7.64.0** - Performant form management
- **Zod 4.1.11** - TypeScript-first schema validation
- **@hookform/resolvers** - Validation library resolvers for React Hook Form

### Environment & Configuration

- **@t3-oss/env-nextjs 0.13.8** - Type-safe environment variables
- **Zod** - Runtime validation for env vars

### Developer Experience

- **ESLint 9** - Code linting with Next.js config
- **Prettier 3.6.2** - Code formatting
- **Husky 9.1.7** - Git hooks
- **lint-staged 16.2.3** - Run linters on staged files
- **TypeScript** - Static type checking

### Notifications

- **Sonner 2.0.7** - Toast notifications (modern replacement for react-hot-toast)

### Package Manager

- **pnpm 10.18.0** - Fast, disk space efficient package manager

---

## Architecture Patterns

### 1. Server-First Architecture

Following Next.js 15 best practices, the application prioritizes Server Components:

```typescript
// ✅ Default - Server Component (no directive needed)
export default async function Page() {
  const data = await fetchData(); // Direct server-side fetch
  return <div>{data}</div>;
}

// ⚠️ Client Component - only when necessary
'use client';
export function InteractiveButton() {
  const [count, setCount] = useState(0);
  return <button onClick={() => setCount(count + 1)}>{count}</button>;
}
```

**Benefits:**

- Smaller JavaScript bundles sent to client
- Better SEO and initial page load
- Direct access to backend resources
- Improved security (sensitive operations on server)

### 2. State Management Strategy

#### Two-Layer State Architecture

**Layer 1: Client UI State (Zustand)**

- Purpose: Ephemeral UI state that doesn't come from the server
- Examples: Modal open/closed, sidebar collapsed, theme preference
- Location: `src/store/`
- Persistence: Optional via zustand/persist middleware

```typescript
// src/store/ui.store.ts
export const useUIStore = create((set) => ({
  isSidebarOpen: false,
  toggleSidebar: () =>
    set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
}));
```

**Layer 2: Server State (TanStack Query)**

- Purpose: ALL data from API/server
- Examples: User data, posts, comments, any backend data
- Location: `src/hooks/`
- Features: Automatic caching, background refetching, optimistic updates

```typescript
// src/hooks/useUsers.ts
export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: () => api.get("/users").then((res) => res.data),
  });
}
```

**❌ Anti-Pattern:** Never store server data in Zustand!

```typescript
// ❌ WRONG - Don't do this
const useStore = create((set) => ({
  users: [],
  fetchUsers: async () => {
    const users = await api.get("/users");
    set({ users });
  },
}));

// ✅ CORRECT - Use TanStack Query
const { data: users } = useQuery({
  queryKey: ["users"],
  queryFn: () => api.get("/users"),
});
```

### 3. Type-Safe Environment Variables

Using `@t3-oss/env-nextjs` for compile-time and runtime validation:

```typescript
// src/env.ts
export const env = createEnv({
  server: {
    DATABASE_URL: z.string().url(),
    API_SECRET: z.string().min(1),
  },
  client: {
    NEXT_PUBLIC_API_URL: z.string().url(),
  },
  runtimeEnv: {
    DATABASE_URL: process.env.DATABASE_URL,
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
});
```

**Benefits:**

- Autocomplete for environment variables
- Compile-time errors for missing/invalid vars
- Type safety across the application
- Clear separation of server/client vars

### 4. API Client Architecture

Centralized Axios instance with interceptors:

```typescript
// src/lib/api/client.ts
export const api = axios.create({
  baseURL: env.NEXT_PUBLIC_API_URL,
});

// Auto-inject auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("auth_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Logout and redirect
    }
    return Promise.reject(error);
  },
);
```

**Benefits:**

- Centralized auth token management
- Automatic error handling
- Single source of truth for API config
- Easy to add global interceptors

### 5. Authentication Flow

```
┌─────────────┐
│   Login     │
│   Form      │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│  TanStack Query Mutation        │
│  (useLogin hook)                │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  POST /auth/login               │
│  (via api client)               │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  On Success:                    │
│  1. Store token in localStorage │
│  2. Update Zustand auth store   │
│  3. Redirect to dashboard       │
└─────────────────────────────────┘

Subsequent Requests:
┌─────────────────────────────────┐
│  API Request                    │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Request Interceptor            │
│  - Reads token from localStorage│
│  - Adds Authorization header    │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│  Server validates token         │
└──────┬──────────────────────────┘
       │
       ▼ (if 401)
┌─────────────────────────────────┐
│  Response Interceptor           │
│  - Clear localStorage           │
│  - Clear Zustand store          │
│  - Redirect to /login           │
└─────────────────────────────────┘
```

### 6. Component Architecture

#### Component Types

**1. Page Components** (`src/app/**/page.tsx`)

- Server Components by default
- Handle data fetching
- Define page metadata
- Coordinate layout and child components

**2. Layout Components** (`src/components/layouts/`)

- Header, Footer, Sidebar
- May be Client Components if they need interactivity
- Shared across multiple pages

**3. UI Components** (`src/components/ui/`)

- Generated via shadcn/ui CLI
- Reusable, accessible primitives
- Styled with Tailwind CSS
- Accept className prop for customization

**4. Feature Components** (future: `src/components/features/`)

- Business logic components
- Specific to a feature/domain
- Compose UI components

#### Component Pattern

```typescript
import { forwardRef } from 'react';
import { cn } from '@/lib/utils';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'outline';
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'base-styles',
          variant === 'default' && 'default-variant-styles',
          variant === 'outline' && 'outline-variant-styles',
          className
        )}
        {...props}
      />
    );
  }
);
```

### 7. Data Fetching Patterns

#### Server Components (Preferred)

```typescript
// app/users/page.tsx
async function UsersPage() {
  // Direct fetch on server
  const users = await fetch('https://api.example.com/users').then(r => r.json());

  return <UserList users={users} />;
}
```

#### Client Components with TanStack Query

```typescript
// hooks/useUsers.ts
'use client';

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: async () => {
      const { data } = await api.get('/users');
      return data;
    },
    staleTime: 60_000, // Consider fresh for 1 minute
  });
}

// components/UserList.tsx
'use client';

export function UserList() {
  const { data: users, isLoading, error } = useUsers();

  if (isLoading) return <Spinner />;
  if (error) return <ErrorMessage />;

  return <div>{users.map(...)}</div>;
}
```

### 8. File Organization

```
src/
├── app/                          # Next.js App Router
│   ├── (auth)/                   # Route groups for auth pages
│   │   ├── login/page.tsx
│   │   └── signup/page.tsx
│   ├── dashboard/                # Protected routes
│   │   └── page.tsx
│   ├── layout.tsx                # Root layout
│   ├── page.tsx                  # Homepage
│   ├── error.tsx                 # Error boundary
│   ├── loading.tsx               # Loading UI
│   ├── not-found.tsx             # 404 page
│   ├── providers.tsx             # Client-side providers
│   └── globals.css               # Global styles + CSS variables
│
├── components/
│   ├── ui/                       # shadcn/ui components (CLI)
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   └── ...
│   ├── layouts/                  # Layout components
│   │   ├── Header.tsx
│   │   └── Footer.tsx
│   └── features/                 # Feature-specific components
│       └── ...
│
├── hooks/                        # Custom React hooks
│   ├── useAuth.ts               # Auth mutations/queries
│   └── ...
│
├── lib/                          # Utilities & helpers
│   ├── utils.ts                 # cn() and other utilities
│   └── api/
│       └── client.ts            # Axios instance
│
├── store/                        # Zustand stores
│   ├── auth.store.ts            # Auth state
│   └── ui.store.ts              # UI state
│
├── types/                        # TypeScript types
│   └── index.ts                 # Shared types
│
└── env.ts                        # Environment validation
```

### 9. Styling Architecture

#### CSS Variables System

Global CSS variables defined in `globals.css`:

```css
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 0 0% 3.9%;
    --primary: 221.2 83.2% 53.3%;
    --radius: 0.5rem;
    /* ... more variables */
  }

  .dark {
    --background: 0 0% 3.9%;
    --foreground: 0 0% 98%;
    /* ... dark mode overrides */
  }
}
```

#### Tailwind Configuration

- **v4** with `@import "tailwindcss"`
- CSS variables for theming
- Custom variants for dark mode
- Configured via `@theme inline` in globals.css

#### Component Styling

```typescript
// Use cn() utility to merge Tailwind classes
import { cn } from '@/lib/utils';

<div className={cn(
  'base-classes',
  condition && 'conditional-classes',
  className // Allow prop override
)} />
```

### 10. Error Handling

#### Global Error Boundary

```typescript
// app/error.tsx
'use client';

export default function Error({ error, reset }: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div>
      <h2>Something went wrong!</h2>
      <button onClick={reset}>Try again</button>
    </div>
  );
}
```

#### API Error Handling

```typescript
// Centralized in axios interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
    }
    if (error.response?.status === 500) {
      // Handle server error
    }
    return Promise.reject(error);
  },
);
```

#### TanStack Query Error Handling

```typescript
const { data, error, isError } = useQuery({
  queryKey: ['users'],
  queryFn: fetchUsers,
  retry: 3, // Auto-retry on failure
});

if (isError) {
  return <ErrorComponent error={error} />;
}
```

---

## Performance Optimizations

### 1. Server Components

- Reduce client-side JavaScript bundle
- Direct data fetching on server
- Better SEO and initial load time

### 2. TanStack Query Caching

- Automatic request deduplication
- Background refetching
- Stale-while-revalidate pattern

### 3. Code Splitting

- Automatic route-based splitting via Next.js
- Dynamic imports for heavy components

### 4. Image Optimization

- Next.js Image component with automatic optimization
- WebP format with fallbacks
- Lazy loading by default

### 5. Font Optimization

- `next/font` for zero layout shift
- Automatic font subsetting

---

## Security Considerations

### 1. Environment Variables

- Server-only vars never exposed to client
- Type-safe validation prevents misconfiguration
- `.env.local` git-ignored

### 2. Authentication

- JWT tokens in httpOnly cookies (recommended) or localStorage
- Automatic token refresh
- CSRF protection via Next.js

### 3. API Security

- CORS configured on backend
- Rate limiting via middleware
- Input validation with Zod

### 4. XSS Prevention

- React auto-escapes by default
- Sanitize user input before rendering

---

## Testing Strategy (Future)

### Unit Tests

- Vitest for fast unit testing
- React Testing Library for component tests

### Integration Tests

- Playwright for E2E testing
- Test user flows and critical paths

### Type Safety

- TypeScript strict mode
- Zod for runtime validation
- `pnpm type-check` in CI/CD

---

## Deployment

### Recommended Platform: Vercel

- Zero-config deployment
- Automatic preview deployments
- Edge network for global performance
- Built-in analytics

### Build Process

```bash
pnpm build  # Creates optimized production build
pnpm start  # Starts production server
```

### Environment Variables

- Set in Vercel dashboard or hosting platform
- Never commit `.env.local`
- Use `.env.example` as template

---

## Scalability Considerations

### 1. API Routes (Future)

- Use Next.js API routes for simple endpoints
- Separate backend service for complex logic

### 2. Database (Future)

- PostgreSQL with Prisma ORM
- Connection pooling for performance
- Read replicas for scaling reads

### 3. Caching Strategy

- TanStack Query for client-side cache
- Redis for server-side cache (future)
- CDN for static assets

### 4. Monitoring (Future)

- Sentry for error tracking
- Vercel Analytics for performance
- Custom logging with Winston

---

## Development Workflow

1. **Feature Development**
   - Create feature branch
   - Develop with `pnpm dev`
   - Add types in `src/types/`
   - Create hooks in `src/hooks/`
   - Build UI with shadcn components

2. **Code Quality**
   - Pre-commit hooks auto-run linting/formatting
   - `pnpm type-check` before commit
   - `pnpm lint` for manual check

3. **Testing**
   - Write tests alongside features
   - Run test suite before PR

4. **Deployment**
   - Merge to main
   - Automatic deployment to Vercel
   - Preview deployments for PRs

---

## Future Enhancements

- [ ] Add comprehensive test suite
- [ ] Implement real-time features with WebSockets
- [ ] Add internationalization (i18n)
- [ ] Implement advanced caching strategies
- [ ] Add monitoring and analytics
- [ ] Implement rate limiting
- [ ] Add API documentation with Swagger
- [ ] Implement GraphQL layer (optional)
