import { describe, it, expect } from "vitest";
import { getDateRange, getDefaultPanel2Resolution } from "./chart-utils";

describe("chart-utils", () => {
  describe("getDateRange", () => {
    it("calculates 5m range (today)", () => {
      const result = getDateRange("5m");
      expect(result.from).toBe(result.to);  // Same day
    });

    it("calculates 15m range (5 days)", () => {
      const result = getDateRange("15m");
      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBeCloseTo(5, 0);
    });

    it("calculates 1H range (5 days)", () => {
      const result = getDateRange("1h");
      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBeCloseTo(5, 0);
    });

    it("calculates D with 1M range (30 days)", () => {
      const result = getDateRange("D", "1M");
      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBeCloseTo(30, 0);
    });

    it("calculates D with 3M range (90 days)", () => {
      const result = getDateRange("D", "3M");
      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBeCloseTo(90, 0);
    });

    it("calculates D with 1Y range (360 days)", () => {
      const result = getDateRange("D", "1Y");
      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBeCloseTo(360, 0);
    });
  });

  describe("getDefaultPanel2Resolution", () => {
    it("returns 1h for 5m", () => {
      expect(getDefaultPanel2Resolution("5m")).toBe("1h");
    });

    it("returns 1h for 15m", () => {
      expect(getDefaultPanel2Resolution("15m")).toBe("1h");
    });

    it("returns D for 1h", () => {
      expect(getDefaultPanel2Resolution("1h")).toBe("D");
    });

    it("returns 1h for D", () => {
      expect(getDefaultPanel2Resolution("D")).toBe("1h");
    });
  });
});
