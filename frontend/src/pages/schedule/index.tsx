/**
 * Schedule Page
 *
 * Displays all scheduled jobs with inline editing and run controls.
 */

import { createResource, Show, Suspense, For } from "solid-js";
import { listJobs, patchJob, runJobNow, getHistory } from "../../lib/schedule-api";
import { JobCard } from "./job-card";
import type { JobPatch, HistoryEntry } from "./types";

export default function SchedulePage() {
  // Fetch jobs on mount
  const [jobs, { refetch }] = createResource(listJobs);

  // Fetch run history
  const [history] = createResource<HistoryEntry[]>(getHistory);

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

  /**
   * Format ISO datetime string to readable date/time in ET
   */
  function formatRanAt(isoStr: string): string {
    const d = new Date(isoStr);
    return (
      d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
      " " +
      d.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    );
  }

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

        {/* Run History Section */}
        <section class="history-section">
          <h2>Run History</h2>
          <Show when={!history.loading} fallback={<p>Loading…</p>}>
            <Show
              when={history() && history()!.length > 0}
              fallback={
                <p class="empty-state">
                  No runs yet. Jobs will appear here after their first
                  execution.
                </p>
              }
            >
              <table class="history-table">
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Ran At (ET)</th>
                    <th>Results</th>
                  </tr>
                </thead>
                <tbody>
                  <For each={history()}>
                    {(entry) => (
                      <tr>
                        <td>{entry.job_name}</td>
                        <td>{formatRanAt(entry.ran_at)}</td>
                        <td>{entry.result_count}</td>
                      </tr>
                    )}
                  </For>
                </tbody>
              </table>
            </Show>
          </Show>
        </section>
      </div>
    </div>
  );
}
