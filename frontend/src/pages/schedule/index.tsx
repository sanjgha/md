/**
 * Schedule Page
 *
 * Displays all scheduled jobs with inline editing and run controls.
 */

import { createResource, Show, Suspense } from "solid-js";
import { listJobs, patchJob, runJobNow } from "../../lib/schedule-api";
import { JobCard } from "./job-card";
import type { JobPatch } from "./types";

export default function SchedulePage() {
  // Fetch jobs on mount
  const [jobs, { refetch }] = createResource(listJobs);

  /**
   * Handle patch callback - update job then refresh
   */
  const handlePatch = async (jobId: string, patch: JobPatch) => {
    await patchJob(jobId, patch);
    refetch();
  };

  /**
   * Handle run now callback
   */
  const handleRun = async (jobId: string) => {
    return await runJobNow(jobId);
  };

  return (
    <div class="flex flex-col h-full">
      <div class="border-b px-4 py-3">
        <h1 class="text-xl font-semibold">Scheduled Jobs</h1>
      </div>
      <div class="flex-1 overflow-auto p-4">
        <Suspense fallback={<p>Loading…</p>}>
          <Show
            when={!jobs.error}
            fallback={<p class="error-message">Failed to load jobs: {jobs.error?.message}</p>}
          >
            <Show
              when={jobs() && jobs()!.length > 0}
              fallback={<p class="text-gray-500">No scheduled jobs configured.</p>}
            >
              <div class="space-y-4">
                {jobs()?.map((job) => (
                  <JobCard
                    job={job}
                    onPatch={handlePatch}
                    onRun={handleRun}
                  />
                ))}
              </div>
            </Show>
          </Show>
        </Suspense>
      </div>
    </div>
  );
}
