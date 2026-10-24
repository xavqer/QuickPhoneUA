# Design Foundation Quality Checklist

Use this checklist when changing shared styles or storefront templates.

## Accessibility Baseline

- [ ] Text and control contrast meets WCAG AA intent for primary interactions.
- [ ] Keyboard navigation shows a clear visible focus state (`:focus-visible`) on interactive primitives.
- [ ] Error states remain readable and do not rely only on color.

## Motion and Comfort

- [ ] The shared shell retains its static `qp-performance-lite` profile on every page.
- [ ] `prefers-reduced-motion` reduces non-essential transitions and motion effects.
- [ ] No decorative motion blocks core actions or delays user input feedback.
- [ ] Motion checks compare normal mode vs reduced mode on the same interactions (nav toggle, cart panel open, catalog card hover).
- [ ] Navigation and cart interactions are checked on desktop and a touch viewport.

## Primitive Consistency

- [ ] Shared primitives are used for button/input/surface/chip/nav-shell behaviors.
- [ ] New UI work avoids page-local visual one-offs that bypass tokenized primitives.
- [ ] Variant/state coverage exists for default, hover, focus, disabled, and error where applicable.

## Liquid Glass Guardrails

- [ ] Glass effects stay subtle and localized.
- [ ] Background gradients remain calm, light, and low contrast.
- [ ] Dense text-heavy visual blocks are rejected and reworked.

## Regression Safety

- [ ] Base shell continues to load compiled `css/tailwind.css` and shared `css/stitch_mvp.css`.
- [ ] Critical templates still render nav/cart interaction hooks.
- [ ] Automated tests cover design-system wiring in core user flows.

## Home/Catalog Responsive Checks

- [ ] Home hero keeps readable heading, lead copy, and CTA buttons on desktop and mobile.
- [ ] Catalog desktop keeps sticky filter panel and visible active-filter chip row above result cards.
- [ ] Catalog mobile uses filter drawer open/close controls and backdrop interaction.
- [ ] Catalog mobile grid stays two columns and keeps card text readable without overlap.
- [ ] Glass intensity is reduced on mobile surfaces versus desktop to preserve clarity.
- [ ] Playwright capture set includes `/` and `/catalog/` at desktop and mobile widths for visual signoff.

