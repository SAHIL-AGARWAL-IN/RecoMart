/* Recommendation strips ("You may also like"): fetch JSON from the recommendation API and draw cards.
   Cards are built with DOM methods (textContent), never by pasting server text as HTML.
   The heart and quick-add buttons reuse main.js's delegated click handlers. */
(() => {
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function icon(name) {
    const i = el("i", `bi bi-${name}`);
    i.setAttribute("aria-hidden", "true");
    return i;
  }

  function stars(rating, count) {
    const wrap = el("span", "stars");
    const icons = el("span", "stars__icons");
    icons.setAttribute("role", "img");
    icons.setAttribute("aria-label", `Rated ${rating.toFixed(1)} out of 5`);
    for (let position = 1; position <= 5; position++) {
      const name = rating >= position - 0.25 ? "star-fill" : rating >= position - 0.75 ? "star-half" : "star";
      icons.append(icon(name));
    }
    const label = el("span");
    label.append(el("span", "stars__value", `${rating.toFixed(1)} `), `(${count})`);
    wrap.append(icons, label);
    return wrap;
  }

  function card(item) {
    const article = el("article", "product-card");

    const media = el("a", "product-card__media");
    media.href = item.url;
    media.tabIndex = -1;
    media.setAttribute("aria-hidden", "true");
    if (item.image) {
      const img = el("img");
      Object.assign(img, { src: item.image, alt: "", loading: "lazy", width: 400, height: 320 });
      media.append(img);
    }
    if (item.discount_percent) media.append(el("span", "badge-deal", `${item.discount_percent}% off`));
    if (!item.in_stock) media.append(el("span", "badge-stock", "Out of stock"));

    const heart = el("button", "heart-btn heart-btn--card");
    heart.type = "button";
    heart.dataset.wishlistToggle = item.id;
    heart.setAttribute("aria-pressed", item.wishlisted ? "true" : "false");
    heart.setAttribute("aria-label", `Save ${item.name} to wishlist`);
    heart.append(Object.assign(icon("heart"), { className: "bi bi-heart heart-btn__off" }),
                 Object.assign(icon("heart-fill"), { className: "bi bi-heart-fill heart-btn__on" }));

    const body = el("div", "product-card__body");
    const title = el("h3", "product-card__title");
    const link = el("a", "stretched-link", item.name);
    link.href = item.url;
    title.append(link);

    const foot = el("div", "product-card__foot");
    const price = el("div", "price");
    price.append(el("span", "price__now", item.price));
    if (item.mrp) price.append(el("s", "price__was", item.mrp));
    foot.append(price);
    if (item.in_stock) {
      const add = el("button", "quick-add");
      add.type = "button";
      add.dataset.addToCart = item.id;
      add.setAttribute("aria-label", `Add ${item.name} to cart`);
      add.append(icon("bag-plus"));
      foot.append(add);
    }

    body.append(el("p", "product-card__brand", item.brand), title, stars(item.rating, item.rating_count), foot);
    article.append(media, heart, body);

    const slot = el("div", "rec-track__item");
    slot.append(article);
    return slot;
  }

  async function load(section) {
    const track = section.querySelector("[data-rec-track]");
    try {
      const data = await fetchJSON(section.dataset.recommendations);
      if (!data.results.length) {
        section.hidden = true;
        return;
      }
      track.replaceChildren(...data.results.map(card));
      track.removeAttribute("aria-busy");
    } catch (error) {
      section.hidden = true; // recommendations are a bonus: never break the page if they fail
    }
  }

  document.querySelectorAll("[data-recommendations]").forEach((section) => {
    load(section);
    // Desktop arrow buttons scroll the strip by most of its width
    section.querySelectorAll("[data-scroll]").forEach((button) => {
      button.addEventListener("click", () => {
        const track = section.querySelector("[data-rec-track]");
        track.scrollBy({ left: Number(button.dataset.scroll) * track.clientWidth * 0.8, behavior: "smooth" });
      });
    });
  });
})();
