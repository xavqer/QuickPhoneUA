(() => {
  const gallery = document.querySelector("[data-gallery]");
  const hero = document.getElementById("detail-hero-image");
  const tabsHost = document.querySelector("[data-detail-tabs]");

  if (tabsHost) {
    const triggers = tabsHost.querySelectorAll("[data-tab-trigger]");
    const panels = tabsHost.querySelectorAll("[data-tab-panel]");

    const setTab = (tabName) => {
      panels.forEach((panel) => {
        const isActive = panel.getAttribute("data-tab-panel") === tabName;
        panel.hidden = !isActive;
        panel.setAttribute("aria-hidden", String(!isActive));
      });

      triggers.forEach((trigger) => {
        const isActive = trigger.getAttribute("data-tab-trigger") === tabName;
        trigger.setAttribute("aria-selected", String(isActive));
        trigger.classList.toggle("is-active", isActive);
      });
    };

    triggers.forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const tabName = trigger.getAttribute("data-tab-trigger");
        if (!tabName) {
          return;
        }
        setTab(tabName);
      });
    });

    setTab("description");
  }

  if (!gallery || !hero) {
    return;
  }

  const thumbs = gallery.querySelectorAll("[data-thumb-src]");
  thumbs.forEach((button) => {
    button.addEventListener("click", () => {
      const src = button.getAttribute("data-thumb-src");
      const alt = button.getAttribute("data-thumb-alt") || "";
      if (!src) {
        return;
      }
      hero.src = src;
      hero.alt = alt;
      thumbs.forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
    });
  });
})();

