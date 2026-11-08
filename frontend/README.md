# Frontend

React + TypeScript + Vite + Electron. UI uses Tailwind CSS v4 through `@tailwindcss/vite`.

## Development

- `npm run dev:browser` — browser development.
- `npm run dev:electron` — compiles the Electron main and preload scripts and starts the app.
- `npm run typecheck` — checks the renderer, Vite config and Electron.
- `npm run build:electron` — emits Electron scripts in `dist-electron`.
- `npm run build:web` — production web build.
- `VITE_API_URL` overrides the default `http://127.0.0.1:8000/api`.

The `@/` alias points to `src/`. Vite and the editor read the same mapping from
`tsconfig.json`.

## Mock API

Copy `.env.example` to `.env.local`, set `VITE_USE_MOCKS=true`, and run
`npm run dev:browser` or `npm run dev:electron`. Restart Vite after changing
environment variables. The mock works without a backend. Changes are kept in
memory and reset when the app reloads. Mock imports use the selected filename
to create a demo record.

| `VITE_MOCK_SCENARIO` | Behavior |
| --- | --- |
| `populated` (default) | Demo worlds, characters, and a session with chat history. Send a message to see SSE progress and a response. |
| `empty` | Empty lists. Import a world and a character to start a session with empty history. |
| `network-error` | Requests fail after a short delay, so loading and network error states can be checked. |
| `stream-error` | Demo data loads. Sending a chat message ends with an SSE error. |

The UI-facing DTOs and events are described in [API-CONTRACTS.md](./API-CONTRACTS.md).

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
