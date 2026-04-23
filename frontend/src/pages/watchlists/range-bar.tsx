/**
 * RangeBar — horizontal gradient bar showing current price position.
 *
 * Renders a gradient background (red -> yellow -> green) with a vertical
 * marker showing where the current price sits within the day's low/high range.
 */

import { Component } from "solid-js";

interface RangeBarProps {
  low: number | null;
  high: number | null;
  current: number;
  width: number;
  height: number;
}

export const RangeBar: Component<RangeBarProps> = (props) => {
  // Calculate marker position as percentage (0-100%)
  const markerPosition = () => {
    if (props.low === null || props.high === null || props.low === props.high) {
      return 50; // Center if no range data
    }
    const range = props.high - props.low;
    if (range === 0) return 50;
    const position = ((props.current - props.low) / range) * 100;
    return Math.max(0, Math.min(100, position)); // Clamp to 0-100
  };

  const markerLeft = () => `${markerPosition()}%`;

  return (
    <div
      class="range-bar"
      style={{
        position: "relative",
        width: `${props.width}px`,
        height: `${props.height}px`,
      }}
    >
      {/* Gradient background */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "linear-gradient(90deg, #ef4444 0%, #fbbf24 50%, #22c55e 100%)",
          "border-radius": "2px",
          opacity: "0.5",
        }}
      />

      {/* Position marker */}
      <div
        class="range-bar__marker"
        style={{
          position: "absolute",
          top: "0",
          bottom: "0",
          width: "2px",
          "background-color": "#fbbf24",
          left: markerLeft(),
          "box-shadow": "0 0 3px #fbbf24",
        }}
      />
    </div>
  );
};
