# QuickPhoneUA Redesign Philosophy

## Visual Principles

QuickPhoneUA should feel premium, calm, and trustworthy. The visual language uses subtle liquid-glass layering to elevate product perception without reducing readability.

- Premium is expressed through restraint: clean spacing, clear hierarchy, and controlled contrast.
- Glass surfaces are subtle and localized (navigation, cards, action zones), never full-screen haze.
- Background gradients are light and calm with low contrast.
- Product trust signals (price, condition, availability, CTA) stay dominant over decoration.

## System Rules

### Tokens First

Reuse the tokens and component styles already defined in `static/css/stitch_mvp.css`.

- Existing tokens include `--bg`, `--text`, `--muted`, `--glass-*`, and `--qp-*`.
- Avoid new hardcoded color/blur/shadow values in page templates.

### Primitive Reuse

Use shared primitives before adding page-level styles.

- Buttons: `stitch-btn` with `stitch-btn--solid` or `stitch-btn--soft`
- Inputs: `qp-input`
- Surfaces/Cards: `qp-glass-section`, `qp-glass-soft`, and `stitch-product-card`
- Chips/Badges: `stitch-chip` and `stitch-badge`
- Nav shell: the shared `partials/navbar.html` template

### Hierarchy and Density

- Keep scan path simple: title -> supporting context -> primary action.
- Limit dense text clusters in cards and action blocks.
- Use spacing rhythm from tokens; avoid one-off spacing hacks.

## Accessibility Guardrails

- Meet WCAG AA contrast for text and controls.
- Keyboard focus must remain obvious with `:focus-visible`.
- The shared shell uses the static `qp-performance-lite` profile on every page.
- Respect `prefers-reduced-motion` by reducing non-essential transitions.

## Do

- Use subtle translucency with clear borders.
- Keep gradients soft and low contrast.
- Preserve clear CTA prominence and content readability.
- Keep interaction feedback quick and predictable.

## Do Not

- Do not introduce dense text-heavy visual blocks.
- Do not use neon glow or dramatic high-contrast gradients.
- Do not overuse heavy blur on large surfaces.
- Do not create page-specific visual variants that bypass primitives.

## Component Rules

### Button
- Reuse the solid and soft variants of `stitch-btn`.
- Follow existing template sizing and responsive classes.
- Disabled state must reduce emphasis but stay legible.

### Input
- Clear border and fill contrast.
- Distinct focus ring.
- Error state visible without relying on color alone.

### Surface/Card
- Use tokenized glass surface levels.
- Pair translucency with border + depth token.
- Keep internal spacing consistent.

### Navbar Shell
- Sticky glass shell with calm blur.
- Navigation items readable at all breakpoints.
- Cart action remains clearly discoverable.

