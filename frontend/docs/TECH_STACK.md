# Technology Stack

Complete overview of all technologies, libraries, and tools used in this project.

---

## Frontend Framework

### Next.js 15.5.4

**Purpose:** React framework for production

- **App Router** - File-system based routing with layouts
- **Server Components** - React components that render on the server
- **Server Actions** - Functions that run on the server
- **Turbopack** - Next-generation bundler (faster than Webpack)
- **Image Optimization** - Automatic image optimization
- **Font Optimization** - Zero layout shift with `next/font`

**Why Next.js?**

- Built-in SSR, SSG, and ISR
- Excellent DX with hot reload
- Production-ready optimizations
- Vercel deployment integration

### React 19.1.0

**Purpose:** UI library

- **Server Components** - New paradigm for server-first rendering
- **Concurrent Features** - Better UX with transitions
- **Automatic Batching** - Better performance
- **Improved Hooks** - useId, useTransition, etc.

---

## Language & Type Safety

### TypeScript 5

**Purpose:** Type-safe JavaScript

- **Strict Mode** - Maximum type safety
- **Path Aliases** - `@/*` imports
- **Type Inference** - Less manual typing
- **Compile-time Safety** - Catch errors before runtime

**Configuration:**

```json
{
  "compilerOptions": {
    "strict": true,
    "target": "ES2017",
    "module": "esnext",
    "moduleResolution": "bundler"
  }
}
```

### Zod 4.1.11

**Purpose:** Runtime schema validation

- **Type Inference** - TypeScript types from schemas
- **Environment Variables** - Validate env vars
- **Form Validation** - With React Hook Form
- **API Responses** - Validate server data

**Usage:**

```typescript
const userSchema = z.object({
  name: z.string().min(1),
  email: z.string().email(),
  age: z.number().min(18),
});

type User = z.infer<typeof userSchema>; // Type-safe!
```

---

## Styling

### Tailwind CSS v4

**Purpose:** Utility-first CSS framework

- **JIT Compilation** - Generate classes on-demand
- **CSS Variables** - For theming
- **Custom Variants** - Dark mode, hover states
- **Purge Unused** - Smaller production bundles

**Why Tailwind?**

- Rapid development
- Consistent design system
- No CSS naming conflicts
- Smaller bundle with tree-shaking

### shadcn/ui

**Purpose:** High-quality React components

- **Radix UI Primitives** - Accessible, unstyled components
- **Tailwind Styling** - Customizable with CSS variables
- **Copy-paste Components** - Own your code
- **CLI Installation** - `pnpm dlx shadcn@latest add button`

**Components Used:**

- button, input, label
- card, dialog, dropdown-menu
- avatar, separator, badge
- select, form, sonner (toast)

**Style:** New York
**Base Color:** Neutral
**Icons:** lucide-react

### Supporting Styling Libraries

#### tailwind-merge 3.3.1

**Purpose:** Intelligent Tailwind class merging

```typescript
cn("px-2 py-1", "px-4"); // → 'py-1 px-4' (no conflicts)
```

#### clsx 2.1.1

**Purpose:** Conditional className composition

```typescript
clsx("base", condition && "conditional", { active: isActive });
```

#### class-variance-authority 0.7.1

**Purpose:** Type-safe component variants

```typescript
const button = cva("base", {
  variants: {
    variant: { primary: "bg-blue", secondary: "bg-gray" },
    size: { sm: "text-sm", lg: "text-lg" },
  },
});
```

### lucide-react 0.544.0

**Purpose:** Beautiful, consistent icons

- 1000+ icons
- Tree-shakable
- Customizable size/color
- TypeScript support

---

## State Management

### Zustand 5.0.8

**Purpose:** Client UI state management

- **Minimal Boilerplate** - Simple API
- **No Context Providers** - Direct hook access
- **Middleware Support** - persist, devtools
- **TypeScript First** - Excellent type inference

**Use Cases:**

- Modal open/closed state
- Sidebar collapsed state
- Theme preference
- **Auth state** (user, token, isAuthenticated)

**Example:**

```typescript
const useStore = create((set) => ({
  count: 0,
  increment: () => set((state) => ({ count: state.count + 1 })),
}));
```

### TanStack Query 5.90.2

**Purpose:** Server state management & data fetching

- **Automatic Caching** - Smart cache invalidation
- **Background Refetching** - Keep data fresh
- **Request Deduplication** - Prevent duplicate requests
- **Optimistic Updates** - Better UX
- **DevTools** - Debug queries visually

**Use Cases:**

- ALL server/API data fetching
- User data, posts, comments
- Mutations (POST, PUT, DELETE)

**Query Pattern:**

```typescript
const { data, isLoading } = useQuery({
  queryKey: ["users"],
  queryFn: () => api.get("/users"),
});
```

**Mutation Pattern:**

```typescript
const mutation = useMutation({
  mutationFn: (data) => api.post("/users", data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["users"] });
  },
});
```

---

## HTTP Client

### Axios 1.12.2

**Purpose:** Promise-based HTTP client

- **Interceptors** - Request/response middleware
- **TypeScript Support** - Generic types
- **Auto JSON** - Automatic parsing
- **Error Handling** - Centralized error logic

**Configuration:**

```typescript
const api = axios.create({
  baseURL: env.NEXT_PUBLIC_API_URL,
});

// Auto-inject auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("auth_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-handle 401
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

---

## Form Management

### React Hook Form 7.64.0

**Purpose:** Performant form library

- **Uncontrolled Components** - Better performance
- **Minimal Re-renders** - Smart optimization
- **Easy Validation** - With Zod resolver
- **TypeScript Support** - Full type safety

**Example:**

```typescript
const form = useForm<FormData>({
  resolver: zodResolver(schema),
  defaultValues: { name: "" },
});
```

### @hookform/resolvers 5.2.2

**Purpose:** Validation library integrations

- Zod resolver for schema validation
- Yup, Joi support
- Type-safe integration

---

## Environment Variables

### @t3-oss/env-nextjs 0.13.8

**Purpose:** Type-safe environment variables

- **Zod Validation** - Runtime + compile-time validation
- **Type Inference** - Autocomplete for env vars
- **Server/Client Split** - Clear separation
- **Build-time Validation** - Fails fast on errors

**Configuration:**

```typescript
export const env = createEnv({
  server: {
    DATABASE_URL: z.string().url(),
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

**Usage:**

```typescript
import { env } from "@/env";

const apiUrl = env.NEXT_PUBLIC_API_URL; // Type-safe & validated!
```

---

## UI Primitives

### Radix UI

**Purpose:** Unstyled, accessible UI components

**Installed Primitives:**

- `@radix-ui/react-avatar` - Avatar component
- `@radix-ui/react-dialog` - Modal dialogs
- `@radix-ui/react-dropdown-menu` - Dropdown menus
- `@radix-ui/react-label` - Form labels
- `@radix-ui/react-select` - Select inputs
- `@radix-ui/react-separator` - Visual separators
- `@radix-ui/react-slot` - Composable components
- `@radix-ui/react-toast` - Toast notifications

**Why Radix?**

- Accessibility built-in (WAI-ARIA)
- Unstyled (full design control)
- Composable API
- Keyboard navigation
- Focus management

---

## Notifications

### Sonner 2.0.7

**Purpose:** Toast notifications

- **Beautiful Animations** - Smooth transitions
- **Stacking** - Multiple toasts
- **Promise Support** - Loading states
- **Accessible** - Screen reader support

**Advantages over react-hot-toast:**

- Better animations
- Native dark mode
- Promise-based API
- Smaller bundle size

**Usage:**

```typescript
import { toast } from "sonner";

toast.success("Successfully saved!");
toast.error("Something went wrong");
toast.promise(saveUser(), {
  loading: "Saving...",
  success: "Saved!",
  error: "Error!",
});
```

---

## Developer Tools

### Code Quality

#### ESLint 9

**Purpose:** JavaScript/TypeScript linting

- **Next.js Config** - Next.js-specific rules
- **Prettier Integration** - No conflicts
- **Auto-fix** - Automatic fixes on save

**Configs:**

- `eslint-config-next` - Next.js rules
- `eslint-config-prettier` - Disable conflicting rules

#### Prettier 3.6.2

**Purpose:** Code formatting

- **Consistent Style** - Across team
- **Auto-format** - On save and commit
- **Plugin Support** - Tailwind class sorting

**Plugins:**

- `prettier-plugin-tailwindcss` - Sort Tailwind classes

### Git Hooks

#### Husky 9.1.7

**Purpose:** Git hooks management

- **Pre-commit Hook** - Run linters before commit
- **Commit Message** - Enforce conventions
- **Easy Setup** - `pnpm prepare`

#### lint-staged 16.2.3

**Purpose:** Run linters on staged files

- **Fast** - Only lint changed files
- **Configurable** - Custom commands per file type
- **Auto-fix** - Fix linting errors automatically

**Configuration:**

```json
{
  "lint-staged": {
    "*.{js,jsx,ts,tsx}": ["eslint --fix", "prettier --write"],
    "*.{json,css,md}": ["prettier --write"]
  }
}
```

---

## Package Management

### pnpm 10.18.0

**Purpose:** Fast, disk-efficient package manager

**Advantages over npm/yarn:**

- **Disk Space** - Shared dependency storage
- **Speed** - Faster installs
- **Strict** - Prevents phantom dependencies
- **Monorepo Support** - Workspaces

**Key Files:**

- `pnpm-lock.yaml` - Lockfile
- `pnpm-workspace.yaml` - Workspace config
- `.npmrc` - pnpm configuration

---

## Build Tools

### Turbopack (Next.js 15)

**Purpose:** Next-generation bundler

- **Faster** - 700x faster than Webpack
- **Incremental** - Only rebuild what changed
- **Built-in** - Included with Next.js
- **Rust-based** - Compiled for performance

**Usage:**

```bash
pnpm dev --turbopack     # Development with Turbopack
pnpm build --turbopack   # Production build
```

### PostCSS

**Purpose:** CSS processing

- **Tailwind CSS** - Process Tailwind directives
- **Autoprefixer** - Add vendor prefixes
- **CSS Nesting** - Modern CSS features

**Plugins:**

- `@tailwindcss/postcss` - Tailwind v4 integration

---

## Theming

### next-themes 0.4.6

**Purpose:** Dark mode support

- **System Preference** - Auto-detect OS theme
- **Persistent** - Remember user choice
- **No Flash** - Prevent theme flash on load
- **Multiple Themes** - Support custom themes

**Usage:**

```typescript
import { ThemeProvider } from 'next-themes';

export function Providers({ children }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system">
      {children}
    </ThemeProvider>
  );
}
```

---

## Additional Utilities

### tw-animate-css 1.4.0

**Purpose:** Pre-built Tailwind animations

- Drop-in animations
- Tailwind-compatible
- Customizable

---

## Development Dependencies Summary

| Category            | Libraries                              |
| ------------------- | -------------------------------------- |
| **Framework**       | Next.js 15, React 19                   |
| **Language**        | TypeScript 5, Zod 4                    |
| **Styling**         | Tailwind CSS v4, shadcn/ui, CVA        |
| **State**           | Zustand 5, TanStack Query v5           |
| **HTTP**            | Axios 1.12                             |
| **Forms**           | React Hook Form 7, @hookform/resolvers |
| **Environment**     | @t3-oss/env-nextjs                     |
| **UI Primitives**   | Radix UI (8 packages)                  |
| **Icons**           | lucide-react                           |
| **Notifications**   | Sonner 2                               |
| **Linting**         | ESLint 9, Prettier 3                   |
| **Git Hooks**       | Husky 9, lint-staged 16                |
| **Package Manager** | pnpm 10                                |
| **Theme**           | next-themes 0.4                        |

---

## Version Requirements

- **Node.js:** 18.17 or higher
- **pnpm:** 10.18.0 (enforced via packageManager field)
- **TypeScript:** 5.x

---

## Bundle Size Considerations

### Production Optimizations

1. **Tree Shaking** - Remove unused code
2. **Code Splitting** - Route-based splitting
3. **Image Optimization** - Next.js automatic optimization
4. **Font Optimization** - next/font subsetting
5. **CSS Purging** - Tailwind removes unused classes

### Lightweight Choices

- **Zustand** - ~1KB (vs Redux ~20KB)
- **TanStack Query** - Tree-shakable
- **lucide-react** - Import only needed icons
- **Radix UI** - Import only needed primitives

---

## Why These Choices?

### Modern Stack

- Next.js 15 with App Router (latest paradigm)
- React 19 with Server Components
- TypeScript for safety

### Developer Experience

- Fast refresh with Turbopack
- Type safety everywhere
- Auto-formatting and linting
- Excellent tooling

### Performance

- Server Components reduce bundle size
- TanStack Query minimizes requests
- Tailwind purges unused CSS
- Image/font optimization

### Maintainability

- Clear separation of concerns
- Type safety prevents bugs
- Consistent code style
- Well-documented patterns

### Scalability

- Modular architecture
- State management scales
- Easy to add features
- Production-ready

---

## Future Additions (Planned)

- [ ] Testing: Vitest + React Testing Library
- [ ] E2E: Playwright
- [ ] Database: Prisma + PostgreSQL
- [ ] Auth: NextAuth.js or Clerk
- [ ] Monitoring: Sentry
- [ ] Analytics: Vercel Analytics
- [ ] CMS: Sanity or Contentful
- [ ] Email: Resend or SendGrid
