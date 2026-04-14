/**
 * TypeScript types for the Schedule API.
 * These mirror the Pydantic schemas from src/api/schedule/schemas.py.
 */

/**
 * Last run information for a scheduled job
 * Mirrors LastRun schema
 */
export interface LastRun {
  /** ISO datetime string of when the job last ran */
  ran_at: string;
  /** Number of results returned from the last run */
  result_count: number;
}

/**
 * Scheduled job response with configuration and last run info
 * Mirrors JobResponse schema
 */
export interface ScheduledJob {
  /** Unique job identifier (e.g., "eod_scan", "pre_close_scan") */
  job_id: string;
  /** Human-readable display name */
  name: string;
  /** Hour of day (0-23) when job runs */
  hour: number;
  /** Minute of hour (0-59) when job runs */
  minute: number;
  /** Whether the job is currently enabled */
  enabled: boolean;
  /** Whether results are automatically saved to database */
  auto_save: boolean;
  /** Last run information (null if never run) */
  last_run: LastRun | null;
}

/**
 * Partial update body for PATCH /api/schedule/jobs/:jobId
 * Mirrors JobPatch schema
 */
export interface JobPatch {
  /** Optional: hour of day (0-23) */
  hour?: number;
  /** Optional: minute of hour (0-59) */
  minute?: number;
  /** Optional: whether the job is enabled */
  enabled?: boolean;
  /** Optional: whether results are auto-saved */
  auto_save?: boolean;
}

/**
 * Response from triggering a job run
 * Mirrors RunResponse schema
 */
export interface RunResponse {
  /** Status of the run: "ok" or "error" */
  status: "ok" | "error";
  /** Number of results returned from the run */
  result_count: number;
  /** Optional: error detail if status is "error" */
  detail?: string;
}

/**
 * History entry for a job run
 * Matches the response from GET /api/schedule/jobs/history
 */
export interface HistoryEntry {
  /** Human-readable job name */
  job_name: string;
  /** ISO datetime string of when the job ran */
  ran_at: string;
  /** Number of results from this run */
  result_count: number;
}
