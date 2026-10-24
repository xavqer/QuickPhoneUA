(() => {
  const DELIVERY_METHOD_NOVA_POSHTA = "nova_poshta";
  const DELIVERY_METHOD_PICKUP = "pickup";

  const setStepBadgeState = (stepKey) => {
    document.querySelectorAll("[data-checkout-step]").forEach((section) => {
      const badge = section.querySelector("[data-checkout-step-badge]");
      if (!badge) {
        return;
      }
      const isActive = section.dataset.checkoutStep === stepKey;
      badge.classList.toggle("bg-zinc-900", isActive);
      badge.classList.toggle("text-white", isActive);
      badge.classList.toggle("bg-white", !isActive);
      badge.classList.toggle("text-zinc-900", !isActive);
    });
  };

  const stepHasValue = (section) => {
    if (!section) {
      return false;
    }
    const fields = section.querySelectorAll("input, select, textarea");
    return Array.from(fields).some((field) => {
      if (field.type === "hidden") {
        return false;
      }
      return (field.value || "").trim() !== "";
    });
  };

  const syncStepBadgeState = () => {
    const focusedStep = document.activeElement?.closest?.("[data-checkout-step]")?.dataset?.checkoutStep;
    if (focusedStep) {
      setStepBadgeState(focusedStep);
      return;
    }
    const deliverySection = document.querySelector('[data-checkout-step="delivery"]');
    if (stepHasValue(deliverySection)) {
      setStepBadgeState("delivery");
      return;
    }
    setStepBadgeState("contact");
  };

  const handleStepInteraction = (event) => {
    const step = event.target?.closest?.("[data-checkout-step]")?.dataset?.checkoutStep;
    if (!step) {
      return;
    }
    setStepBadgeState(step);
  };

  const bindStepEvents = () => {
    if (document.body.dataset.checkoutStepEventsBound === "true") {
      return;
    }
    document.body.dataset.checkoutStepEventsBound = "true";
    document.addEventListener("focusin", handleStepInteraction);
    document.addEventListener("input", handleStepInteraction);
    document.addEventListener("change", handleStepInteraction);
  };

  const getSelectedDeliveryMethod = () => {
    const checked = document.querySelector('input[name="delivery_method"]:checked');
    return checked?.value || DELIVERY_METHOD_NOVA_POSHTA;
  };

  const clearEstimateHiddenInputs = () => {
    const estimateContainer = document.getElementById("np-estimate-hidden");
    if (!estimateContainer) {
      return;
    }
    estimateContainer.innerHTML = `
      <input type="hidden" name="np_estimate_min" value="">
      <input type="hidden" name="np_estimate_max" value="">
    `;
  };

  const resetDeliveryEstimate = (textKey = "baseText") => {
    ["delivery", "commission", "total"].forEach((name) => {
      const value = document.getElementById(`checkout-${name}-value`);
      if (value?.dataset?.[textKey]) {
        value.textContent = value.dataset[textKey];
      }
    });
    clearEstimateHiddenInputs();
  };

  const syncDeliveryMethodUI = (refreshEstimateForNp = false) => {
    const npFieldsContainer = document.getElementById("np-delivery-fields");
    const isPickup = getSelectedDeliveryMethod() === DELIVERY_METHOD_PICKUP;

    if (npFieldsContainer) {
      npFieldsContainer.classList.toggle("hidden", isPickup);
      npFieldsContainer.querySelectorAll("input, select, textarea, button").forEach((field) => {
        field.disabled = isPickup;
      });
    }

    if (isPickup) {
      const cityRef = document.getElementById("id_np_city_ref");
      const warehouseRef = document.getElementById("id_np_warehouse_ref");
      if (cityRef) {
        cityRef.value = "";
      }
      if (warehouseRef) {
        warehouseRef.value = "";
      }
      resetDeliveryEstimate("pickupText");
      syncStepBadgeState();
      return;
    }

    if (refreshEstimateForNp) {
      resetDeliveryEstimate();
    }
    if (!refreshEstimateForNp || !window.htmx) {
      syncStepBadgeState();
      return;
    }

    const cityRef = document.getElementById("id_np_city_ref");
    const warehouseRef = document.getElementById("id_np_warehouse_ref");
    if (cityRef?.value && warehouseRef?.value) {
      const url = `/orders/np/estimate/?city_ref=${encodeURIComponent(cityRef.value)}&warehouse_ref=${encodeURIComponent(warehouseRef.value)}`;
      window.htmx.ajax("GET", url, { target: "#np-estimate-hidden", swap: "innerHTML" });
    }
    syncStepBadgeState();
  };

  const wireDeliveryMethodToggle = () => {
    document.querySelectorAll('input[name="delivery_method"]').forEach((input) => {
      if (input.dataset.deliveryMethodBound === "true") {
        return;
      }
      input.dataset.deliveryMethodBound = "true";
      input.addEventListener("change", () => {
        syncDeliveryMethodUI(true);
      });
    });
    syncDeliveryMethodUI(false);
  };

  window.quickPhoneNPSelectCity = (button) => {
    const cityNameInput = document.getElementById("id_np_city_name");
    const cityRefInput = document.getElementById("id_np_city_ref");
    const warehouseRef = document.getElementById("id_np_warehouse_ref");
    const warehouseName = document.getElementById("id_np_warehouse_name");
    const cityResults = document.getElementById("np-city-results");
    const warehouseContainer = document.getElementById("np-warehouse-container");
    const selectedCityRef = button?.dataset?.cityRef || "";

    if (cityNameInput) {
      cityNameInput.value = button.dataset.cityName || "";
    }
    if (cityRefInput) {
      cityRefInput.value = selectedCityRef;
    }
    if (warehouseRef) {
      warehouseRef.value = "";
    }
    if (warehouseName) {
      warehouseName.value = "";
    }
    resetDeliveryEstimate();
    if (window.htmx && selectedCityRef && warehouseContainer) {
      const url = `/orders/np/warehouses/?city_ref=${encodeURIComponent(selectedCityRef)}`;
      window.htmx.ajax("GET", url, { target: "#np-warehouse-container", swap: "innerHTML" });
    }
    if (cityResults) {
      cityResults.innerHTML = "";
    }
    setStepBadgeState("delivery");
  };

  window.quickPhoneNPSelectWarehouse = (button) => {
    if (getSelectedDeliveryMethod() !== DELIVERY_METHOD_NOVA_POSHTA) {
      return;
    }

    const hiddenRef = document.getElementById("id_np_warehouse_ref");
    const warehouseName = document.getElementById("id_np_warehouse_name");
    const cityRef = document.getElementById("id_np_city_ref");
    const filterEmpty = document.getElementById("np-warehouse-filter-empty");
    const selectedWarehouseRef = button?.dataset?.warehouseRef || "";
    const selectedWarehouseName = button?.dataset?.warehouseName || "";

    if (hiddenRef) {
      hiddenRef.value = selectedWarehouseRef;
    }
    if (warehouseName) {
      warehouseName.value = selectedWarehouseName;
    }

    document.querySelectorAll(".np-warehouse-option").forEach((item) => {
      item.classList.remove("hidden");
      item.classList.remove("stitch-btn--solid");
      item.classList.add("stitch-btn--soft");
    });
    if (filterEmpty) {
      filterEmpty.classList.add("hidden");
    }

    if (window.htmx && hiddenRef && cityRef) {
      const url = `/orders/np/estimate/?city_ref=${encodeURIComponent(cityRef.value || "")}&warehouse_ref=${encodeURIComponent(hiddenRef.value || "")}`;
      window.htmx.ajax("GET", url, { target: "#np-estimate-hidden", swap: "innerHTML" });
    }
    setStepBadgeState("delivery");
  };

  const wireWarehouseFilter = () => {
    const warehouseInput = document.getElementById("id_np_warehouse_name");
    if (!(warehouseInput instanceof HTMLInputElement) || warehouseInput.type === "hidden") {
      return;
    }
    if (warehouseInput.dataset.warehouseFilterBound === "true") {
      return;
    }
    warehouseInput.dataset.warehouseFilterBound = "true";

    const applyFilter = () => {
      const query = (warehouseInput.value || "").trim().toLowerCase();
      const options = Array.from(document.querySelectorAll(".np-warehouse-option"));
      const emptyState = document.getElementById("np-warehouse-filter-empty");
      let visibleCount = 0;

      options.forEach((option) => {
        const label = (option.dataset.warehouseName || option.textContent || "").trim().toLowerCase();
        const isVisible = !query || label.includes(query);
        option.classList.toggle("hidden", !isVisible);
        if (isVisible) {
          visibleCount += 1;
        }
      });

      if (emptyState) {
        const showEmptyState = query.length > 0 && options.length > 0 && visibleCount === 0;
        emptyState.classList.toggle("hidden", !showEmptyState);
      }
    };

    warehouseInput.addEventListener("input", () => {
      const hiddenRef = document.getElementById("id_np_warehouse_ref");
      if (hiddenRef) {
        hiddenRef.value = "";
      }
      resetDeliveryEstimate();
      document.querySelectorAll(".np-warehouse-option").forEach((option) => {
        option.classList.remove("stitch-btn--solid");
        option.classList.add("stitch-btn--soft");
      });
      applyFilter();
    });

    warehouseInput.addEventListener("focus", applyFilter);
    applyFilter();
  };

  const extractLocalPhoneDigits = (value) => {
    const digits = (value || "").replace(/\D+/g, "");
    if (digits.startsWith("38")) {
      return digits.slice(2, 12);
    }
    return digits.slice(0, 10);
  };

  const formatPhoneForDisplay = (value) => {
    const localDigits = extractLocalPhoneDigits(value);
    if (!localDigits) {
      return "";
    }

    let formatted = "+38 (";
    formatted += localDigits.slice(0, 3);
    if (localDigits.length >= 3) {
      formatted += ")";
    }
    if (localDigits.length > 3) {
      formatted += ` ${localDigits.slice(3, 6)}`;
    }
    if (localDigits.length > 6) {
      formatted += ` ${localDigits.slice(6, 8)}`;
    }
    if (localDigits.length > 8) {
      formatted += ` ${localDigits.slice(8, 10)}`;
    }
    return formatted;
  };

  const wirePhoneDisplayMask = () => {
    const phoneInput = document.getElementById("id_contact_phone");
    if (!(phoneInput instanceof HTMLInputElement) || phoneInput.dataset.phoneMaskBound === "true") {
      return;
    }
    phoneInput.dataset.phoneMaskBound = "true";

    const applyDisplayFormat = () => {
      phoneInput.value = formatPhoneForDisplay(phoneInput.value);
    };

    phoneInput.addEventListener("input", applyDisplayFormat);
    phoneInput.addEventListener("blur", applyDisplayFormat);
    applyDisplayFormat();
  };

  const initCheckoutUI = () => {
    wireDeliveryMethodToggle();
    wireWarehouseFilter();
    wirePhoneDisplayMask();
    bindStepEvents();
    syncStepBadgeState();
  };

  document.addEventListener("DOMContentLoaded", initCheckoutUI);
  document.body.addEventListener("htmx:afterSwap", initCheckoutUI);
  if (document.readyState !== "loading") {
    initCheckoutUI();
  }
})();

