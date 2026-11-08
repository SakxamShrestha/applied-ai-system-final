# Assets

The system architecture diagram's **source of record** is
[`../diagrams/architecture.mmd`](../diagrams/architecture.mmd) — a Mermaid source file, as
the project requirements specify. It also renders inline in the
[README](../README.md#architecture) on GitHub.

This folder holds optional rendered images of that diagram.

## Exporting a PNG

From the project root:

```bash
npx -y @mermaid-js/mermaid-cli -i diagrams/architecture.mmd -o assets/architecture.png -b white -w 1800
```

Or paste the contents of `diagrams/architecture.mmd` into https://mermaid.live and use its
PNG export.

Keep the `.mmd` file as the thing you edit; a PNG is a build output of it, not a substitute.
