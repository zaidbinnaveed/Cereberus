# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

The selected visual target for Cereberus is `.design/cereberus-spatial-gateway-reference.png` in the repository root (the second generated “Spatial Gateway” concept). Preserve its full-bleed live-camera hierarchy, sparse spatial-glass controls, violet/cyan scan treatment, and low-profile activity timeline. The product must remain an operational access-control console rather than a marketing dashboard.

Build app UI in `src/`. Validate production changes with `npm run build`; the output is written to `dist/client` and served locally by `src.web`.
