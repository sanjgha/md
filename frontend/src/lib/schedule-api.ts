/**
 * Schedule API client.
 * Provides methods for managing scheduled jobs and viewing run history.
 */

import { apiFetch } from "./api";
import type {
  ScheduledJob,
  JobPatch,
  RunResponse,
  HistoryEntry,
} from "../pages/schedule/types";

export type {
  ScheduledJob,
  JobPatch,
  RunResponse,
  HistoryEntry,
} from "../pages/schedule/types";

/**
 * List all scheduled jobs with their configuration and last run info
 * GET /api/schedule/jobs
 */
export const listJobs = (): Promise<ScheduledJob[]> =>
  apiFetch("/api/schedule/jobs");

/**
 * Update a scheduled job's configuration
 * PATCH /api/schedule/jobs/:jobId
 */
export const patchJob = (
  jobId: string,
  body: JobPatch
): Promise<ScheduledJob> =>
  apiFetch(`/api/schedule/jobs/${jobId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

/**
 * Trigger a job to run immediately
 * POST /api/schedule/jobs/:jobId/run
 */
export const runJobNow = (jobId: string): Promise<RunResponse> =>
  apiFetch(`/api/schedule/jobs/${jobId}/run`, {
    method: "POST",
  });

/**
 * Get run history for all jobs over the last 7 days
 * GET /api/schedule/jobs/history
 */
export const getHistory = (): Promise<HistoryEntry[]> =>
  apiFetch("/api/schedule/jobs/history");
