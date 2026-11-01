/* RecoMart site-wide JavaScript (vanilla, no frameworks).
   Behaviours are attached through data-* attributes so templates stay readable. */

// ---------- CSRF-aware fetch helper (used by AJAX features) ----------
function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[2]) : null;
}

/** POST/GET JSON with Django's CSRF token. Returns the parsed JSON body. */
async function fetchJSON(url, { method = "GET", body = null, signal } = {}) {
  const options = { method, signal, headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" } };
  if (method !== "GET") {
    options.headers["X-CSRFToken"] = getCookie("csrftoken");
    if (body !== null) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
  }
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(data.error || response.statusText), { status: response.status, data });
  return data;
}

// ---------- Toasts ----------
function showToast(message, icon = "check-circle") {
  const stack = document.getElementById("toast-stack");
  if (!stack) return;
  const toast = document.createElement("div");
  toast.className = "toast align-items-center";
  toast.setAttribute("role", "status");
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body d-flex align-items-center gap-2"><i class="bi bi-${icon}" aria-hidden="true"></i><span></span></div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
    </div>`;
  toast.querySelector(".toast-body span").textContent = message; // textContent: never inject HTML
  stack.appendChild(toast);
  toast.addEventListener("hidden.bs.toast", () => toast.remove());
  bootstrap.Toast.getOrCreateInstance(toast, { delay: 3500 }).show();
}

// ---------- Navbar badges ----------
function setBadge(selector, count) {
  document.querySelectorAll(selector).forEach((badge) => {
    badge.textContent = count;
    badge.hidden = !count;
  });
}

// ---------- Add to cart and wishlist hearts (event delegation: works for AJAX-loaded cards too) ----------
document.addEventListener("click", async (event) => {
  const addButton = event.target.closest("[data-add-to-cart]");
  if (addButton) {
    const qtyInput = addButton.dataset.quantityInput && document.querySelector(addButton.dataset.quantityInput);
    addButton.classList.add("is-busy");
    try {
      const data = await fetchJSON(document.body.dataset.cartAddUrl, {
        method: "POST",
        body: { product_id: addButton.dataset.addToCart, quantity: qtyInput ? qtyInput.value : 1 },
      });
      setBadge("[data-cart-count]", data.cart.count);
      addButton.classList.add("is-added");
      showToast(data.message, "bag-check");
    } catch (error) {
      showToast(error.message, "exclamation-circle");
    } finally {
      addButton.classList.remove("is-busy");
    }
    return;
  }

  const heart = event.target.closest("[data-wishlist-toggle]");
  if (heart) {
    const url = document.body.dataset.wishlistUrl.replace("/0/", `/${heart.dataset.wishlistToggle}/`);
    try {
      const data = await fetchJSON(url, { method: "POST" });
      // Update every heart for this product on the page (card and buy box)
      document.querySelectorAll(`[data-wishlist-toggle="${heart.dataset.wishlistToggle}"]`).forEach((h) => {
        h.setAttribute("aria-pressed", data.wishlisted ? "true" : "false");
        h.classList.toggle("is-pulsing", data.wishlisted);
      });
      setBadge("[data-wishlist-count]", data.count);
      showToast(data.message, data.wishlisted ? "heart-fill" : "heart");
    } catch (error) {
      if (error.status === 401 && error.data.login_url) window.location.href = error.data.login_url;
      else showToast(error.message, "exclamation-circle");
    }
    return;
  }

  // Quantity steppers: +/- buttons change the number box next to them, within its min and max
  const step = event.target.closest(".stepper [data-step]");
  if (step) {
    const input = step.closest(".stepper").querySelector("input");
    const next = Number(input.value || 1) + Number(step.dataset.step);
    const max = Number(input.max || Infinity);
    input.value = Math.min(Math.max(next, Number(input.min || 1)), max);
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }
});

document.addEventListener("DOMContentLoaded", () => {
  // Django messages rendered by the server
  document.querySelectorAll(".toast[data-autoshow]").forEach((el) => {
    bootstrap.Toast.getOrCreateInstance(el, { delay: 4000 }).show();
  });

  // Product gallery: clicking a thumbnail swaps the main image
  document.querySelectorAll("[data-gallery]").forEach((gallery) => {
    const main = gallery.querySelector("[data-gallery-main]");
    gallery.querySelectorAll("[data-gallery-thumb]").forEach((thumb) => {
      thumb.addEventListener("click", () => {
        main.src = thumb.dataset.galleryThumb;
        gallery.querySelectorAll("[data-gallery-thumb]").forEach((t) => t.removeAttribute("aria-current"));
        thumb.setAttribute("aria-current", "true");
      });
    });
  });

  // <select data-autosubmit>: submit its form as soon as the value changes (e.g. sort order)
  document.querySelectorAll("select[data-autosubmit]").forEach((select) => {
    select.addEventListener("change", () => select.form.requestSubmit());
  });

  // After a form fails validation on the server, put the cursor in the first invalid field
  const firstInvalid = document.querySelector("form .is-invalid");
  if (firstInvalid) firstInvalid.focus();

  // Deep link to a tab: /product/x/#reviews opens the Reviews tab, and switching tabs updates the URL
  document.querySelectorAll('[data-bs-toggle="tab"]').forEach((tab) => {
    const name = tab.id.replace(/-tab$/, "");
    if (location.hash === `#${name}`) {
      bootstrap.Tab.getOrCreateInstance(tab).show();
      tab.scrollIntoView({ block: "start" });
    }
    tab.addEventListener("shown.bs.tab", () => history.replaceState(null, "", `#${name}`));
  });

  // Links that open a Bootstrap tab, e.g. the star rating jumps to the Reviews tab
  document.querySelectorAll("[data-open-tab]").forEach((link) => {
    link.addEventListener("click", (event) => {
      const tabButton = document.querySelector(link.dataset.openTab);
      if (!tabButton) return;
      event.preventDefault();
      bootstrap.Tab.getOrCreateInstance(tabButton).show();
      tabButton.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });
});
