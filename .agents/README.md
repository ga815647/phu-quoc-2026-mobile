# Repo-local design tools

Codex automatically discovers repo skills under `.agents/skills`.

- `frontend-design` is vendored from Anthropic's official skills repository at a pinned commit. It is used for visual direction, typography, hierarchy, copy, restraint, and self-critique.
- OpenAI's proprietary `product-design` plugin is not copied into this repository. `.agents/plugins/marketplace.json` exposes the official pinned Git subdirectory as a repo marketplace entry instead.

The Product Design plugin includes screenshot-backed UX audit workflows. In ChatGPT desktop / Codex surfaces that support repo marketplaces, restart the app if needed, open the Plugins Directory, select `Phu Quoc 2026 Design Tools`, and install `Product Design`.

Keep the deterministic Playwright smoke checks even when using design skills: design review and regression testing serve different purposes.
