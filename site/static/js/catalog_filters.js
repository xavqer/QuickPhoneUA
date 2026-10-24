(() => {
  const root = document.querySelector("[data-catalog-root]");
  if (!root) {
    return;
  }

  const panel = document.querySelector("[data-filter-panel]");
  const backdrop = document.querySelector("[data-filter-backdrop]");
  const openBtn = document.querySelector("[data-filter-open]");
  const closeBtn = document.querySelector("[data-filter-close]");
  const resetBtn = document.querySelector("[data-soft-reset]");
  const form = document.getElementById("catalog-filter-form");
  const headerSearchInput = document.querySelector("[data-catalog-header-search]");
  const headerSearchForm = document.querySelector("[data-header-search-form]");

  if (!form) {
    return;
  }

  const searchField = form.querySelector("[data-search-field]");
  const getSortSelect = () => document.querySelector("[data-sort-select]");

  const syncSortControl = () => {
    const sortSelect = getSortSelect();
    if (!(sortSelect instanceof HTMLSelectElement) || sortSelect.options.length === 0) {
      return;
    }
    const defaultValue = sortSelect.options[0].value;
    if (sortSelect.value === defaultValue) {
      sortSelect.removeAttribute("name");
      return;
    }
    sortSelect.setAttribute("name", "sort");
  };

  const submitForm = () => {
    syncSortControl();
    if (window.htmx) {
      window.htmx.trigger(form, "submit");
      return;
    }
    form.submit();
  };

  document.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof Element) || !target.matches("[data-sort-select]")) {
      return;
    }
    submitForm();
  });

  const setPanelOpen = (isOpen) => {
    if (!panel || !backdrop) {
      return;
    }
    panel.classList.toggle("is-open", isOpen);
    backdrop.hidden = !isOpen;
    backdrop.style.display = isOpen ? "block" : "none";
    if (openBtn) {
      openBtn.setAttribute("aria-expanded", String(isOpen));
    }
  };

  const closePanel = () => setPanelOpen(false);

  if (openBtn) {
    openBtn.setAttribute("aria-expanded", "false");
    openBtn.addEventListener("click", () => setPanelOpen(true));
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", closePanel);
  }
  if (backdrop) {
    backdrop.addEventListener("click", closePanel);
  }

  form.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (!target.getAttribute("name")) {
      return;
    }
    if (target.matches("[data-price-min-range], [data-price-max-range]")) {
      return;
    }
    submitForm();
  });

  const categoryGroup = form.querySelector('[data-single-group="category"]');
  const categoryInput = form.querySelector('[data-single-value="category"]');
  if (categoryGroup && categoryInput) {
    categoryGroup.addEventListener("click", (event) => {
      const clickTarget = event.target;
      if (!(clickTarget instanceof Element)) {
        return;
      }
      const button = clickTarget.closest("[data-single-option]");
      if (!button) {
        return;
      }

      const nextValue = button.dataset.value || "";
      if (categoryInput.value === nextValue && button.classList.contains("is-active")) {
        return;
      }

      categoryInput.value = nextValue;
      categoryGroup.querySelectorAll("[data-single-option]").forEach((item) => {
        item.classList.toggle("is-active", item === button);
      });
      submitForm();
    });
  }

  const brandGroup = form.querySelector('[data-multi-group="brand"]');
  const brandInputsHost = form.querySelector('[data-multi-inputs="brand"]');
  if (brandGroup && brandInputsHost) {
    const syncBrandInputs = () => {
      brandInputsHost.innerHTML = "";
      brandGroup.querySelectorAll("[data-multi-option].is-active").forEach((button) => {
        const value = button.dataset.value;
        if (!value) {
          return;
        }
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "brand";
        input.value = value;
        brandInputsHost.appendChild(input);
      });
    };

    brandGroup.addEventListener("click", (event) => {
      const clickTarget = event.target;
      if (!(clickTarget instanceof Element)) {
        return;
      }
      const button = clickTarget.closest("[data-multi-option]");
      if (!button) {
        return;
      }
      const isActive = button.classList.toggle("is-active");
      button.setAttribute("aria-pressed", String(isActive));
      syncBrandInputs();
      submitForm();
    });
  }

  const minRange = form.querySelector("[data-price-min-range]");
  const maxRange = form.querySelector("[data-price-max-range]");
  const rangeStack = form.querySelector(".stitch-range-stack");
  const minLabel = form.querySelector("[data-price-min-label]");
  const maxLabel = form.querySelector("[data-price-max-label]");
  const minInput = form.querySelector("[data-price-min-input]");
  const maxInput = form.querySelector("[data-price-max-input]");
  const priceFloor = Number.parseInt(form.dataset.priceFloor || "0", 10);
  const priceCeiling = Number.parseInt(form.dataset.priceCeiling || "0", 10);

  const updatePriceState = (source) => {
    if (!minRange || !maxRange || !minInput || !maxInput || !minLabel || !maxLabel) {
      return;
    }

    let minValue = Number.parseInt(minRange.value, 10);
    let maxValue = Number.parseInt(maxRange.value, 10);

    if (minValue > maxValue) {
      if (source === "min") {
        maxValue = minValue;
        maxRange.value = String(maxValue);
      } else {
        minValue = maxValue;
        minRange.value = String(minValue);
      }
    }

    minLabel.textContent = `${minValue} грн`;
    maxLabel.textContent = `${maxValue} грн`;
    minInput.value = minValue > priceFloor ? String(minValue) : "";
    maxInput.value = maxValue < priceCeiling ? String(maxValue) : "";

    if (rangeStack && priceCeiling > priceFloor) {
      const minPercent = ((minValue - priceFloor) / (priceCeiling - priceFloor)) * 100;
      const maxPercent = ((maxValue - priceFloor) / (priceCeiling - priceFloor)) * 100;
      rangeStack.style.setProperty("--range-start", `${minPercent}%`);
      rangeStack.style.setProperty("--range-end", `${maxPercent}%`);
    }

    minRange.style.zIndex = minValue >= maxValue ? "5" : "3";
    maxRange.style.zIndex = "4";
  };

  if (minRange && maxRange) {
    updatePriceState();
    minRange.addEventListener("input", () => updatePriceState("min"));
    maxRange.addEventListener("input", () => updatePriceState("max"));
    minRange.addEventListener("change", () => {
      updatePriceState("min");
      submitForm();
    });
    maxRange.addEventListener("change", () => {
      updatePriceState("max");
      submitForm();
    });
  }

  syncSortControl();

  if (headerSearchInput && searchField) {
    const searchFieldWrap = headerSearchInput.closest(".stitch-header-search__field");
    let pendingSearchRequests = 0;
    let markNextRequestAsSearch = false;

    const setSearchingState = (isSearching) => {
      if (!searchFieldWrap) {
        return;
      }
      searchFieldWrap.classList.toggle("is-searching", isSearching);
    };

    searchField.value = headerSearchInput.value.trim();
    let searchDebounceId = 0;

    headerSearchInput.addEventListener("input", () => {
      searchField.value = headerSearchInput.value.trim();
      window.clearTimeout(searchDebounceId);
      searchDebounceId = window.setTimeout(() => {
        markNextRequestAsSearch = true;
        submitForm();
      }, 280);
    });

    if (headerSearchForm) {
      headerSearchForm.addEventListener("submit", (event) => {
        event.preventDefault();
        searchField.value = headerSearchInput.value.trim();
        markNextRequestAsSearch = true;
        submitForm();
      });
    }

    document.body.addEventListener("htmx:beforeRequest", (event) => {
      const requestElement = event.detail && event.detail.elt;
      if (requestElement !== form || !markNextRequestAsSearch) {
        return;
      }
      markNextRequestAsSearch = false;
      pendingSearchRequests += 1;
      setSearchingState(true);
    });

    document.body.addEventListener("htmx:afterRequest", (event) => {
      const requestElement = event.detail && event.detail.elt;
      if (requestElement !== form || pendingSearchRequests === 0) {
        return;
      }
      pendingSearchRequests -= 1;
      if (pendingSearchRequests === 0) {
        setSearchingState(false);
      }
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      if (searchField) {
        searchField.value = "";
      }
      if (headerSearchInput) {
        headerSearchInput.value = "";
      }

      if (categoryInput) {
        categoryInput.value = "";
      }
      if (categoryGroup) {
        categoryGroup.querySelectorAll("[data-single-option]").forEach((item) => {
          const isAllOption = (item.dataset.value || "") === "";
          item.classList.toggle("is-active", isAllOption);
        });
      }

      if (brandGroup && brandInputsHost) {
        brandGroup.querySelectorAll("[data-multi-option]").forEach((button) => {
          button.classList.remove("is-active");
          button.setAttribute("aria-pressed", "false");
        });
        brandInputsHost.innerHTML = "";
      }

      if (minRange && maxRange) {
        minRange.value = String(priceFloor);
        maxRange.value = String(priceCeiling);
        updatePriceState();
      }

      const conditionField = form.querySelector('[name="condition"]');
      if (conditionField) {
        conditionField.value = "";
      }

      const sortSelect = getSortSelect();
      if (sortSelect instanceof HTMLSelectElement && sortSelect.options.length > 0) {
        sortSelect.value = sortSelect.options[0].value;
        syncSortControl();
      }

      submitForm();
    });
  }

  document.body.addEventListener("htmx:afterSwap", closePanel);
})();

