(() => {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const backgroundVariants = ["qp-bg-v1", "qp-bg-v2", "qp-bg-v3"];
  const lockedBackgroundVariant = "qp-bg-v3";
  const mediaMatches = (query) => window.matchMedia(query).matches;
  const userAgent = navigator.userAgent || "";
  const isAppleTouchDevice =
    /iP(hone|od|ad)/.test(userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const isIOSWebKit = isAppleTouchDevice && /WebKit/i.test(userAgent) && !/CriOS|FxiOS|EdgiOS/i.test(userAgent);
  const iOSVersionMatch = userAgent.match(/OS (\d+)_/);
  const iOSMajorVersion = iOSVersionMatch ? Number.parseInt(iOSVersionMatch[1], 10) : null;
  const isTouchDevice = navigator.maxTouchPoints > 0 || mediaMatches("(hover: none), (pointer: coarse)");
  const useLegacyMobileCompat = Boolean(isIOSWebKit && iOSMajorVersion && iOSMajorVersion < 17);
  const syncViewportHeight = () => {
    const viewportHeight = window.visualViewport ? window.visualViewport.height : window.innerHeight;
    document.documentElement.style.setProperty("--qp-app-height", `${Math.round(viewportHeight)}px`);
  };

  const applyBackgroundVariant = () => {
    backgroundVariants.forEach((name) => document.body.classList.remove(name));
    document.body.classList.add(lockedBackgroundVariant);
    try {
      window.localStorage.setItem("qp-bg-variant", lockedBackgroundVariant);
    } catch (error) {
      // Some Safari/private browsing setups block storage writes.
    }
  };

  syncViewportHeight();
  applyBackgroundVariant();
  document.body.classList.toggle("qp-touch-device", isTouchDevice);
  document.body.classList.toggle("qp-legacy-ios", useLegacyMobileCompat);
  window.addEventListener("resize", syncViewportHeight);
  window.addEventListener("orientationchange", syncViewportHeight);
  window.addEventListener("pageshow", syncViewportHeight);
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", syncViewportHeight);
  }

  const getCookie = (name) => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
      return parts.pop().split(";").shift();
    }
    return "";
  };

  document.body.addEventListener("htmx:configRequest", (event) => {
    event.detail.headers["X-CSRFToken"] = getCookie("csrftoken");
  });

  const isConstraintControl = (target) =>
    target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement;

  const getFieldLabelText = (field) => {
    if (!field.id) {
      return "";
    }
    const label = document.querySelector(`label[for="${field.id}"]`);
    if (!(label instanceof HTMLLabelElement)) {
      return "";
    }
    return (label.textContent || "").replace(/\s+/g, " ").trim();
  };

  const getRequiredFieldMessage = (field) => {
    const customMessage = field.getAttribute("data-required-message");
    if (customMessage) {
      return customMessage;
    }
    const labelText = getFieldLabelText(field);
    if (!labelText) {
      return "Заповніть це поле.";
    }
    return `Заповніть поле «${labelText}».`;
  };

  const setConstraintMessage = (field) => {
    field.setCustomValidity("");
    if (field.validity.valid) {
      return;
    }
    if (field.validity.valueMissing) {
      field.setCustomValidity(getRequiredFieldMessage(field));
      return;
    }
    field.setCustomValidity("Перевірте правильність заповнення поля.");
  };

  document.addEventListener(
    "invalid",
    (event) => {
      const target = event.target;
      if (!isConstraintControl(target)) {
        return;
      }
      setConstraintMessage(target);
    },
    true
  );

  const clearConstraintMessage = (event) => {
    const target = event.target;
    if (!isConstraintControl(target)) {
      return;
    }
    target.setCustomValidity("");
  };

  document.addEventListener("input", clearConstraintMessage, true);
  document.addEventListener("change", clearConstraintMessage, true);

  const navToggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav]");
  if (navToggle && nav) {
    const navHost = navToggle.closest(".stitch-header__inner");
    const profileMenus = Array.from(nav.querySelectorAll("[data-profile-menu]"));
    const catalogMenu = document.querySelector("[data-catalog-menu]");
    const catalogMenuTrigger = catalogMenu ? catalogMenu.querySelector("[data-catalog-menu-trigger]") : null;
    const catalogMenuUrl = catalogMenu ? catalogMenu.getAttribute("data-catalog-url") || "" : "";
    const isDesktopPointerMode = () => window.matchMedia("(hover: hover) and (pointer: fine)").matches;

    const closeProfileMenus = (exceptMenu = null) => {
      profileMenus.forEach((menu) => {
        if (menu !== exceptMenu) {
          menu.removeAttribute("open");
        }
      });
    };

    const closeCatalogMenu = () => {
      if (!catalogMenu) {
        return;
      }
      catalogMenu.removeAttribute("open");
      if (catalogMenuTrigger instanceof HTMLElement) {
        catalogMenuTrigger.setAttribute("aria-expanded", "false");
      }
    };

    const syncCatalogMenuState = () => {
      if (!catalogMenu || !(catalogMenuTrigger instanceof HTMLElement)) {
        return;
      }
      catalogMenuTrigger.setAttribute("aria-expanded", catalogMenu.hasAttribute("open") ? "true" : "false");
    };

    const closeHeaderMenus = () => {
      closeProfileMenus();
      closeCatalogMenu();
    };

    const setNavState = (isOpen) => {
      navToggle.setAttribute("aria-expanded", String(isOpen));
      nav.classList.toggle("is-open", isOpen);
      if (navHost) {
        navHost.classList.toggle("is-nav-open", isOpen);
      }
      if (!isOpen) {
        closeHeaderMenus();
      }
    };

    setNavState(false);
    syncCatalogMenuState();

    if (catalogMenu && catalogMenuTrigger instanceof HTMLElement) {
      catalogMenu.addEventListener("toggle", () => {
        syncCatalogMenuState();
        if (catalogMenu.open) {
          closeProfileMenus();
        }
      });

      catalogMenuTrigger.addEventListener("click", (event) => {
        if (!isDesktopPointerMode()) {
          return;
        }
        event.preventDefault();
        if (catalogMenuUrl) {
          window.location.assign(catalogMenuUrl);
        }
      });

      catalogMenu.addEventListener("pointerenter", () => {
        if (!isDesktopPointerMode()) {
          return;
        }
        catalogMenu.setAttribute("open", "");
        syncCatalogMenuState();
        closeProfileMenus();
      });

      catalogMenu.addEventListener("pointerleave", () => {
        if (!isDesktopPointerMode()) {
          return;
        }
        closeCatalogMenu();
      });
    }

    profileMenus.forEach((menu) => {
      const trigger = menu.querySelector(".stitch-profile-menu__trigger");
      const profileUrl = menu.getAttribute("data-profile-url") || "";

      const syncProfileMenuState = () => {
        if (trigger instanceof HTMLElement) {
          trigger.setAttribute("aria-expanded", menu.hasAttribute("open") ? "true" : "false");
        }
      };

      syncProfileMenuState();

      menu.addEventListener("toggle", () => {
        syncProfileMenuState();
        if (menu.open) {
          closeCatalogMenu();
          closeProfileMenus(menu);
        }
      });

      if (trigger instanceof HTMLElement) {
        trigger.addEventListener("click", (event) => {
          if (!isDesktopPointerMode()) {
            return;
          }
          event.preventDefault();
          if (profileUrl) {
            window.location.assign(profileUrl);
          }
        });
      }

      menu.addEventListener("pointerenter", () => {
        if (!isDesktopPointerMode()) {
          return;
        }
        menu.setAttribute("open", "");
        syncProfileMenuState();
        closeCatalogMenu();
        closeProfileMenus(menu);
      });

      menu.addEventListener("pointerleave", () => {
        if (!isDesktopPointerMode()) {
          return;
        }
        menu.removeAttribute("open");
        syncProfileMenuState();
      });
    });

    const closeHeaderMenusOnOutsideInteract = (event) => {
      const hasOpenProfile = profileMenus.some((menu) => menu.hasAttribute("open"));
      const hasOpenCatalog = Boolean(catalogMenu && catalogMenu.hasAttribute("open"));
      if (!hasOpenProfile && !hasOpenCatalog) {
        return;
      }
      const target = event.target;
      if (
        target instanceof Node &&
        (profileMenus.some((menu) => menu.contains(target)) || (catalogMenu && catalogMenu.contains(target)))
      ) {
        return;
      }
      closeHeaderMenus();
    };

    navToggle.addEventListener("click", () => {
      const expanded = navToggle.getAttribute("aria-expanded") === "true";
      const nextState = !expanded;
      if (nextState) {
        closeHeaderMenus();
      }
      setNavState(nextState);
    });

    document.addEventListener("click", (event) => {
      if (navToggle.getAttribute("aria-expanded") !== "true") {
        return;
      }
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      if (target.closest(".stitch-header")) {
        return;
      }
      setNavState(false);
    });

    if (window.PointerEvent) {
      document.addEventListener("pointerdown", closeHeaderMenusOnOutsideInteract, true);
    } else {
      document.addEventListener("touchstart", closeHeaderMenusOnOutsideInteract, true);
      document.addEventListener("mousedown", closeHeaderMenusOnOutsideInteract, true);
    }
    document.addEventListener("focusin", closeHeaderMenusOnOutsideInteract);

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeHeaderMenus();
      }
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 760) {
        setNavState(false);
      }
      closeHeaderMenus();
    });
  }

  const headerSearchForm = document.querySelector("[data-header-search-form]");
  const headerSearchInput = headerSearchForm ? headerSearchForm.querySelector("[data-header-search]") : null;
  const suggestionsHost = headerSearchForm ? headerSearchForm.querySelector("[data-search-suggestions]") : null;
  const suggestionsList = headerSearchForm ? headerSearchForm.querySelector("[data-search-suggestions-list]") : null;
  const suggestUrl = headerSearchForm ? headerSearchForm.getAttribute("data-search-suggest-url") : "";

  if (
    headerSearchForm &&
    headerSearchInput instanceof HTMLInputElement &&
    suggestionsHost instanceof HTMLElement &&
    suggestionsList instanceof HTMLElement &&
    suggestUrl
  ) {
    const searchMinLength = 2;
    const searchFieldWrap = headerSearchInput.closest(".stitch-header-search__field");
    let suggestDebounceId = 0;
    let activeRequest = null;
    let requestSequence = 0;

    const syncTypingState = () => {
      if (!searchFieldWrap) {
        return;
      }
      const isTyping = document.activeElement === headerSearchInput && headerSearchInput.value.trim().length > 0;
      searchFieldWrap.classList.toggle("is-typing", isTyping);
    };

    const hideSuggestions = () => {
      suggestionsList.innerHTML = "";
      suggestionsHost.hidden = true;
      headerSearchInput.setAttribute("aria-expanded", "false");
      syncTypingState();
    };

    const renderSuggestions = (items) => {
      suggestionsList.innerHTML = "";
      items.forEach((item) => {
        const li = document.createElement("li");
        const link = document.createElement("a");
        link.className = "stitch-header-search__suggestion";
        link.href = item.url || "#";

        const textWrap = document.createElement("span");
        textWrap.className = "stitch-header-search__suggestion-text";

        const title = document.createElement("span");
        title.className = "stitch-header-search__suggestion-title";
        title.textContent = item.title || "";

        textWrap.appendChild(title);

        if (item.subtitle) {
          const subtitle = document.createElement("span");
          subtitle.className = "stitch-header-search__suggestion-subtitle";
          subtitle.textContent = item.subtitle;
          textWrap.appendChild(subtitle);
        }

        link.appendChild(textWrap);

        if (Number.isFinite(Number(item.price_uah))) {
          const price = document.createElement("span");
          price.className = "stitch-header-search__suggestion-price";
          price.textContent = `${new Intl.NumberFormat("uk-UA").format(Number(item.price_uah))} UAH`;
          link.appendChild(price);
        }

        li.appendChild(link);
        suggestionsList.appendChild(li);
      });

      suggestionsHost.hidden = items.length === 0;
      headerSearchInput.setAttribute("aria-expanded", items.length > 0 ? "true" : "false");
      syncTypingState();
    };

    const requestSuggestions = async (query) => {
      const requestId = ++requestSequence;
      if (activeRequest && typeof activeRequest.abort === "function") {
        activeRequest.abort();
      }
      const controller = typeof window.AbortController === "function" ? new AbortController() : null;
      activeRequest = controller;

      try {
        const response = await fetch(`${suggestUrl}?q=${encodeURIComponent(query)}`, {
          headers: { Accept: "application/json" },
          signal: controller ? controller.signal : undefined,
        });
        if (requestId !== requestSequence || headerSearchInput.value.trim() !== query) {
          return;
        }
        if (!response.ok) {
          hideSuggestions();
          return;
        }
        const payload = await response.json();
        const items = Array.isArray(payload.items) ? payload.items.slice(0, 5) : [];
        if (requestId !== requestSequence || headerSearchInput.value.trim() !== query) {
          return;
        }
        renderSuggestions(items);
      } catch (error) {
        if (requestId === requestSequence && headerSearchInput.value.trim() === query && error.name !== "AbortError") {
          hideSuggestions();
        }
      } finally {
        if (requestId === requestSequence) {
          activeRequest = null;
        }
      }
    };

    const scheduleSuggestions = () => {
      const query = headerSearchInput.value.trim();
      window.clearTimeout(suggestDebounceId);
      syncTypingState();
      if (query.length < searchMinLength) {
        requestSequence += 1;
        if (activeRequest && typeof activeRequest.abort === "function") {
          activeRequest.abort();
        }
        activeRequest = null;
        hideSuggestions();
        return;
      }
      suggestDebounceId = window.setTimeout(() => {
        requestSuggestions(query);
      }, 220);
    };

    headerSearchInput.addEventListener("input", scheduleSuggestions);
    headerSearchInput.addEventListener("focus", scheduleSuggestions);
    headerSearchInput.addEventListener("blur", syncTypingState);
    headerSearchInput.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hideSuggestions();
      }
    });

    headerSearchForm.addEventListener("submit", () => {
      hideSuggestions();
      if (searchFieldWrap) {
        searchFieldWrap.classList.remove("is-typing");
      }
    });

    document.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      if (target.closest("[data-header-search-form]")) {
        return;
      }
      hideSuggestions();
    });
  }

  const cartButton = document.querySelector("[data-cart-open]");
  const panel = () => document.getElementById("cart-panel");
  const feedbackHost = () => document.getElementById("global-feedback");
  let feedbackDismissTimer = 0;

  const clearFeedbackDismissTimer = () => {
    if (!feedbackDismissTimer) {
      return;
    }
    window.clearTimeout(feedbackDismissTimer);
    feedbackDismissTimer = 0;
  };

  const hideFeedbackToast = () => {
    const host = feedbackHost();
    if (!(host instanceof HTMLElement)) {
      return;
    }
    const toast = host.querySelector("[data-feedback-toast]");
    clearFeedbackDismissTimer();
    if (!(toast instanceof HTMLElement)) {
      host.innerHTML = "";
      return;
    }
    toast.classList.add("is-hiding");
    window.setTimeout(() => {
      if (host.contains(toast)) {
        host.innerHTML = "";
      }
    }, 190);
  };

  const mountFeedbackToast = () => {
    const host = feedbackHost();
    if (!(host instanceof HTMLElement)) {
      return;
    }
    const toast = host.querySelector("[data-feedback-toast]");
    clearFeedbackDismissTimer();
    if (!(toast instanceof HTMLElement)) {
      return;
    }

    const dismissButton = toast.querySelector("[data-feedback-dismiss]");
    if (dismissButton instanceof HTMLButtonElement) {
      dismissButton.addEventListener("click", hideFeedbackToast);
    }

    let timeout = 3000;
    if (toast.classList.contains("stitch-feedback--info")) {
      timeout = 3600;
    } else if (toast.classList.contains("stitch-feedback--error")) {
      timeout = 4400;
    }

    feedbackDismissTimer = window.setTimeout(hideFeedbackToast, timeout);
  };

  const setCartButtonState = (isActive) => {
    if (!cartButton) {
      return;
    }
    cartButton.classList.toggle("is-active", isActive);
    cartButton.setAttribute("aria-pressed", String(isActive));
  };

  if (cartButton) {
    const initialPanel = panel();
    setCartButtonState(Boolean(initialPanel && initialPanel.classList.contains("is-open")));
    cartButton.addEventListener("click", () => {
      const el = panel();
      if (!el) {
        return;
      }
      const nextState = !el.classList.contains("is-open");
      el.classList.toggle("is-open", nextState);
      setCartButtonState(nextState);
    });
  }

  document.body.addEventListener("htmx:afterSettle", (event) => {
    const target = event.detail && event.detail.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    // Wait for HTMX to finish restoring attributes on the swapped cart panel.
    if (target.id !== "global-feedback") {
      return;
    }
    mountFeedbackToast();
    const el = panel();
    if (el) {
      el.classList.add("is-open");
      setCartButtonState(true);
    }
  });

  document.addEventListener("click", (event) => {
    if (!cartButton) {
      return;
    }
    const el = panel();
    if (!el || !el.classList.contains("is-open")) {
      return;
    }
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (target.closest("[data-cart-open]") || target.closest("#cart-panel") || target.closest("#global-feedback")) {
      return;
    }
    el.classList.remove("is-open");
    setCartButtonState(false);
  });

  if (prefersReducedMotion || useLegacyMobileCompat) {
    document.body.classList.add("qp-reduce-motion");
  }

  mountFeedbackToast();

  let headerScrollFrame = 0;
  const syncHeaderScrollState = () => {
    headerScrollFrame = 0;
    document.body.classList.toggle("qp-header-scrolled", window.scrollY > 8);
  };
  const scheduleHeaderScrollState = () => {
    if (headerScrollFrame) {
      return;
    }
    headerScrollFrame = window.requestAnimationFrame(syncHeaderScrollState);
  };

  syncHeaderScrollState();
  window.addEventListener("scroll", scheduleHeaderScrollState, { passive: true });
})();

