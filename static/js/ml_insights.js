/* ML Insights page: K-selection charts, cluster small multiples, CTR chart, Retrain button, A/B switch. */
function drawInsightCharts() {
  const { line, bar, highlightScatter, dataFrom } = window.RMCharts;

  // ---- Choosing K: inertia (elbow) and silhouette, chosen K highlighted ----
  const kScores = dataFrom("k-scores");
  const chosenK = dataFrom("chosen-k");
  if (kScores) {
    const labels = kScores.map((row) => `K=${row.k}`);
    const chosenIndex = kScores.findIndex((row) => row.k === chosenK);
    line(document.getElementById("elbow-chart"), labels, kScores.map((row) => row.inertia), { highlightIndex: chosenIndex });
    line(document.getElementById("silhouette-chart"), labels, kScores.map((row) => row.silhouette), { highlightIndex: chosenIndex });
  }

  // ---- Clusters: one small scatter per cluster (small multiples) ----
  const points = dataFrom("scatter-points");
  if (points) {
    document.querySelectorAll("canvas[data-facet]").forEach((canvas) => {
      highlightScatter(canvas, points, Number(canvas.dataset.facet));
    });
  }

  // ---- Click-through rate per recommendation strip ----
  const ctr = dataFrom("ctr-data");
  if (ctr) {
    bar(document.getElementById("ctr-chart"), ctr.map((row) => row.label), ctr.map((row) => row.ctr),
        { percent: true, horizontal: true });
  }

}

document.addEventListener("DOMContentLoaded", () => {
  drawInsightCharts();
  window.addEventListener("rm:themechange", drawInsightCharts);

  // ---- Retrain: POST, show a spinner, then reload to show the new model's charts ----
  const retrain = document.querySelector("[data-retrain]");
  if (retrain) {
    retrain.addEventListener("click", async () => {
      retrain.disabled = true;
      const original = retrain.innerHTML;
      retrain.innerHTML = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Training…';
      try {
        await fetchJSON(retrain.dataset.retrain, { method: "POST" });
        window.location.reload(); // the success message is shown as a toast after reload
      } catch (error) {
        showToast(error.message || "Training failed.", "exclamation-circle");
        retrain.disabled = false;
        retrain.innerHTML = original;
      }
    });
  }

  // ---- A/B switch saves as soon as it's flipped ----
  const abSwitch = document.querySelector("[data-autosubmit-switch]");
  if (abSwitch) abSwitch.addEventListener("change", () => abSwitch.form.requestSubmit());
});
