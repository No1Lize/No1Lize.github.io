"use client";

import * as echarts from "echarts";
import { useEffect, useRef } from "react";

const months = ["10月", "11月", "12月", "1月", "2月", "3月"];
const china = [7, 9, 8, 12, 11, 14];
const usa = [12, 14, 13, 18, 16, 22];

export function SectorChart() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "svg" });
    chart.setOption({
      animation: false,
      backgroundColor: "transparent",
      textStyle: { color: "#a4b0aa", fontFamily: "Inter, sans-serif" },
      tooltip: { trigger: "axis", backgroundColor: "#101e1b", borderColor: "#263833", textStyle: { color: "#f1f3ed" } },
      legend: { data: ["中国", "美国"], right: 8, textStyle: { color: "#a4b0aa" } },
      grid: { left: 40, right: 16, top: 38, bottom: 28 },
      xAxis: { type: "category", data: months, boundaryGap: false, axisLine: { lineStyle: { color: "#263833" } }, axisLabel: { color: "#77847e" } },
      yAxis: { type: "value", name: "事件数", nameTextStyle: { color: "#77847e" }, splitLine: { lineStyle: { color: "#1b2c28" } }, axisLabel: { color: "#77847e" } },
      series: [
        { name: "中国", type: "line", data: china, smooth: true, symbolSize: 7, lineStyle: { color: "#8dbb9d", width: 2 }, itemStyle: { color: "#8dbb9d" }, areaStyle: { color: "rgba(141,187,157,.08)" } },
        { name: "美国", type: "line", data: usa, smooth: true, symbolSize: 7, lineStyle: { color: "#8cb7d9", width: 2 }, itemStyle: { color: "#8cb7d9" }, areaStyle: { color: "rgba(140,183,217,.06)" } },
      ],
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, []);

  return (
    <div>
      <div ref={ref} className="chart-canvas" role="img" aria-label="过去六个月中美公开事件样本数量趋势：中国由7升至14，美国由12升至22。" />
      <details className="chart-table">
        <summary>查看数据表</summary>
        <table>
          <thead><tr><th>月份</th>{months.map((month) => <th key={month}>{month}</th>)}</tr></thead>
          <tbody>
            <tr><th>中国</th>{china.map((value, i) => <td key={i}>{value}</td>)}</tr>
            <tr><th>美国</th>{usa.map((value, i) => <td key={i}>{value}</td>)}</tr>
          </tbody>
        </table>
      </details>
    </div>
  );
}
