# Cafe React: 404 investigation and next checks

Status: the specific 22 October 2026 browser-log issue is understood; the app files were repaired. The current browser was not available for a visual smoke test.

## What the log proves

At 22:11, the server returned `200` for `/` and `/style.css`, then `404` for `/style.js` and `/favicon.ico`.

- `/style.js` was a bad asset reference and needed to be removed. Do not rename `style.css` to `.js` or load CSS with a script tag.
- `/favicon.ico` is a browser icon lookup. A missing icon does not stop the page rendering. The app now declares `favicon.svg`; if a browser still requests `.ico`, verify rendering separately before treating that request as a failure.
- A separate, page-breaking defect was found in `index.html`: the Babel CDN URL was invalid. It now points to `@babel/standalone/babel.min.js`.
- The project is React loaded from CDN, not a bundled/Vite React app. It needs network access for React and Babel. `app.js` uses the loaded browser globals and React 18 `createRoot`.

Current files: `workspace/Cafe_React/{index.html,style.css,app.js,favicon.svg}`. The persisted directory is `.data/agent-core/workspace/Cafe_React`.

## Verified so far

- Local static-server requests returned `200` for `/`, `/style.css`, `/app.js`, and `/favicon.svg`.
- The Babel CDN URL returned `200` after redirects.
- Compose config validated and all 83 agent-core tests passed.
- No graphical browser check was available, so visual rendering and browser-console errors remain unverified.

## Avoid repeating the failure

For every generated web project, Aria should:

1. Inspect the actual HTML and files before diagnosing a 404.
2. Match every local `src`/`href` path exactly, including filename case and extension. Keep CSS in `<link rel="stylesheet">`; keep JavaScript in `<script>`.
3. Check server logs and browser console separately. A favicon request is not proof the app failed.
4. Confirm the server root is the project directory and use a free port. Port `8000` was already occupied; the previous run served on `8080`.
5. Verify the page and each referenced local asset return `200`; then check browser rendering and console before saying it works.
6. Report only files actually written and checks actually run. The supplied Telegram trace had `used_tools: []`, so Aria did not create files through her workspace tools and the code reviewer did not run.

## Tomorrow's checklist

1. Rotate the Telegram bot token if the old token was exposed; update the local `.env` without sharing the token in chat.
2. Recreate the agent with the built non-root configuration: `python3 tools/aria start --channels cli,web,telegram`.
3. Confirm `docker compose exec agent-core id` reports the host user's UID/GID, then create a small test project from Telegram and confirm it appears under `workspace/` and is editable by the host user.
4. In `http://localhost:8080/` (or the port actually in use), confirm the cafe page renders and inspect the browser console. Treat a remaining `/favicon.ico` 404 as harmless only if the declared icon loads and the page renders.
5. Check `/aria-trace`: a real project build should show workspace tool calls and file paths. A code-review entry should appear only when the reviewer is explicitly invoked.

The coding prompt now asks for evidence-based diagnosis and post-write asset checks, but prompt instructions alone cannot guarantee model compliance. A deterministic artifact-write gate/retry and any OpenCode coding-worker integration remain future work; neither was added in this incident fix.
