# Repo-local design tools

Codex automatically discovers repo skills under `.agents/skills`.

- `frontend-design` is vendored from Anthropic's official skills repository at a pinned commit. It is used for visual direction, typography, hierarchy, copy, restraint, and self-critique.
- OpenAI's official `product-design` plugin is proprietary and therefore is **not vendored into this repository**. Install it from Codex's official plugin marketplace when using a Codex surface that supports plugins. Its audit workflow is useful for screenshot-backed UX, design, and accessibility review.

For this repository, use the layers for different jobs:

1. `frontend-design` — design direction and self-critique.
2. OpenAI Product Design / audit — interactive screenshot-backed review when the plugin is installed and the required browser surface is available.
3. `.github/workflows/v2-ux-audit.yml` — reproducible mobile journey screenshots and interaction metrics.
4. `.github/workflows/v2-mobile-smoke.yml` — deterministic regression checks.

Do not copy the proprietary Product Design plugin files into this repo. Keep the deterministic Playwright checks even when design skills/plugins are available: design review and regression testing serve different purposes.
