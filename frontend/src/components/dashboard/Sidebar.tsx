"use client";

import { useState, useEffect, useRef, Fragment } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  Home,
  BookOpen,
  MessageSquare,
  User,
  Menu,
  X,
  Code2,
  Users,
  ChevronLeft,
  ChevronRight,
  Shield,
  BarChart3,
  Plug,
  Workflow as WorkflowIcon,
  AudioLines,
  Tag,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useUIStore } from "@/store/ui.store";

const navigation = [
  {
    name: "Overview",
    href: "/dashboard",
    icon: Home,
  },
  {
    name: "Personas",
    href: "/dashboard/personas",
    icon: Users,
  },
  {
    name: "Knowledge Library",
    href: "/dashboard/knowledge",
    icon: BookOpen,
  },
  {
    name: "Voice Clone",
    href: "/dashboard/voice-clone",
    icon: AudioLines,
  },
  {
    name: "Conversations",
    href: "/dashboard/conversations",
    icon: MessageSquare,
  },
  {
    name: "Widgets",
    href: "/dashboard/widgets",
    icon: Code2,
  },
  {
    name: "Whitelabel",
    href: "/dashboard/whitelabel",
    icon: Tag,
  },
  {
    name: "Workflows",
    href: "/dashboard/workflows",
    icon: WorkflowIcon,
    beta: true,
    betaWarning: "This feature is in beta and may not work as expected.",
  },
  {
    name: "Integrations",
    href: "/dashboard/integrations",
    icon: Plug,
  },
  {
    name: "Access Control",
    href: "/dashboard/access-control",
    icon: Shield,
  },
  {
    name: "Limits & Usage",
    href: "/dashboard/usage",
    icon: BarChart3,
  },
  {
    name: "Profile",
    href: "/dashboard/profile",
    icon: User,
  },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const collapsed = useUIStore((state) => state.sidebarCollapsed);
  const setSidebarCollapsed = useUIStore((state) => state.setSidebarCollapsed);
  const previousPathnameRef = useRef(pathname);

  // Update CSS variable when sidebar collapses/expands
  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.style.setProperty(
        "--sidebar-width",
        collapsed ? "80px" : "256px",
      );
    }
  }, [collapsed]);

  // Auto-expand sidebar when navigating FROM collapsed pages to other pages
  useEffect(() => {
    // Pages that auto-collapse the sidebar
    const isCollapsedPage = (path: string) =>
      path.includes("/personas/") || path.includes("/workflows/visual-builder");

    const wasInCollapsedPage = isCollapsedPage(previousPathnameRef.current);
    const isInCollapsedPage = isCollapsedPage(pathname);

    // Only expand when transitioning FROM collapsed page TO elsewhere
    if (wasInCollapsedPage && !isInCollapsedPage && collapsed) {
      setSidebarCollapsed(false);
    }

    previousPathnameRef.current = pathname;
  }, [pathname, collapsed, setSidebarCollapsed]);

  const SidebarContent = ({ isDesktop = false }: { isDesktop?: boolean }) => (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Logo */}
      <div
        className={cn(
          "flex h-16 shrink-0 items-center border-b",
          isDesktop && collapsed
            ? "justify-center px-2"
            : "justify-between px-6",
        )}
      >
        {(!isDesktop || !collapsed) && (
          <Image
            src="/myclone-logo.svg"
            alt="MyClone"
            width={126}
            height={32}
          />
        )}
        {isDesktop && collapsed && (
          <Image src="/Brand.png" alt="MyClone" width={40} height={40} />
        )}
        {isDesktop && !collapsed && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarCollapsed(!collapsed)}
            className="size-8"
          >
            <ChevronLeft className="size-4" />
          </Button>
        )}
      </div>

      {/* Navigation */}
      <nav
        id="sidebar-navigation"
        className="flex-1 space-y-1 overflow-y-auto px-3 py-4"
      >
        {navigation.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));

          // Generate ID for each nav item
          const navId = `sidebar-${item.name.toLowerCase().replace(/\s+/g, "-")}`;

          const isBeta = "beta" in item && item.beta;
          const betaWarning =
            "betaWarning" in item ? (item.betaWarning as string) : undefined;

          const navLink = (
            <Link
              href={item.href}
              id={navId}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all",
                isActive
                  ? "bg-yellow-bright text-black shadow-sm"
                  : "text-foreground/70 hover:bg-yellow-light hover:text-gray-700",
                isDesktop && collapsed && "justify-center",
              )}
            >
              <item.icon
                className={cn(
                  "size-5 shrink-0 transition-colors",
                  isActive
                    ? "text-black"
                    : "text-foreground/50 group-hover:text-gray-700",
                )}
              />
              {(!isDesktop || !collapsed) && (
                <span className="flex items-center gap-2">
                  {item.name}
                  {isBeta && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex items-center rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 border border-amber-300">
                          Beta
                        </span>
                      </TooltipTrigger>
                      {betaWarning && (
                        <TooltipContent
                          side="right"
                          className="max-w-[200px] bg-amber-50 text-amber-900 border-amber-200"
                        >
                          <p className="text-xs">{betaWarning}</p>
                        </TooltipContent>
                      )}
                    </Tooltip>
                  )}
                </span>
              )}
            </Link>
          );

          // Only show tooltip when collapsed on desktop
          if (isDesktop && collapsed) {
            return (
              <Tooltip key={item.name}>
                <TooltipTrigger asChild>{navLink}</TooltipTrigger>
                <TooltipContent
                  side="right"
                  sideOffset={8}
                  className={cn(
                    "border shadow-md text-sm",
                    isBeta
                      ? "bg-amber-50 text-amber-900 border-amber-200 [&>svg]:fill-amber-50"
                      : "bg-yellow-light text-black border-border [&>svg]:fill-yellow-light",
                  )}
                >
                  <div className="flex flex-col gap-1">
                    <span className="flex items-center gap-2">
                      {item.name}
                      {isBeta && (
                        <span className="inline-flex items-center rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 border border-amber-300">
                          Beta
                        </span>
                      )}
                    </span>
                    {isBeta && betaWarning && (
                      <span className="text-xs text-amber-700">
                        {betaWarning}
                      </span>
                    )}
                  </div>
                </TooltipContent>
              </Tooltip>
            );
          }

          return <Fragment key={item.name}>{navLink}</Fragment>;
        })}
      </nav>
    </div>
  );

  return (
    <>
      {/* Mobile Menu Button */}
      <div className="fixed left-0 top-0 z-40 flex h-16 w-full items-center border-b bg-slate-50 px-4 md:hidden">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="md:hidden">
              {mobileOpen ? (
                <X className="size-6" />
              ) : (
                <Menu className="size-6" />
              )}
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-64 p-0">
            <SidebarContent isDesktop={false} />
          </SheetContent>
        </Sheet>
        <div className="ml-4 flex items-center">
          <Image
            src="/myclone-logo.svg"
            alt="MyClone"
            width={100}
            height={26}
          />
        </div>
      </div>

      {/* Desktop Sidebar */}
      <div
        className={cn(
          "group/sidebar fixed inset-y-0 left-0 z-50 hidden border-r bg-slate-50 transition-all duration-300 md:block",
          collapsed ? "w-20" : "w-64",
        )}
      >
        <SidebarContent isDesktop={true} />

        {/* Floating Expand Button - Only when collapsed on desktop, shows on hover */}
        {collapsed && (
          <Button
            variant="outline"
            size="icon"
            onClick={() => setSidebarCollapsed(false)}
            className="absolute right-0 top-6 translate-x-1/2 size-7 rounded-full shadow-sm border border-amber-500 bg-white hover:bg-yellow-bright hover:border-yellow-bright hover:shadow-lg transition-all opacity-0 group-hover/sidebar:opacity-100"
          >
            <ChevronRight className="size-3.5 text-amber-600 hover:text-black" />
          </Button>
        )}
      </div>
    </>
  );
}
