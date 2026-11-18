// Draws the report chart from the JSON the server rendered, and redraws after each live update.
(() => {
  let chart = null;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function colours() {
    const css = getComputedStyle(document.documentElement);
    const v = (name) => css.getPropertyValue(name).trim();
    return { ink: v("--ink"), soft: v("--ink-soft"), line: v("--line"),
             series: [v("--ink"), v("--accent"), v("--ok"), v("--warn"), "#7f77dd", "#d4537e", v("--ink-soft")] };
  }

  function draw() {
    const data = document.getElementById("report-chart-data");
    const canvas = document.getElementById("report-chart");
    if (chart) { chart.destroy(); chart = null; }
    if (!data || !canvas || !window.Chart) return;
    const spec = JSON.parse(data.textContent);
    const c = colours();
    const bar = spec.type === "bar";
    canvas.parentElement.style.height = bar ? `${Math.max(160, spec.labels.length * 30 + 40)}px` : "320px";
    chart = new Chart(canvas, {
      type: spec.type,
      data: {
        labels: spec.labels,
        datasets: spec.series.map((s, i) => ({
          label: s.name,
          data: s.data,
          borderColor: c.series[i % c.series.length],
          backgroundColor: bar ? c.series[0] : c.series[i % c.series.length],
          borderRadius: bar ? 6 : 0,
          tension: 0.3,
          pointRadius: spec.labels.length > 40 ? 0 : 3,
        })),
      },
      options: {
        indexAxis: bar ? "y" : "x",
        maintainAspectRatio: false,
        animation: still ? false : { duration: 700, easing: "easeOutCubic" },
        plugins: { legend: { display: !bar && spec.series.length > 1, labels: { color: c.ink } } },
        scales: {
          x: { ticks: { color: c.soft }, grid: { color: c.line } },
          y: { ticks: { color: c.soft }, grid: { color: bar ? "transparent" : c.line }, beginAtZero: true },
        },
      },
    });
  }

  // Print or save as PDF uses the browser's own dialog; the print styles in ui.css lay it out.
  document.addEventListener("click", (e) => { if (e.target.closest("[data-print]")) window.print(); });
  document.addEventListener("DOMContentLoaded", draw);
  document.addEventListener("htmx:afterSettle", draw);
})();
