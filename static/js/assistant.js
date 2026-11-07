/* Shopping assistant chat panel.
   Messages are sent to /api/assistant/ with fetchJSON (main.js) and answers are drawn with DOM
   methods (textContent), never by pasting text as HTML. The conversation is kept in
   sessionStorage, so it survives moving between pages in the same tab. */
(() => {
  const root = document.querySelector("[data-assistant]");
  if (!root) return;

  const panel = root.querySelector("#assistant-panel");
  const launcher = root.querySelector("[data-assistant-open]");
  const log = root.querySelector("[data-assistant-log]");
  const form = root.querySelector("[data-assistant-form]");
  const input = form.querySelector("input");
  const sendButton = form.querySelector("button");
  const STORAGE_KEY = "recomart-assistant";
  const START_CHIPS = ["Phones under ₹20,000", "Something like Atomic Habits", "Recommend something for me",
                       "Where is my order?", "What's in my cart?", "Delivery charges"];
  let history = load();

  // ---------- storage (optional: the chat still works if the browser blocks it) ----------
  function load() {
    try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || []; } catch { return []; }
  }
  function save() {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(-30))); } catch { /* ignore */ }
  }

  // ---------- drawing messages ----------
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function miniProduct(item) {
    const link = el("a", "mini-product");
    link.href = item.url;
    const img = el("img");
    Object.assign(img, { src: item.image, alt: "", width: 48, height: 48, loading: "lazy" });
    const info = el("span");
    const meta = el("span", "mini-product__meta");
    const star = el("i", "bi bi-star-fill");
    star.setAttribute("aria-hidden", "true");
    meta.append(`${item.brand}, `, star, ` ${item.rating.toFixed(1)}${item.in_stock ? "" : ", out of stock"}`);
    info.append(el("span", "mini-product__name", item.name), meta);
    link.append(img, info, el("span", "mini-product__price", item.price));
    const li = el("li");
    li.append(link);
    return li;
  }

  function render(message) {
    const wrap = el("div", `msg msg--${message.from}`);
    wrap.append(el("p", "msg__bubble", message.text));
    if (message.products && message.products.length) {
      const list = el("ul", "msg__products");
      message.products.forEach((item) => list.append(miniProduct(item)));
      wrap.append(list);
    }
    if (message.link) {
      const link = el("a", "msg__link", message.link.label);
      link.href = message.link.url;
      wrap.append(link);
    }
    if (message.chips && message.chips.length) {
      const chips = el("div", "msg__chips");
      // A chip is either plain text, or {label, message} when the button says less than it sends
      message.chips.forEach((chipData) => {
        const label = typeof chipData === "string" ? chipData : chipData.label;
        const text = typeof chipData === "string" ? chipData : chipData.message;
        const chip = el("button", "msg__chip", label);
        chip.type = "button";
        chip.addEventListener("click", () => send(text));
        chips.append(chip);
      });
      wrap.append(chips);
    }
    log.append(wrap);
    log.scrollTop = log.scrollHeight;
  }

  function add(message) {
    history.push(message);
    save();
    render(message);
  }

  function welcome() {
    add({ from: "bot", text: root.dataset.greeting, chips: START_CHIPS });
  }

  // ---------- sending ----------
  async function send(text) {
    text = text.trim();
    if (!text) return;
    add({ from: "user", text });
    input.value = "";
    sendButton.disabled = true;
    const typing = el("div", "msg msg--bot");
    const dots = el("div", "msg__bubble msg__typing");
    dots.setAttribute("aria-label", "The assistant is typing");
    dots.append(el("span"), el("span"), el("span"));
    typing.append(dots);
    log.append(typing);
    log.scrollTop = log.scrollHeight;

    try {
      const data = await fetchJSON(root.dataset.url, {
        method: "POST",
        body: { message: text, product_id: document.body.dataset.currentProduct || null },
      });
      add({ from: "bot", text: data.text, products: data.products, chips: data.chips, link: data.link });
    } catch (error) {
      add({ from: "bot", text: error.message || "Something went wrong. Please try again." });
    } finally {
      typing.remove();
      sendButton.disabled = false;
      input.focus();
    }
  }

  // ---------- opening and closing ----------
  function open() {
    panel.hidden = false;
    root.classList.add("is-open");
    launcher.setAttribute("aria-expanded", "true");
    if (!log.childElementCount) {
      if (history.length) history.forEach(render); else welcome();
    }
    log.scrollTop = log.scrollHeight;
    input.focus();
  }

  function close() {
    panel.hidden = true;
    root.classList.remove("is-open");
    launcher.setAttribute("aria-expanded", "false");
    launcher.focus();
  }

  launcher.addEventListener("click", () => (panel.hidden ? open() : close()));
  root.querySelector("[data-assistant-close]").addEventListener("click", close);
  root.querySelector("[data-assistant-clear]").addEventListener("click", () => {
    history = [];
    save();
    log.replaceChildren();
    welcome();
    input.focus();
  });
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    send(input.value);
  });
})();
