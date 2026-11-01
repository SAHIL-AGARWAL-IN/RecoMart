/* Dashboard charts (Chart.js). One small helper, RMCharts, gives every chart the same look:
   thin marks, rounded bar ends, quiet gridlines, a tooltip on hover, and colours read from the
   CSS custom properties in dashboard.css, so light and dark mode both work. */
(() => {
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const rupees = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
  const number = new Intl.NumberFormat("en-IN");

  function theme() {
    return { mark: css("--rm-chart"), soft: css("--rm-chart-soft"), muted: css("--rm-chart-muted"),
             grid: css("--rm-grid"), axis: css("--rm-axis"), surface: css("--rm-surface"), ink: css("--rm-ink") };
  }

  function baseOptions({ money = false, percent = false, horizontal = false } = {}) {
    const t = theme();
    const format = (v) => (money ? rupees.format(v) : percent ? `${(v * 100).toFixed(1)}%` : number.format(v));
    const valueAxis = { beginAtZero: true, grid: { color: t.grid, drawTicks: false }, border: { display: false },
                        ticks: { color: t.axis, padding: 6, maxTicksLimit: 6, callback: format } };
    const categoryAxis = { grid: { display: false }, border: { color: t.grid },
                           ticks: { color: t.axis, maxRotation: 0, autoSkipPadding: 12 } };
    return {
      maintainAspectRatio: false,
      animation: reduceMotion ? false : { duration: 400 },
      indexAxis: horizontal ? "y" : "x",
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false }, // one series per chart: the panel title names it
        tooltip: {
          backgroundColor: t.ink, titleColor: t.surface, bodyColor: t.surface, padding: 10, cornerRadius: 8,
          displayColors: false, callbacks: { label: (ctx) => format(horizontal ? ctx.parsed.x : ctx.parsed.y) },
        },
      },
      scales: horizontal ? { x: valueAxis, y: categoryAxis } : { x: categoryAxis, y: valueAxis },
    };
  }

  function dataFrom(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  function line(canvas, labels, values, { money = false, highlightIndex = null } = {}) {
    const t = theme();
    const radius = values.map((_, i) => (i === highlightIndex ? 6 : highlightIndex === null ? 0 : 3));
    return new Chart(canvas, {
      type: "line",
      data: { labels, datasets: [{
        data: values, borderColor: t.mark, backgroundColor: t.soft, borderWidth: 2, tension: 0.25,
        fill: highlightIndex === null, pointRadius: radius, pointHoverRadius: 6,
        pointBackgroundColor: t.mark, pointBorderColor: t.surface, pointBorderWidth: 2,
      }] },
      options: baseOptions({ money }),
    });
  }

  function bar(canvas, labels, values, { money = false, percent = false, horizontal = false } = {}) {
    const t = theme();
    const radius = horizontal ? { topRight: 4, bottomRight: 4 } : { topLeft: 4, topRight: 4 };
    return new Chart(canvas, {
      type: "bar",
      data: { labels, datasets: [{ data: values, backgroundColor: t.mark, hoverBackgroundColor: t.mark,
                                   borderRadius: radius, borderSkipped: horizontal ? "start" : "bottom",
                                   maxBarThickness: horizontal ? 22 : 18 }] },
      options: baseOptions({ money, percent, horizontal }),
    });
  }

  /* One cluster in colour, every other product in grey (small multiples, one per cluster). */
  function highlightScatter(canvas, points, cluster) {
    const t = theme();
    const mine = points.filter((p) => p.c === cluster);
    const rest = points.filter((p) => p.c !== cluster);
    return new Chart(canvas, {
      type: "scatter",
      data: { datasets: [
        { data: rest, backgroundColor: t.muted, pointRadius: 2, pointHoverRadius: 2 },
        { data: mine, backgroundColor: t.mark, borderColor: t.surface, borderWidth: 1.5, pointRadius: 4, pointHoverRadius: 6 },
      ] },
      options: {
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            filter: (item) => item.datasetIndex === 1, // only the highlighted cluster gets a tooltip
            backgroundColor: t.ink, titleColor: t.surface, bodyColor: t.surface, displayColors: false,
            callbacks: { label: (ctx) => ctx.raw.name },
          },
        },
        scales: { x: { display: false }, y: { display: false } },
      },
    });
  }

  window.RMCharts = { line, bar, highlightScatter, dataFrom, rupees, number };

  // ---- Overview page ----
  document.addEventListener("DOMContentLoaded", () => {
    const daily = dataFrom("daily-data");
    if (daily) {
      const labels = daily.map((d) => new Date(d.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" }));
      line(document.getElementById("revenue-chart"), labels, daily.map((d) => d.revenue), { money: true });
      bar(document.getElementById("orders-chart"), labels, daily.map((d) => d.orders));
    }
    const top = dataFrom("top-data");
    if (top && top.length) {
      bar(document.getElementById("top-chart"), top.map((p) => p.product_name.length > 26 ? `${p.product_name.slice(0, 25)}…` : p.product_name),
          top.map((p) => p.units), { horizontal: true });
    }
    const categories = dataFrom("category-data");
    if (categories && categories.length) {
      bar(document.getElementById("category-chart"), categories.map((c) => c.category),
          categories.map((c) => Number(c.revenue)), { horizontal: true, money: true });
    }
  });
})();
