// React wrapper around a modular ECharts instance: owns the lifecycle,
// pushes option updates, and resizes with its container.

import { useEffect, useRef } from "react";
import { echarts, type Chart, type EChartsCoreOption } from "../lib/echartsSetup";

export interface EChartProps {
  option: EChartsCoreOption;
  height?: number | string;
  className?: string;
  onReady?: (chart: Chart) => void;
}

export function EChart({ option, height = 320, className, onReady }: EChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<Chart | null>(null);
  const readyRef = useRef(onReady);
  readyRef.current = onReady;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const chart = echarts.init(container);
    chartRef.current = chart;
    readyRef.current?.(chart);
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(container);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true });
  }, [option]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ width: "100%", height, minHeight: 120 }}
    />
  );
}
