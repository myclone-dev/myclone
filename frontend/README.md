# ConvoxAI Frontend

A modern, full-stack web application built with Next.js 15, React 19, TypeScript, and best practices for 2025.

---

## 🚀 Quick Start

```bash
# Install dependencies
pnpm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your values

# Start development server
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) to see the app.

---

## 📚 Documentation

Comprehensive documentation is available in the [`/docs`](./docs) folder:

- **[Architecture](./docs/ARCHITECTURE.md)** - System design and patterns
- **[Tech Stack](./docs/TECH_STACK.md)** - Technologies and why we use them
- **[Development Guide](./docs/DEVELOPMENT_GUIDE.md)** - How to build features

**New to the project?** Start with the [docs README](./docs/README.md)

---

## 🛠️ Tech Stack

### Core

- **Next.js 15.5.4** - React framework with App Router & Turbopack
- **React 19.1.0** - UI library with Server Components
- **TypeScript 5** - Type-safe JavaScript

### Styling

- **Tailwind CSS v4** - Utility-first CSS
- **shadcn/ui** - High-quality React components
- **Radix UI** - Accessible UI primitives

### State Management

- **Zustand 5** - Client UI state
- **TanStack Query v5** - Server state & data fetching

### Developer Experience

- **pnpm** - Fast, efficient package manager
- **ESLint + Prettier** - Code quality & formatting
- **Husky** - Git hooks for pre-commit checks

[See full tech stack →](./docs/TECH_STACK.md)

---

## 📋 Available Commands

```bash
# Development
pnpm dev              # Start dev server
pnpm build            # Production build
pnpm start            # Start production server

# Code Quality
pnpm type-check       # TypeScript check
pnpm lint             # Run ESLint
pnpm lint:fix         # Fix ESLint errors
pnpm format           # Format with Prettier

# UI Components
pnpm dlx shadcn@latest add <component>  # Add shadcn component
```

---

## 📁 Project Structure

```
src/
├── app/              # Next.js App Router (pages)
├── components/
│   ├── ui/          # shadcn/ui components (CLI-generated)
│   └── layouts/     # Layout components
├── hooks/           # Custom React hooks
├── lib/             # Utilities & API client
├── store/           # Zustand stores
├── types/           # TypeScript types
└── env.ts           # Environment validation
```

---

## 🎯 Key Features

✅ **Server Components First** - Reduce client JavaScript
✅ **Type-Safe Environment Variables** - With `@t3-oss/env-nextjs`
✅ **Smart State Management** - Zustand for UI, TanStack Query for server data
✅ **Automatic Auth** - JWT tokens with auto-refresh
✅ **Beautiful UI** - shadcn/ui components with dark mode
✅ **Pre-commit Hooks** - Auto-lint and format on commit

---

## 🔐 Environment Variables

Create `.env.local` from template:

```env
NEXT_PUBLIC_API_URL=http://localhost:3001/api
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

Variables are validated at build time using Zod schemas.

[Learn more about environment setup →](./docs/DEVELOPMENT_GUIDE.md#adding-environment-variables)

---

## 🏗️ Architecture Principles

### Server-First

- Server Components by default
- `'use client'` only when needed
- Better performance & SEO

### State Separation

- **Zustand** → Client UI state (modals, theme, auth)
- **TanStack Query** → ALL server/API data

### Type Safety

- TypeScript strict mode
- Zod runtime validation
- Type-safe env vars

[Read full architecture →](./docs/ARCHITECTURE.md)

---

## 🎨 Adding Components

**Always use the shadcn CLI:**

```bash
pnpm dlx shadcn@latest add dialog
pnpm dlx shadcn@latest add table
```

Never manually create components in `src/components/ui/`.

[Component guidelines →](./docs/DEVELOPMENT_GUIDE.md#adding-ui-components)

---

## 🧪 Code Quality

Pre-commit hooks automatically run:

- ESLint with auto-fix
- Prettier formatting
- TypeScript check

Manual checks:

```bash
pnpm type-check && pnpm lint && pnpm format:check
```

---

## 🚢 Deployment

### Vercel (Recommended)

1. Push to GitHub
2. Import to Vercel
3. Set environment variables
4. Deploy!

### Manual

```bash
pnpm build
pnpm start
```

[Deployment guide →](./docs/ARCHITECTURE.md#deployment)

---

## 📖 Learn More

- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [shadcn/ui](https://ui.shadcn.com)
- [TanStack Query](https://tanstack.com/query/latest)

---

## 🤝 Contributing

1. Read the [Development Guide](./docs/DEVELOPMENT_GUIDE.md)
2. Create a feature branch
3. Make your changes
4. Pre-commit hooks will run automatically
5. Submit a pull request

---

## 📄 License

This project is private and proprietary.

---

## 🆘 Need Help?

1. Check the [documentation](./docs)
2. Search existing issues
3. Create a new issue with details

---

**Built with ❤️ using Next.js 15 and modern best practices**
