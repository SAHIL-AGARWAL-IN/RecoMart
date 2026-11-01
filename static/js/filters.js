/* Product list: filters, sort and pagination without reloading the page.
   Without JavaScript the filter form still works as a normal GET form; this file upgrades it.
   The browser URL is kept in sync (history.pushState), so filtered pages can be shared and bookmarked. */
(() => {
  const form = document.querySelector("form[data-ajax-filters]");
  const results = document.getElementById("product-results");
  if (!form || !results) return;

  let controller = null;

  function skeletons(count = 8) {
    const card = `
      <div class="col"><div class="skeleton-card" aria-hidden="true">
        <div class="skeleton skeleton-card__media"></div>
        <div class="skeleton skeleton-card__line"></div>
        <div class="skeleton skeleton-card__line skeleton-card__line--short"></div>
      </div></div>`;
    return `<p class="visually-hidden" role="status">Loading products…</p>
      <div class="row row-cols-2 row-cols-md-3 row-cols-xl-4 row-cols-xxl-5 g-3">${card.repeat(count)}</div>`;
  }

  function currentParams(page) {
    // FormData includes the sort box too, because it has form="filter-form"
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(form)) {
      if (value !== "") params.set(key, value);
    }
    if (page && page !== "1") params.set("page", page);
    return params;
  }

  async function load(params, { push = true, scroll = false } = {}) {
    if (controller) controller.abort();
    controller = new AbortController();

    const apiParams = new URLSearchParams(params);
    if (results.dataset.category) apiParams.set("category", results.dataset.category);

    results.setAttribute("aria-busy", "true");
    results.innerHTML = skeletons();
    if (scroll) results.scrollIntoView({ behavior: "smooth", block: "start" });

    try {
      const data = await fetchJSON(`${results.dataset.resultsUrl}?${apiParams}`, { signal: controller.signal });
      results.innerHTML = data.html; // HTML rendered by our own Django template (auto-escaped)
      if (push) {
        const query = params.toString();
        history.pushState(null, "", query ? `${form.action}?${query}` : form.action);
      }
    } catch (error) {
      if (error.name === "AbortError") return;
      showToast("Couldn't load products. Showing the full page instead.", "exclamation-circle");
      window.location.href = `${form.action}?${params}`;
    } finally {
      results.removeAttribute("aria-busy");
    }
  }

  // Apply filters (button, Enter in a price box, or the sort box via main.js's autosubmit)
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    load(currentParams());
    const offcanvas = bootstrap.Offcanvas.getInstance(document.getElementById("filters"));
    if (offcanvas) offcanvas.hide(); // close the drawer on phones
  });

  // Rating radios apply immediately
  form.addEventListener("change", (event) => {
    if (event.target.name === "rating") form.requestSubmit();
  });

  // Pagination links inside the results
  results.addEventListener("click", (event) => {
    const link = event.target.closest(".page-link[href]");
    if (!link) return;
    event.preventDefault();
    const page = new URL(link.href, window.location.href).searchParams.get("page");
    load(currentParams(page), { scroll: true });
  });

  // Back/forward buttons: reload so the form and grid match the URL again
  window.addEventListener("popstate", () => window.location.reload());
})();
