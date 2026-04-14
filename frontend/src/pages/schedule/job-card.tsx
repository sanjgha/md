/**
 * JobCard Component
 *
 * Displays a single scheduled job with inline time edit, enable toggle,
 * auto-save toggle, and Run Now button.
 */

import { Show, createSignal } from "solid-js";
import type { ScheduledJob, JobPatch, RunResponse } from "./types";

interface JobCardProps {
  job: ScheduledJob;
  onPatch: (jobId: string, patch: JobPatch) => Promise<void>;
  onRun: (jobId: string) => Promise<RunResponse>;
}

export function JobCard(props: JobCardProps) {
  // Local state for inline time editing
  const [editHour, setEditHour] = createSignal(props.job.hour);
  const [editMinute, setEditMinute] = createSignal(props.job.minute);
  const [hourError, setHourError] = createSignal<string | null>(null);
  const [minuteError, setMinuteError] = createSignal<string | null>(null);

  // Loading/error states
  const [isPatching, setIsPatching] = createSignal(false);
  const [isRunning, setIsRunning] = createSignal(false);
  const [patchError, setPatchError] = createSignal<string | null>(null);
  const [runResult, setRunResult] = createSignal<string | null>(null);

  /**
   * Format ISO datetime string for display
   */
  const formatDateTime = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  };

  /**
   * Handle time input blur - validate and patch
   */
  const handleTimeBlur = async () => {
    const hour = editHour();
    const minute = editMinute();

    // Validate hour
    if (hour < 0 || hour > 23) {
      setHourError("Hour must be 0-23");
      return;
    }
    setHourError(null);

    // Validate minute
    if (minute < 0 || minute > 59) {
      setMinuteError("Minute must be 0-59");
      return;
    }
    setMinuteError(null);

    // Check if values actually changed
    if (hour === props.job.hour && minute === props.job.minute) {
      return;
    }

    // Patch the update
    setIsPatching(true);
    setPatchError(null);

    try {
      await props.onPatch(props.job.job_id, { hour, minute });
    } catch (err) {
      setPatchError(err instanceof Error ? err.message : "Failed to update time");
      // Reset to original values on error
      setEditHour(props.job.hour);
      setEditMinute(props.job.minute);
    } finally {
      setIsPatching(false);
    }
  };

  /**
   * Handle enable toggle change
   */
  const handleEnabledChange = async () => {
    setIsPatching(true);
    setPatchError(null);

    try {
      await props.onPatch(props.job.job_id, {
        enabled: !props.job.enabled,
      });
    } catch (err) {
      setPatchError(
        err instanceof Error ? err.message : "Failed to update enabled state"
      );
    } finally {
      setIsPatching(false);
    }
  };

  /**
   * Handle auto-save toggle change
   */
  const handleAutoSaveChange = async () => {
    setIsPatching(true);
    setPatchError(null);

    try {
      await props.onPatch(props.job.job_id, {
        auto_save: !props.job.auto_save,
      });
    } catch (err) {
      setPatchError(
        err instanceof Error ? err.message : "Failed to update auto-save"
      );
    } finally {
      setIsPatching(false);
    }
  };

  /**
   * Handle Run Now button click
   */
  const handleRunNow = async () => {
    setIsRunning(true);
    setRunResult(null);
    setPatchError(null);

    try {
      const response = await props.onRun(props.job.job_id);

      if (response.status === "ok") {
        setRunResult(`✓ ${response.result_count} tickers`);
      } else {
        setRunResult(`✗ ${response.detail || "Failed"}`);
      }
    } catch (err) {
      setRunResult(
        `✗ ${err instanceof Error ? err.message : "Failed to run job"}`
      );
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div class="job-card">
      {/* Header with job name and last run info */}
      <div class="job-card-header">
        <h3>{props.job.name}</h3>
        <Show
          when={props.job.last_run}
          fallback={
            <span class="last-run-info">
              Last run: <span class="never-run">Never run</span>
            </span>
          }
        >
          {(lastRun) => (
            <span class="last-run-info">
              Last run:{" "}
              <span class="last-run-time">
                {formatDateTime(lastRun().ran_at)}
              </span>{" "}
              <span class="last-run-count">
                ✓ {lastRun().result_count} tickers
              </span>
            </span>
          )}
        </Show>
      </div>

      {/* Schedule info */}
      <div class="job-card-schedule">
        <span class="schedule-days">⏰ Mon–Fri</span>
      </div>

      {/* Controls row */}
      <div class="job-card-controls">
        {/* Time input */}
        <div class="time-control">
          <label class="time-label">Time:</label>
          <div class="time-inputs">
            <input
              type="number"
              min="0"
              max="23"
              value={editHour()}
              onInput={(e) => setEditHour(parseInt(e.currentTarget.value) || 0)}
              onBlur={handleTimeBlur}
              disabled={isPatching()}
              aria-label="Hour"
              aria-invalid={hourError() !== null}
              class="time-input"
            />
            <span class="time-separator">:</span>
            <input
              type="number"
              min="0"
              max="59"
              value={editMinute()}
              onInput={(e) => setEditMinute(parseInt(e.currentTarget.value) || 0)}
              onBlur={handleTimeBlur}
              disabled={isPatching()}
              aria-label="Minute"
              aria-invalid={minuteError() !== null}
              class="time-input"
            />
          </div>
          <Show when={hourError() || minuteError()}>
            <div class="time-error">
              {hourError() || minuteError()}
            </div>
          </Show>
        </div>

        {/* Auto-save toggle */}
        <div class="toggle-control">
          <label class="toggle-label">
            Auto-save:
            <input
              type="checkbox"
              checked={props.job.auto_save}
              onChange={handleAutoSaveChange}
              disabled={isPatching()}
              class="toggle-checkbox"
            />
            <span class="toggle-slider"></span>
          </label>
        </div>

        {/* Run Now button */}
        <button
          onClick={handleRunNow}
          disabled={isRunning()}
          class="run-now-button"
        >
          <Show when={isRunning()} fallback="▶ Run Now">
            Running...
          </Show>
        </button>
      </div>

      {/* Enable toggle (separate row) */}
      <div class="job-card-enable-row">
        <label class="enable-toggle-label">
          <input
            type="checkbox"
            checked={props.job.enabled}
            onChange={handleEnabledChange}
            disabled={isPatching()}
            class="enable-checkbox"
          />
          <span class="enable-slider"></span>
          <span class="enable-text">
            {props.job.enabled ? "Enabled" : "Paused"}
          </span>
        </label>
      </div>

      {/* Error message */}
      <Show when={patchError()}>
        <div class="error-message">{patchError()}</div>
      </Show>

      {/* Run result */}
      <Show when={runResult()}>
        <div
          class={`run-result ${
            runResult()?.startsWith("✓") ? "run-success" : "run-error"
          }`}
        >
          {runResult()}
        </div>
      </Show>
    </div>
  );
}
