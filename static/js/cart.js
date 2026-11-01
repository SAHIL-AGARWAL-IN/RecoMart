/* Cart page: change quantities and remove items without reloading the page.
   Uses fetchJSON / showToast / setBadge from main.js. */
(() => {
  const page = document.querySelector("[data-cart-page]");
  if (!page) return;

  const timers = new Map(); // one pending update per product (debounce)

  function renderSummary(cart) {
    setBadge("[data-cart-count]", cart.count);
    page.querySelectorAll("[data-summary]").forEach((el) => {
      el.textContent = cart[el.dataset.summary];
    });
    const fill = page.querySelector(".free-ship__fill");
    const track = page.querySelector(".free-ship__track");
    const text = page.querySelector("[data-free-ship-text]");
    fill.style.width = `${cart.free_shipping_progress}%`;
    track.setAttribute("aria-valuenow", cart.free_shipping_progress);
    if (cart.free_shipping_progress >= 100) {
      text.textContent = "You've unlocked free delivery.";
    } else {
      text.textContent = "";
      const strong = document.createElement("strong");
      strong.textContent = cart.free_shipping_remaining;
      text.append("Add ", strong, " more for free delivery.");
    }
  }

  function removeLine(line) {
    line.classList.add("is-removing");
    line.addEventListener("transitionend", () => {
      line.remove();
      if (!page.querySelector("[data-cart-line]")) window.location.reload(); // show the empty state
    }, { once: true });
  }

  async function send(url, line, body) {
    line.classList.add("is-busy");
    try {
      const data = await fetchJSON(url, { method: "POST", body });
      if (data.item) {
        line.querySelector("[data-qty-input]").value = data.item.quantity;
        line.querySelector("[data-line-total]").textContent = data.item.line_total;
      } else {
        removeLine(line);
      }
      renderSummary(data.cart);
      if (data.message) showToast(data.message, data.item ? "info-circle" : "trash3");
    } catch (error) {
      showToast(error.message, "exclamation-circle");
    } finally {
      line.classList.remove("is-busy");
    }
  }

  // Quantity typed or changed with +/- (main.js fires "change" for the stepper buttons)
  page.addEventListener("change", (event) => {
    const input = event.target.closest("[data-qty-input]");
    if (!input) return;
    const line = input.closest("[data-cart-line]");
    const productId = line.dataset.cartLine;
    clearTimeout(timers.get(productId));
    timers.set(productId, setTimeout(() => {
      send(page.dataset.updateUrl, line, { product_id: productId, quantity: input.value });
    }, 400));
  });

  page.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove]");
    if (!removeButton) return;
    const line = removeButton.closest("[data-cart-line]");
    send(page.dataset.removeUrl, line, { product_id: line.dataset.cartLine });
  });
})();
