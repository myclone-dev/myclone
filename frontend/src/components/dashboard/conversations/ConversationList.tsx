"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  useUserConversations,
  usePersonaConversations,
} from "@/lib/queries/conversations";
import { Button } from "@/components/ui/button";
import { ConversationCard } from "./ConversationCard";

interface ConversationListProps {
  userId: string;
  personaId?: string | null;
}

const ITEMS_PER_PAGE = 20;

export function ConversationList({ userId, personaId }: ConversationListProps) {
  const [page, setPage] = useState(0);

  // Use persona-specific hook if personaId is provided, otherwise use user-wide hook
  const userConversations = useUserConversations(
    personaId ? undefined : userId,
    {
      limit: ITEMS_PER_PAGE,
      offset: page * ITEMS_PER_PAGE,
    },
  );

  const personaConversationsHook = usePersonaConversations(
    personaId || undefined,
    {
      limit: ITEMS_PER_PAGE,
      offset: page * ITEMS_PER_PAGE,
    },
  );

  const { data, isLoading, error } = personaId
    ? personaConversationsHook
    : userConversations;

  // Get all conversations without filtering
  const conversations = data?.conversations || [];
  const total = data?.total ?? 0;
  const hasMore = data?.has_more ?? false;
  const totalPages = Math.ceil(total / ITEMS_PER_PAGE);

  // Calculate display range
  const startItem = page * ITEMS_PER_PAGE + 1;
  const endItem = Math.min((page + 1) * ITEMS_PER_PAGE, total);

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages: (number | "ellipsis")[] = [];
    const maxVisiblePages = 5;

    if (totalPages <= maxVisiblePages) {
      // Show all pages if total is small
      for (let i = 0; i < totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(0);

      if (page > 2) {
        pages.push("ellipsis");
      }

      // Show pages around current page
      const start = Math.max(1, page - 1);
      const end = Math.min(totalPages - 2, page + 1);

      for (let i = start; i <= end; i++) {
        if (!pages.includes(i)) {
          pages.push(i);
        }
      }

      if (page < totalPages - 3) {
        pages.push("ellipsis");
      }

      // Always show last page
      if (!pages.includes(totalPages - 1)) {
        pages.push(totalPages - 1);
      }
    }

    return pages;
  };

  // Early return AFTER all hooks
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="h-20 animate-pulse rounded-lg bg-muted/50 border"
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center">
        <p className="font-medium text-red-900">Failed to load conversations</p>
        <p className="mt-2 text-sm text-red-700">
          {error instanceof Error ? error.message : "An error occurred"}
        </p>
      </div>
    );
  }

  // Show empty state
  if (conversations.length === 0 && page === 0) {
    return (
      <div className="rounded-lg border border-dashed p-12 text-center">
        <p className="text-lg font-medium">No conversations yet</p>
        <p className="mt-2 text-sm text-muted-foreground">
          When visitors chat with your AI clone, their conversations will appear
          here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Conversation List */}
      <div className="space-y-3">
        {conversations.map((conversation, index) => (
          <ConversationCard
            key={conversation.id}
            conversation={conversation}
            isFirstCard={index === 0}
          />
        ))}
      </div>

      {/* Pagination */}
      {total > 0 && (
        <div className="flex flex-col gap-4 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {startItem} - {endItem} of {total} conversations
          </p>

          <div className="flex items-center gap-1">
            {/* Previous Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="h-8 w-8 p-0"
            >
              <ChevronLeft className="size-4" />
              <span className="sr-only">Previous page</span>
            </Button>

            {/* Page Numbers */}
            <div className="flex items-center gap-1">
              {getPageNumbers().map((pageNum, idx) =>
                pageNum === "ellipsis" ? (
                  <span
                    key={`ellipsis-${idx}`}
                    className="px-2 text-muted-foreground"
                  >
                    ...
                  </span>
                ) : (
                  <Button
                    key={pageNum}
                    variant={page === pageNum ? "default" : "outline"}
                    size="sm"
                    onClick={() => setPage(pageNum)}
                    className="h-8 w-8 p-0"
                  >
                    {pageNum + 1}
                  </Button>
                ),
              )}
            </div>

            {/* Next Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasMore && page >= totalPages - 1}
              className="h-8 w-8 p-0"
            >
              <ChevronRight className="size-4" />
              <span className="sr-only">Next page</span>
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
