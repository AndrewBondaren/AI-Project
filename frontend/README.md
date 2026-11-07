# Frontend

React + Vite + Electron. UI uses Tailwind CSS v4 through `@tailwindcss/vite`.

## Development

- `npm run dev:browser` — browser development.
- `npm run dev:electron` — Electron development.
- `npm run build:web` — production web build.
- `VITE_API_URL` overrides the default `http://127.0.0.1:8000/api`.

## Structure

- `src/app` — providers, router, application layout and global Tailwind theme.
- `src/pages/home` — campaign list.
- `src/pages/session` — session screen and composition of character selection/import.
- `src/pages/settings` — existing backend/world settings screens.
- `src/widgets/app-sidebar`, `session-header`, `chat-panel` — application UI blocks.
- `src/features/create-session`, `send-message`, `import-world`, `import-character` — user actions.
- `src/entities/session`, `message`, `world`, `character` — domain data, models and UI.
- `src/shared/api` — existing backend HTTP/SSE contracts.
- `src/shared/ui`, `lib`, `config`, `types` — reusable primitives, platform helpers, configuration and shared types.
- `public/icons` — SVG icons; `public/images` — raster image assets.

Dependencies point downward: app → pages → widgets → features → entities → shared.
Compose separate features in pages/widgets. Entities and shared do not import features.
The session provider supplies the same campaign list to the home page and sidebar.

## Styling

`src/app/styles/tailwind.css` imports Tailwind and defines design tokens using `@theme`.
Use semantic utilities such as `bg-panel`, `text-muted`, `border-line`, and `font-display`.
`global.css` contains only application-wide base rules. Component styles and responsive
states are expressed in Tailwind utilities; CSS Modules are no longer used.

The session creation dialog imports worlds and characters through the existing backend endpoints.
Electron sends the selected local path, and the browser uploads the selected file.
