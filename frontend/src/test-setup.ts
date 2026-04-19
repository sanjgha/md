import "@testing-library/jest-dom";

// Polyfill ResizeObserver — not available in jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
