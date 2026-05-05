import { create } from "zustand";

interface ViewerState {
  /** Current PDF page (0-based) */
  currentPage: number;
  setCurrentPage: (page: number) => void;
}

export const useViewerStore = create<ViewerState>((set) => ({
  currentPage: 0,
  setCurrentPage: (page) => set({ currentPage: page }),
}));
