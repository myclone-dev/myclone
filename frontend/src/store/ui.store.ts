import { create } from "zustand";

interface UIState {
  isSidebarOpen: boolean;
  sidebarCollapsed: boolean;
  isModalOpen: boolean;
  toggleSidebar: () => void;
  closeSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  openModal: () => void;
  closeModal: () => void;
}

/**
 * Zustand store for UI state
 * Manages client-side UI interactions (modals, sidebar, etc.)
 */
export const useUIStore = create<UIState>((set) => ({
  isSidebarOpen: false,
  sidebarCollapsed: false,
  isModalOpen: false,

  toggleSidebar: () =>
    set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  closeSidebar: () => set({ isSidebarOpen: false }),
  setSidebarCollapsed: (collapsed: boolean) =>
    set({ sidebarCollapsed: collapsed }),
  openModal: () => set({ isModalOpen: true }),
  closeModal: () => set({ isModalOpen: false }),
}));
