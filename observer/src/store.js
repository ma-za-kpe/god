import { create } from 'zustand';

export const useObserverStore = create((set) => ({
  agents: [],
  events: [],
  stats: {},
  snapshot: null,
  observerHealth: { ok: false, lastPollAt: 0, lastError: '' },
  selectedSoulId: null,
  setAgents: (agents) => set({ agents }),
  setEvents: (events) => set({ events }),
  setStats: (stats) => set({ stats }),
  setSnapshot: (snapshot) => set({ snapshot }),
  setObserverHealth: (observerHealth) => set({ observerHealth }),
  selectAgent: (selectedSoulId) => set({ selectedSoulId }),
}));
