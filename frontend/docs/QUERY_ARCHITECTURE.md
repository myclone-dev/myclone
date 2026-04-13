# TanStack Query Architecture

This document explains our TanStack Query organization pattern, inspired by the rappo repository structure.

## Why This Architecture?

### Problems with the Old Approach

- ❌ Types mixed with hooks in single file (`hooks/useOnboarding.ts`)
- ❌ Fetch functions inside hook definitions (harder to test)
- ❌ No domain organization (everything in flat `hooks/` folder)
- ❌ Types scattered between `hooks/` and `types/`
- ❌ Difficult to scale as project grows

### Benefits of the New Approach

- ✅ **Domain-organized**: Each feature domain gets its own folder (`lib/queries/expert/`, `lib/queries/auth/`, etc.)
- ✅ **Separation of concerns**: Fetch functions separate from hooks
- ✅ **Type co-location**: Types live with their queries in `interface.ts`
- ✅ **Testability**: Fetch functions can be tested independently
- ✅ **Cache management**: Exported query key generators for invalidation
- ✅ **Single import**: Import hooks and types from same place

## Folder Structure

```
src/lib/queries/
├── error.ts              # ApiException class
└── {domain}/             # e.g., expert, auth, users
    ├── index.ts          # Exports all hooks and types
    ├── interface.ts      # TypeScript interfaces
    └── use{Feature}.ts   # Query/mutation hooks
```

### Example: Expert Domain

```
lib/queries/expert/
├── index.ts                           # Exports
├── interface.ts                       # Types
├── useLinkedInSearch.ts               # LinkedIn search
└── useExpertOnboardingSubmit.ts       # Onboarding submission
```

## File Patterns

### 1. `interface.ts` - Type Definitions

All TypeScript interfaces for the domain:

```typescript
export interface LinkedInSearchRequest {
  name: string;
  current_company?: string;
  role?: string;
}

export interface LinkedInSearchResponse {
  success: boolean;
  profiles: LinkedInProfile[];
  error?: string | null;
}
```

### 2. `use{Feature}.ts` - Query/Mutation Hooks

Four-part structure:

```typescript
// 1. Fetch function (separate, testable)
const fetchLinkedInSearch = async (
  searchData: LinkedInSearchRequest,
): Promise<LinkedInSearchResponse> => {
  const response = await fetch(
    `${env.NEXT_PUBLIC_API_URL}/user/linkedin/search`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(searchData),
    },
  );

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || "Failed to fetch");
  }

  return response.json();
};

// 2. Query key generator (for cache management)
export const getLinkedInSearchQueryKey = (
  searchData: LinkedInSearchRequest,
) => {
  return [
    "linkedin-search",
    {
      name: searchData.name,
      company: searchData.current_company,
      role: searchData.role,
    },
  ];
};

// 3. Query hook (for data fetching)
export const useLinkedInSearchQuery = (
  searchData: LinkedInSearchRequest | null,
  options?: { enabled?: boolean; staleTime?: number },
) => {
  return useQuery({
    queryKey: searchData
      ? getLinkedInSearchQueryKey(searchData)
      : ["linkedin-search", "disabled"],
    queryFn: () => {
      if (!searchData) throw new Error("Search data required");
      return fetchLinkedInSearch(searchData);
    },
    enabled: options?.enabled !== false && !!searchData,
    staleTime: options?.staleTime ?? 10 * 60 * 1000,
  });
};

// 4. Mutation hook (for POST/PUT/DELETE)
export const useLinkedInSearch = () => {
  return useMutation({
    mutationFn: fetchLinkedInSearch,
    onError: (error: Error) => {
      console.error("LinkedIn search failed:", error.message);
    },
  });
};
```

### 3. `index.ts` - Exports

Clean barrel exports:

```typescript
export * from "./interface";
export * from "./useLinkedInSearch";
export * from "./useExpertOnboardingSubmit";
```

## Usage in Components

### Single Import for Everything

```typescript
import {
  useLinkedInSearchQuery,
  useExpertOnboardingSubmit,
  type OnboardingData,
  type LinkedInProfile,
  type LinkedInSearchRequest,
} from "@/lib/queries/expert";
```

### Using Query Hooks

```typescript
const { data, isLoading, error } = useLinkedInSearchQuery(searchParams, {
  enabled: !!searchParams,
});
```

### Using Mutation Hooks

```typescript
const submitMutation = useExpertOnboardingSubmit();

await submitMutation.mutateAsync(formData);
```

## Query Key Management

Exported query key generators allow for precise cache invalidation:

```typescript
import { getLinkedInSearchQueryKey } from "@/lib/queries/expert";

// Invalidate specific search
queryClient.invalidateQueries({
  queryKey: getLinkedInSearchQueryKey(searchData),
});

// Invalidate all LinkedIn searches
queryClient.invalidateQueries({
  queryKey: ["linkedin-search"],
});
```

## Real-World Example: Expert Onboarding

### Before (Old Pattern)

```typescript
// hooks/useOnboarding.ts - Everything mixed together
export function useLinkedInSearchQuery(searchData, options) {
  return useQuery({
    queryKey: ["linkedin-search"],
    queryFn: async () => {
      const response = await fetch(/* ... */);
      return response.json();
    },
    enabled: options?.enabled,
  });
}

// types/onboarding.ts - Types in separate file
export interface LinkedInSearchRequest {
  // ...
}
```

### After (New Pattern)

```typescript
// lib/queries/expert/interface.ts
export interface LinkedInSearchRequest {
  /* ... */
}
export interface LinkedInSearchResponse {
  /* ... */
}

// lib/queries/expert/useLinkedInSearch.ts
const fetchLinkedInSearch = async (/* ... */) => {
  /* ... */
};
export const getLinkedInSearchQueryKey = (/* ... */) => {
  /* ... */
};
export const useLinkedInSearchQuery = (/* ... */) => {
  /* ... */
};

// lib/queries/expert/index.ts
export * from "./interface";
export * from "./useLinkedInSearch";

// Component usage
import {
  useLinkedInSearchQuery,
  type LinkedInSearchRequest,
} from "@/lib/queries/expert";
```

## Benefits in Practice

1. **Co-location**: Types and hooks for a feature live together
2. **Discoverability**: Easy to find all expert-related queries
3. **Reusability**: Fetch functions can be used outside hooks
4. **Testing**: Fetch functions can be unit tested independently
5. **Cache control**: Query key generators for precise invalidation
6. **Scalability**: Add new domains without cluttering existing code

## Migration Guide

When adding a new API integration:

1. Create domain folder: `src/lib/queries/{domain}/`
2. Create `interface.ts` with all types
3. Create `use{Feature}.ts` with fetch function + hooks
4. Create `index.ts` with barrel exports
5. Import from `@/lib/queries/{domain}` in components

## Related Files

- See `src/lib/queries/expert/` for complete implementation
- See `CLAUDE.md` for architecture overview
- See `src/components/onboarding/ExpertOnboarding.tsx` for usage example
