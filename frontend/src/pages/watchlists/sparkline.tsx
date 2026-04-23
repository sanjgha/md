/**
 * Sparkline — mini line chart showing intraday price movement.
 *
 * Renders an SVG polyline from intraday close prices.
 * Color indicates direction: green (up), red (down), gray (flat/no data).
 */

import { Component } from "solid-js";

export interface IntradayPoint {
  time: string;
  close: number;
}

interface SparklineProps {
  data: IntradayPoint[];
  color: "green" | "red" | "gray";
  width: number;
  height: number;
}

const COLOR_MAP = {
  green: "#22c55e",
  red: "#ef4444",
  gray: "#94a3b8",
};

export const Sparkline: Component<SparklineProps> = (props) => {
  const color = () => COLOR_MAP[props.color];

  // Normalize close prices to fit in SVG height (0 to height-1)
  const normalizeData = (): string => {
    if (props.data.length === 0) {
      // No data: render flat line in middle
      const midY = Math.floor(props.height / 2);
      return `0,${midY} ${props.width},${midY}`;
    }

    if (props.data.length === 1) {
      // Single point: dot in middle
      const midY = Math.floor(props.height / 2);
      const midX = Math.floor(props.width / 2);
      return `${midX},${midY}`;
    }

    const closes = props.data.map((d) => d.close);
    const minClose = Math.min(...closes);
    const maxClose = Math.max(...closes);
    const range = maxClose - minClose || 1; // Avoid divide by zero

    // Map each data point to (x, y) coordinates
    const points = props.data.map((d, i) => {
      const x = (i / (props.data.length - 1)) * props.width;
      // Invert y because SVG coordinates: 0 is top
      const normalizedY = (d.close - minClose) / range;
      const y = props.height - 1 - normalizedY * (props.height - 1);
      return `${x},${y}`;
    });

    return points.join(" ");
  };

  return (
    <svg
      width={props.width}
      height={props.height}
      viewBox={`0 0 ${props.width} ${props.height}`}
      aria-hidden="true"
      style="display: block;"
    >
      <polyline
        points={normalizeData()}
        fill="none"
        stroke={color()}
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  );
};
