/* Live search: results appear under the search box as you type.
   - waits 300 ms after the last key press (debounce) so we don't call the server on every letter
   - cancels the previous request with AbortController, so a slow old response never overwrites a newer one
   - arrow keys move through results, Enter opens one, Escape closes the list */
(() => {
  const DEBOUNCE_MS = 300;
  const searchUrl = document.body.dataset.searchUrl;

  function highlight(text, query) {
    // Build the name with the matching part in <mark>, using text nodes only (no HTML injection).
    const fragment = document.createDocumentFragment();
    const index = text.toLowerCase().indexOf(query.toLowerCase());
    if (index === -1) {
      fragment.append(text);
    } else {
      const mark = document.createElement("mark");
      mark.textContent = text.slice(index, index + query.length);
      fragment.append(text.slice(0, index), mark, text.slice(index + query.length));
    }
    return fragment;
  }

  function resultRow(item, query, id) {
    const link = document.createElement("a");
    link.className = "search-result";
    link.href = item.url;
    link.id = id;
    link.setAttribute("role", "option");
    link.setAttribute("aria-selected", "false");
    const img = document.createElement("img");
    img.src = item.image;
    img.alt = "";
    img.width = 44;
    img.height = 44;
    const text = document.createElement("span");
    text.className = "search-result__text";
    const name = document.createElement("span");
    name.className = "search-result__name";
    name.append(highlight(item.name, query));
    const meta = document.createElement("span");
    meta.className = "search-result__meta";
    meta.textContent = `${item.brand} in ${item.category}`;
    text.append(name, meta);
    const price = document.createElement("span");
    price.className = "search-result__price";
    price.textContent = item.price;
    link.append(img, text, price);
    return link;
  }

  function attach(input) {
    const box = input.closest("form");
    const list = document.createElement("div");
    list.className = "search-results";
    list.id = `${input.id}-results`;
    list.setAttribute("role", "listbox");
    list.hidden = true;
    box.appendChild(list);

    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", list.id);
    input.setAttribute("aria-expanded", "false");

    let timer = null;
    let controller = null;
    let active = -1;

    const options = () => [...list.querySelectorAll('[role="option"]')];

    function close() {
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }

    function setActive(index) {
      const items = options();
      items.forEach((el, i) => el.setAttribute("aria-selected", i === index ? "true" : "false"));
      active = index;
      if (items[index]) {
        input.setAttribute("aria-activedescendant", items[index].id);
        items[index].scrollIntoView({ block: "nearest" });
      }
    }

    async function search(query) {
      if (controller) controller.abort();
      controller = new AbortController();
      try {
        const data = await fetchJSON(`${searchUrl}?q=${encodeURIComponent(query)}`, { signal: controller.signal });
        list.replaceChildren();
        if (!data.results.length) {
          const empty = document.createElement("p");
          empty.className = "search-results__empty";
          empty.textContent = `No products match “${query}”. Try a shorter word.`;
          list.append(empty);
        } else {
          data.results.forEach((item, i) => list.append(resultRow(item, query, `${list.id}-${i}`)));
          const all = document.createElement("a");
          all.className = "search-results__all";
          all.href = data.see_all_url;
          all.id = `${list.id}-all`;
          all.setAttribute("role", "option");
          all.textContent = `See all ${data.total} results`;
          list.append(all);
        }
        list.hidden = false;
        input.setAttribute("aria-expanded", "true");
        active = -1;
      } catch (error) {
        if (error.name !== "AbortError") close();
      }
    }

    input.addEventListener("input", () => {
      clearTimeout(timer);
      const query = input.value.trim();
      if (query.length < 2) {
        if (controller) controller.abort();
        close();
        return;
      }
      timer = setTimeout(() => search(query), DEBOUNCE_MS);
    });

    input.addEventListener("keydown", (event) => {
      const items = options();
      if (list.hidden || !items.length) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActive((active + 1) % items.length);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setActive((active - 1 + items.length) % items.length);
      } else if (event.key === "Enter" && active >= 0) {
        event.preventDefault();
        window.location.href = items[active].href;
      } else if (event.key === "Escape") {
        close();
      }
    });

    // Close when focus or a click leaves the search box
    document.addEventListener("click", (event) => {
      if (!box.contains(event.target)) close();
    });
    input.addEventListener("focus", () => {
      if (list.childElementCount && input.value.trim().length >= 2) {
        list.hidden = false;
        input.setAttribute("aria-expanded", "true");
      }
    });
  }

  document.querySelectorAll("input[data-live-search]").forEach(attach);
})();
