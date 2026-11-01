/* Checkout: show only the fields for the chosen payment method, and a "processing" state on submit. */
(() => {
  const form = document.querySelector("[data-checkout-form]");
  if (!form) return;

  function showPanel() {
    const chosen = form.querySelector('input[name="payment_method"]:checked');
    form.querySelectorAll("[data-payment-panel]").forEach((panel) => {
      panel.hidden = !chosen || panel.dataset.paymentPanel !== chosen.value;
    });
  }

  form.addEventListener("change", (event) => {
    if (event.target.name === "payment_method") showPanel();
  });
  showPanel();

  // Simulated payment: disable the button and show a spinner so it can't be clicked twice.
  form.addEventListener("submit", () => {
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Processing payment…';
  });
})();
