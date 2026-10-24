(() => {
  const AUTO_ADVANCE_MS = 3200;
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const isTouchDevice = window.matchMedia("(hover: none), (pointer: coarse)").matches;
  const usePerformanceLite = document.body.classList.contains("qp-performance-lite");

  function getPerView() {
    if (window.matchMedia("(max-width: 760px)").matches) {
      return 1;
    }
    if (window.matchMedia("(max-width: 960px)").matches) {
      return 2;
    }
    return 3;
  }

  function wrapIndex(value, length) {
    if (length <= 0) {
      return 0;
    }
    return ((value % length) + length) % length;
  }

  function initCarousel(carousel) {
    if (carousel.dataset.carouselReady === "true") {
      return;
    }
    carousel.dataset.carouselReady = "true";

    const section = carousel.closest("section");
    const track = carousel.querySelector("[data-carousel-track]");
    const slides = Array.from(track ? track.querySelectorAll(".home-carousel__slide") : []);
    const dots = carousel.querySelector("[data-carousel-dots]");
    const prevButton = section ? section.querySelector("[data-carousel-prev]") : null;
    const nextButton = section ? section.querySelector("[data-carousel-next]") : null;

    if (!track || !slides.length) {
      return;
    }

    let currentIndex = 0;
    let windowCount = Math.max(1, slides.length - getPerView() + 1);
    let autoAdvanceId = null;
    let resizeId = null;
    let scrollSyncId = null;
    let inViewport = true;
    const allowMotion = !(prefersReducedMotion || isTouchDevice || usePerformanceLite);

    const setActiveDot = () => {
      if (!dots) {
        return;
      }
      Array.from(dots.children).forEach((dot, index) => {
        const isActive = index === currentIndex;
        dot.classList.toggle("is-active", isActive);
        dot.setAttribute("aria-current", isActive ? "true" : "false");
      });
    };

    const goTo = (nextIndex, smooth = true) => {
      currentIndex = wrapIndex(nextIndex, windowCount);
      const targetSlide = slides[currentIndex];
      if (!targetSlide) {
        return;
      }
      const targetLeft = targetSlide.offsetLeft - track.offsetLeft;
      track.scrollTo({left: targetLeft, behavior: smooth && allowMotion ? "smooth" : "auto"});
      setActiveDot();
    };

    const buildDots = () => {
      if (!dots) {
        return;
      }
      dots.innerHTML = "";
      dots.hidden = windowCount <= 1;
      if (windowCount <= 1) {
        return;
      }

      for (let index = 0; index < windowCount; index += 1) {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "home-carousel__dot";
        dot.setAttribute("aria-label", `Перейти до позиції ${index + 1}`);
        dot.addEventListener("click", () => {
          goTo(index);
          startAutoAdvance();
        });
        dots.appendChild(dot);
      }
      setActiveDot();
    };

    const syncFromScroll = () => {
      if (windowCount <= 1) {
        return;
      }

      const scrollLeft = track.scrollLeft;
      let nearestIndex = 0;
      let nearestDistance = Number.POSITIVE_INFINITY;

      for (let index = 0; index < windowCount; index += 1) {
        const slideLeft = slides[index].offsetLeft - track.offsetLeft;
        const distance = Math.abs(slideLeft - scrollLeft);
        if (distance < nearestDistance) {
          nearestDistance = distance;
          nearestIndex = index;
        }
      }

      currentIndex = nearestIndex;
      setActiveDot();
    };

    const stopAutoAdvance = () => {
      if (autoAdvanceId) {
        window.clearInterval(autoAdvanceId);
        autoAdvanceId = null;
      }
    };

    const startAutoAdvance = () => {
      stopAutoAdvance();
      if (!allowMotion || windowCount <= 1 || !inViewport || document.hidden) {
        return;
      }
      autoAdvanceId = window.setInterval(() => {
        goTo(currentIndex + 1);
      }, AUTO_ADVANCE_MS);
    };

    const updateMetrics = () => {
      const visibleSlots = Math.min(getPerView(), slides.length);
      track.style.setProperty("--home-carousel-visible", String(visibleSlots));
      windowCount = Math.max(1, slides.length - visibleSlots + 1);
      if (currentIndex >= windowCount) {
        currentIndex = 0;
      }

      if (prevButton) {
        prevButton.hidden = windowCount <= 1;
      }
      if (nextButton) {
        nextButton.hidden = windowCount <= 1;
      }

      carousel.classList.toggle("is-static", windowCount <= 1);
      buildDots();
      goTo(currentIndex, false);
      startAutoAdvance();
    };

    prevButton?.addEventListener("click", () => {
      goTo(currentIndex - 1);
      startAutoAdvance();
    });

    nextButton?.addEventListener("click", () => {
      goTo(currentIndex + 1);
      startAutoAdvance();
    });

    track.addEventListener(
      "scroll",
      () => {
        window.clearTimeout(scrollSyncId);
        scrollSyncId = window.setTimeout(syncFromScroll, 90);
      },
      {passive: true}
    );

    carousel.addEventListener("mouseenter", stopAutoAdvance);
    carousel.addEventListener("mouseleave", startAutoAdvance);
    carousel.addEventListener("focusin", stopAutoAdvance);
    carousel.addEventListener("focusout", startAutoAdvance);

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        stopAutoAdvance();
      } else {
        startAutoAdvance();
      }
    });

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          inViewport = entries.some((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.35);
          if (inViewport) {
            startAutoAdvance();
          } else {
            stopAutoAdvance();
          }
        },
        {threshold: [0.35]}
      );
      observer.observe(carousel);
    }

    window.addEventListener("resize", () => {
      window.clearTimeout(resizeId);
      resizeId = window.setTimeout(updateMetrics, 140);
    });

    updateMetrics();
  }

  function initHomeCarousels() {
    document.querySelectorAll("[data-home-carousel]").forEach(initCarousel);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initHomeCarousels, {once: true});
  } else {
    initHomeCarousels();
  }
})();
