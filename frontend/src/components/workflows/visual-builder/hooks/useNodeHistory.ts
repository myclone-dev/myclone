"use client";

import { useCallback, useState } from "react";
import type { Node, Edge } from "reactflow";

interface HistoryState {
  nodes: Node[];
  edges: Edge[];
}

interface UseNodeHistoryReturn {
  pushState: (nodes: Node[], edges: Edge[]) => void;
  undo: () => HistoryState | null;
  redo: () => HistoryState | null;
  canUndo: boolean;
  canRedo: boolean;
}

const MAX_HISTORY_SIZE = 50;

/**
 * useNodeHistory - Manages undo/redo history for ReactFlow nodes and edges
 * Stores deep copies of state to allow restoration
 */
export function useNodeHistory(): UseNodeHistoryReturn {
  // Use state for history to properly trigger re-renders
  const [history, setHistory] = useState<HistoryState[]>([]);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [isUndoRedoAction, setIsUndoRedoAction] = useState(false);

  const pushState = useCallback(
    (nodes: Node[], edges: Edge[]) => {
      // Skip if this is triggered by an undo/redo action
      if (isUndoRedoAction) {
        setIsUndoRedoAction(false);
        return;
      }

      const newState: HistoryState = {
        nodes: JSON.parse(JSON.stringify(nodes)),
        edges: JSON.parse(JSON.stringify(edges)),
      };

      setHistory((prevHistory) => {
        // Remove any future states if we're not at the end
        const newHistory = prevHistory.slice(0, currentIndex + 1);

        // Add new state
        newHistory.push(newState);

        // Limit history size
        if (newHistory.length > MAX_HISTORY_SIZE) {
          newHistory.shift();
        }

        return newHistory;
      });

      setCurrentIndex((prevIndex) =>
        Math.min(prevIndex + 1, MAX_HISTORY_SIZE - 1),
      );
    },
    [currentIndex, isUndoRedoAction],
  );

  const undo = useCallback((): HistoryState | null => {
    if (currentIndex <= 0) return null;

    setIsUndoRedoAction(true);
    const newIndex = currentIndex - 1;
    setCurrentIndex(newIndex);

    return history[newIndex];
  }, [currentIndex, history]);

  const redo = useCallback((): HistoryState | null => {
    if (currentIndex >= history.length - 1) return null;

    setIsUndoRedoAction(true);
    const newIndex = currentIndex + 1;
    setCurrentIndex(newIndex);

    return history[newIndex];
  }, [currentIndex, history]);

  return {
    pushState,
    undo,
    redo,
    canUndo: currentIndex > 0,
    canRedo: currentIndex < history.length - 1,
  };
}
