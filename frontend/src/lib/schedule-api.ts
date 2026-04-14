/**
 * Schedule API client.
 * Provides methods for managing scheduled jobs and viewing run history.
 */

import { apiFetch } from "./api";
import type {
  JobResponse,
  JobPatch,
  RunResponse,
  JobRunHistoryEntry,
} from "../pages/schedule/types";

export type {
  JobResponse,
  JobPatch,
  RunResponse,
  JobRunHistoryEntry,
} from "../pages/schedule/types";

/**
 * List all scheduled jobs with their configuration and last run info
 * GET /api/schedule/jobs
 */
export const listJobs = (): Promise<JobResponse[]> =>
  apiFetch("/api/schedule/jobs");

/**
 * Update a scheduled job's configuration
 * PATCH /api/schedule/jobs/:jobId
 */
export const patchJob = (
  jobId: string,
  body: JobPatch
): Promise<JobResponse> =>
  apiFetch(`/api/schedule/jobs/${jobId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

/**
 * Trigger a job to run immediately
 * POST /api/schedule/jobs/:jobId/run
 */
export const runJob = (jobId: string): Promise<RunResponse> =>
  apiFetch(`/api/schedule/jobs/${jobId}/run`, {
    method: "POST",
  });

/**
 * Get run history for all jobs over the last 7 days
 * GET /api/schedule/jobs/history
 *
 * Note: The endpoint doesn't currently accept query parameters,
 * but the interface is kept flexible for future enhancements.
 */
export const getHistory = (_params?: {
  runType?: string;
  from?: string;
  to?: string;
}): Promise<JobRunHistoryEntry[]> =>
  apiFetch("/api/schedule/jobs/history");
