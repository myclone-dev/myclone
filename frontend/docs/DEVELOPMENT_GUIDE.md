# Development Guide

Complete guide for developing in this codebase.

---

## Getting Started

### Prerequisites

- **Node.js:** 18.17 or higher
- **pnpm:** 10.18.0 (automatically enforced)
- **Git:** For version control

### Initial Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd myclone-frontend
   ```

2. **Install dependencies**

   ```bash
   pnpm install
   ```

3. **Set up environment variables**

   ```bash
   cp .env.example .env.local
   ```

   Edit `.env.local` and add your values:

   ```env
   NEXT_PUBLIC_API_URL=http://localhost:3001/api
   NEXT_PUBLIC_APP_URL=http://localhost:3000
   ```

4. **Start development server**

   ```bash
   pnpm dev
   ```

   Open [http://localhost:3000](http://localhost:3000)

---

## Available Commands

### Development

```bash
pnpm dev              # Start development server with Turbopack
pnpm build            # Create production build
pnpm start            # Start production server
```

### Code Quality

```bash
pnpm type-check       # Run TypeScript compiler (no emit)
pnpm lint             # Run ESLint
pnpm lint:fix         # Auto-fix ESLint errors
pnpm format           # Format code with Prettier
pnpm format:check     # Check formatting without changes
```

### UI Components

```bash
# Add new shadcn/ui components
pnpm dlx shadcn@latest add <component-name>

# Examples:
pnpm dlx shadcn@latest add toast
pnpm dlx shadcn@latest add table
pnpm dlx shadcn@latest add calendar
```

### Git Hooks

Pre-commit hooks automatically run:

- ESLint with auto-fix
- Prettier formatting
- Only on staged files

---

## Project Structure

```
myclone-frontend/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx         # Root layout
│   │   ├── page.tsx           # Homepage
│   │   ├── error.tsx          # Error boundary
│   │   ├── loading.tsx        # Loading UI
│   │   └── providers.tsx      # Client providers
│   │
│   ├── components/
│   │   ├── ui/                # shadcn/ui components (CLI)
│   │   └── layouts/           # Layout components
│   │
│   ├── hooks/                 # Custom React hooks
│   ├── lib/                   # Utilities
│   ├── store/                 # Zustand stores
│   ├── types/                 # TypeScript types
│   └── env.ts                 # Environment validation
│
├── public/                     # Static assets
├── docs/                       # Documentation
├── .env.local                  # Local environment (git-ignored)
├── .env.example                # Environment template
├── components.json             # shadcn/ui config
├── next.config.ts              # Next.js config
├── tsconfig.json               # TypeScript config
└── package.json                # Dependencies
```

---

## Development Workflow

### 1. Creating a New Feature

#### Step 1: Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

#### Step 2: Define Types

Create types in `src/types/index.ts`:

```typescript
export interface NewFeature {
  id: string;
  name: string;
  description: string;
}
```

#### Step 3: Create API Hook (if needed)

Create in `src/hooks/useFeature.ts`:

```typescript
"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { NewFeature } from "@/types";

export function useFeatures() {
  return useQuery({
    queryKey: ["features"],
    queryFn: async () => {
      const { data } = await api.get<NewFeature[]>("/features");
      return data;
    },
  });
}

export function useCreateFeature() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (feature: Omit<NewFeature, "id">) => {
      const { data } = await api.post<NewFeature>("/features", feature);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["features"] });
    },
  });
}
```

#### Step 4: Create UI Components

Add shadcn components if needed:

```bash
pnpm dlx shadcn@latest add card
```

Create feature component:

```typescript
// src/components/features/FeatureCard.tsx
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import type { NewFeature } from '@/types';

interface FeatureCardProps {
  feature: NewFeature;
}

export function FeatureCard({ feature }: FeatureCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{feature.name}</CardTitle>
      </CardHeader>
      <CardContent>
        <p>{feature.description}</p>
      </CardContent>
    </Card>
  );
}
```

#### Step 5: Create Page

```typescript
// src/app/features/page.tsx
'use client';

import { useFeatures } from '@/hooks/useFeature';
import { FeatureCard } from '@/components/features/FeatureCard';

export default function FeaturesPage() {
  const { data: features, isLoading } = useFeatures();

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="grid grid-cols-3 gap-4">
      {features?.map((feature) => (
        <FeatureCard key={feature.id} feature={feature} />
      ))}
    </div>
  );
}
```

#### Step 6: Test Locally

```bash
pnpm dev
pnpm type-check
pnpm lint
```

#### Step 7: Commit

```bash
git add .
git commit -m "feat: add features page"
# Pre-commit hooks will auto-run
```

### 2. Adding Environment Variables

#### Step 1: Update Schema

Edit `src/env.ts`:

```typescript
export const env = createEnv({
  server: {
    NODE_ENV: z.enum(["development", "test", "production"]),
    NEW_SERVER_VAR: z.string().min(1), // Add here
  },
  client: {
    NEXT_PUBLIC_API_URL: z.string().url(),
    NEXT_PUBLIC_NEW_VAR: z.string(), // Add here
  },
  runtimeEnv: {
    NODE_ENV: process.env.NODE_ENV,
    NEW_SERVER_VAR: process.env.NEW_SERVER_VAR,
    NEXT_PUBLIC_NEW_VAR: process.env.NEXT_PUBLIC_NEW_VAR,
  },
});
```

#### Step 2: Add to .env.local

```env
NEW_SERVER_VAR=secret-value
NEXT_PUBLIC_NEW_VAR=public-value
```

#### Step 3: Add to .env.example

```env
NEW_SERVER_VAR=
NEXT_PUBLIC_NEW_VAR=
```

#### Step 4: Use in Code

```typescript
import { env } from "@/env";

const value = env.NEXT_PUBLIC_NEW_VAR; // Type-safe!
```

### 3. Adding UI Components

**ALWAYS use shadcn CLI:**

```bash
# List available components
pnpm dlx shadcn@latest add

# Add specific component
pnpm dlx shadcn@latest add dialog

# Add multiple components
pnpm dlx shadcn@latest add toast table calendar
```

**Never manually create components in `src/components/ui/`**

### 4. State Management

#### Client UI State (Zustand)

Use for: modals, sidebar, theme, auth state

```typescript
// src/store/modal.store.ts
import { create } from "zustand";

interface ModalState {
  isOpen: boolean;
  modalContent: React.ReactNode | null;
  openModal: (content: React.ReactNode) => void;
  closeModal: () => void;
}

export const useModalStore = create<ModalState>((set) => ({
  isOpen: false,
  modalContent: null,
  openModal: (content) => set({ isOpen: true, modalContent: content }),
  closeModal: () => set({ isOpen: false, modalContent: null }),
}));
```

#### Server Data (TanStack Query)

Use for: ALL API/server data

```typescript
// src/hooks/usePosts.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

export function usePosts() {
  return useQuery({
    queryKey: ["posts"],
    queryFn: async () => {
      const { data } = await api.get("/posts");
      return data;
    },
    staleTime: 60_000, // 1 minute
  });
}
```

### 5. Styling Components

#### Use Tailwind Utilities

```typescript
<div className="flex items-center justify-between p-4 bg-background">
  <h1 className="text-2xl font-bold">Title</h1>
</div>
```

#### Use cn() for Conditional Classes

```typescript
import { cn } from '@/lib/utils';

<button
  className={cn(
    'px-4 py-2 rounded',
    isActive && 'bg-primary text-primary-foreground',
    disabled && 'opacity-50 cursor-not-allowed'
  )}
/>
```

#### Use CSS Variables for Theming

```typescript
// Access theme colors
<div className="bg-primary text-primary-foreground">
  Primary colored div
</div>

// Custom styles with CSS variables
<div style={{ backgroundColor: 'hsl(var(--primary))' }}>
  Custom background
</div>
```

---

## Code Style Guidelines

### TypeScript

```typescript
// ✅ Use type inference
const users = await getUsers(); // Type inferred

// ❌ Don't over-annotate
const users: User[] = await getUsers();

// ✅ Use interfaces for objects
interface User {
  id: string;
  name: string;
}

// ✅ Use types for unions/intersections
type Status = "idle" | "loading" | "error";

// ✅ Use const for everything (unless you need let)
const count = 0;

// ✅ Destructure props
function Component({ title, description }: Props) {}

// ❌ Don't use props object
function Component(props: Props) {}
```

### React Components

```typescript
// ✅ Arrow functions for components
const MyComponent = () => { };

// ✅ Use Server Components by default
export default async function Page() {
  const data = await fetchData();
  return <div>{data}</div>;
}

// ✅ Only use 'use client' when needed
'use client';
export function InteractiveComponent() {
  const [state, setState] = useState(0);
  return <button onClick={() => setState(state + 1)}>{state}</button>;
}

// ✅ Use forwardRef for form components
export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => {
    return <input ref={ref} className={cn('base', className)} {...props} />;
  }
);
```

### Imports

```typescript
// ✅ Use path aliases
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { env } from "@/env";

// ❌ Don't use relative paths for deep imports
import { Button } from "../../../components/ui/button";

// ✅ Group imports: external, internal, types
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";

import type { User } from "@/types";
```

### File Naming

```
✅ page.tsx, layout.tsx, loading.tsx, error.tsx  # Next.js conventions
✅ button.tsx, input.tsx                          # shadcn/ui lowercase
✅ Header.tsx, Footer.tsx                         # Custom components PascalCase
✅ useAuth.ts, usePosts.ts                        # Hooks with 'use' prefix
✅ auth.store.ts, ui.store.ts                     # Stores with .store suffix
✅ client.ts, utils.ts                            # Utilities lowercase
```

---

## Common Tasks

### Adding a New Page

1. Create file in `src/app/`:

   ```typescript
   // src/app/about/page.tsx
   export default function AboutPage() {
     return <div>About Page</div>;
   }
   ```

2. Add metadata:

   ```typescript
   export const metadata = {
     title: "About",
     description: "About our application",
   };
   ```

3. Access at `/about`

### Creating a Protected Route

1. Create route group:

   ```
   src/app/(protected)/
   ├── layout.tsx     # Check auth here
   └── dashboard/
       └── page.tsx
   ```

2. Add auth check in layout:

   ```typescript
   'use client';

   import { useAuthStore } from '@/store/auth.store';
   import { redirect } from 'next/navigation';

   export default function ProtectedLayout({ children }) {
     const { isAuthenticated } = useAuthStore();

     if (!isAuthenticated) {
       redirect('/login');
     }

     return <>{children}</>;
   }
   ```

### Adding Form Validation

1. Install if needed (already installed):

   ```bash
   pnpm add react-hook-form @hookform/resolvers zod
   ```

2. Create schema:

   ```typescript
   import { z } from "zod";

   const formSchema = z.object({
     email: z.string().email("Invalid email"),
     password: z.string().min(8, "Password must be 8+ characters"),
   });

   type FormData = z.infer<typeof formSchema>;
   ```

3. Use in component:

   ```typescript
   'use client';

   import { useForm } from 'react-hook-form';
   import { zodResolver } from '@hookform/resolvers/zod';

   export function LoginForm() {
     const form = useForm<FormData>({
       resolver: zodResolver(formSchema),
       defaultValues: { email: '', password: '' },
     });

     const onSubmit = (data: FormData) => {
       console.log(data); // Type-safe!
     };

     return (
       <form onSubmit={form.handleSubmit(onSubmit)}>
         <input {...form.register('email')} />
         {form.formState.errors.email && (
           <span>{form.formState.errors.email.message}</span>
         )}
       </form>
     );
   }
   ```

### Displaying Toasts

```typescript
'use client';

import { toast } from 'sonner';

export function ExampleComponent() {
  const handleClick = () => {
    toast.success('Successfully saved!');
    toast.error('Something went wrong');
    toast.loading('Saving...');

    // Promise toast
    toast.promise(saveData(), {
      loading: 'Saving...',
      success: 'Saved!',
      error: 'Failed to save',
    });
  };

  return <button onClick={handleClick}>Show Toast</button>;
}
```

---

## Debugging

### TypeScript Errors

```bash
# Check types
pnpm type-check

# Common fixes:
# 1. Missing import
# 2. Wrong type annotation
# 3. Null/undefined not handled
```

### ESLint Errors

```bash
# Check errors
pnpm lint

# Auto-fix
pnpm lint:fix
```

### TanStack Query DevTools

Already configured in `src/app/providers.tsx`:

```typescript
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

// Available in development at bottom-right corner
<ReactQueryDevtools initialIsOpen={false} />
```

### Browser Check Issues

Always check before using browser APIs:

```typescript
// ✅ Correct
if (typeof window !== "undefined") {
  localStorage.setItem("key", "value");
}

// ❌ Wrong - will error on server
localStorage.setItem("key", "value");
```

---

## Performance Tips

1. **Use Server Components** - Default to server, only go client when needed
2. **Code Split** - Dynamic imports for heavy components
   ```typescript
   const HeavyComponent = dynamic(() => import('./HeavyComponent'), {
     loading: () => <Spinner />,
   });
   ```
3. **Optimize Images** - Use Next.js Image component
   ```typescript
   import Image from 'next/image';
   <Image src="/photo.jpg" width={500} height={300} alt="Photo" />
   ```
4. **TanStack Query Caching** - Configure staleTime appropriately
5. **Memoization** - Use React.memo, useMemo, useCallback sparingly

---

## Troubleshooting

### Port Already in Use

```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill -9

# Or use different port
pnpm dev -- -p 3001
```

### pnpm Install Fails

```bash
# Clear cache
pnpm store prune

# Remove node_modules and reinstall
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### Build Errors

```bash
# Clean Next.js cache
rm -rf .next

# Rebuild
pnpm build
```

### Environment Variable Not Working

1. Restart dev server after changing `.env.local`
2. Check variable is in `src/env.ts` schema
3. Check spelling (case-sensitive)
4. Client vars MUST start with `NEXT_PUBLIC_`

---

## CI/CD (Future)

### GitHub Actions

```yaml
name: CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: pnpm/action-setup@v2
      - uses: actions/setup-node@v3
        with:
          node-version: 18
          cache: "pnpm"
      - run: pnpm install
      - run: pnpm type-check
      - run: pnpm lint
      - run: pnpm build
```

---

## Resources

- [Next.js Docs](https://nextjs.org/docs)
- [React Docs](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS Docs](https://tailwindcss.com/docs)
- [shadcn/ui Docs](https://ui.shadcn.com)
- [TanStack Query Docs](https://tanstack.com/query/latest)
- [Zustand Docs](https://zustand-demo.pmnd.rs/)

---

## Getting Help

1. Check documentation in `/docs` folder
2. Read error messages carefully
3. Search existing issues on GitHub
4. Ask team members
5. Check library documentation
