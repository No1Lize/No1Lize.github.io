"use client";

import * as echarts from "echarts";
import { useEffect, useMemo, useRef } from "react";
import { useArticles } from "@/lib/use-articles";

function monthKey(date: Date) {
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function SectorChart() {
  const ref = useRef<HTMLDivElement>(null);
  const { articles, generatedAt } = useArticles();
  const seriesData = useMemo(() => {
    const parsed = new Date(generatedAt);
    const end = Number.isFinite(parsed.getTime()) ? parsed : new Date();
    const keys = Array.from({ length: 6 }, (_, index) => {
      const date = new Date(
        Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - (5 - index), 1),
      );
      return monthKey(date);
    });
    const counts = new Map(
      keys.flatMap((key) => [
        [`${key}-中国`, 0],
        [`${key}-美国`, 0],
      ]),
    );
    for (const article of articles) {
      const date = new Date(`${article.publishedAt}T00:00:00Z`);
      const key = `${monthKey(date)}-${article.region}`;
      if (counts.has(key)) counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return {
      labels: keys.map((key) => `${Number(key.slice(5))}月`),
      china: keys.map((key) => counts.get(`${key}-中国`) ?? 0),
      usa: keys.map((key) => counts.get(`${key}-美国`) ?? 0),
    };
  }, [articles, generatedAt]);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "svg" });
    chart.setOption({
      animation: false,
      backgroundColor: "transparent",
      textStyle: { color: "#a4b0aa", fontFamily: "Inter, sans-serif" },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#101e1b",
        borderColor: "#263833",
        textStyle: { color: "#f1f3ed" },
      },
      legend: {
        data: ["中国", "美国"],
        right: 8,
        textStyle: { color: "#a4b0aa" },
      },
      grid: { left: 40, right: 16, top: 38, bottom: 28 },
      xAxis: {
        type: "category",
        data: seriesData.labels,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#263833" } },
        axisLabel: { color: "#77847e" },
      },
      yAxis: {
        type: "value",
        name: "事件数",
        minInterval: 1,
        nameTextStyle: { color: "#77847e" },
        splitLine: { lineStyle: { color: "#1b2c28" } },
        axisLabel: { color: "#77847e" },
      },
      series: [
        {
          name: "中国",
          type: "line",
          data: seriesData.china,
          smooth: true,
          symbolSize: 7,
          lineStyle: { color: "#8dbb9d", width: 2 },
          itemStyle: { color: "#8dbb9d" },
          areaStyle: { color: "rgba(141,187,157,.08)" },
        },
        {
          name: "美国",
          type: "line",
          data: seriesData.usa,
          smooth: true,
          symbolSize: 7,
          lineStyle: { color: "#8cb7d9", width: 2 },
          itemStyle: { color: "#8cb7d9" },
          areaStyle: { color: "rgba(140,183,217,.06)" },
        },
      ],
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [seriesData]);

  return (
    <div>
      <div
        ref={ref}
        className="chart-canvas"
        role="img"
        aria-label={`最近六个月公开事件数量：中国 ${seriesData.china.join("、")}；美国 ${seriesData.usa.join("、")}。`}
      />
      <details className="chart-table">
        <summary>查看数据表</summary>
        <table>
          <thead>
            <tr>
              <th>月份</th>
              {seriesData.labels.map((month, index) => (
                <th key={`${month}-${index}`}>{month}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>中国</th>
              {seriesData.china.map((value, index) => (
                <td key={index}>{value}</td>
              ))}
            </tr>
            <tr>
              <th>美国</th>
              {seriesData.usa.map((value, index) => (
                <td key={index}>{value}</td>
              ))}
            </tr>
          </tbody>
        </table>
      </details>
    </div>
  );
}
