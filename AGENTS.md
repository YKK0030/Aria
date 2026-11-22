# Repository Guidelines

## Project Structure & Module Organization

Aria is a multi-service agent project. `services/agent-core/src/agent_core/` contains the Python FastAPI and Agno runtime, channel integrations, memory, prompts, skills, and tool registry. Its tests are in `services/agent-core/tests/`. The React/Vite control UI lives in `services/agent-core/frontend/`. `services/whatsapp-gateway/src/` contains the TypeScript Fastify/Baileys gateway. Shared Python tools are discovered from the repository-root `tools/` directory. `skills/` contains skill manifests and prompt packs; `config/` holds policies and monitoring configuration; `docs/` contains setup and architecture notes. Runtime state belongs under `.data/`, not in source control.

## Build, Test, and Development Commands

- `npm run up` builds and starts the Docker Compose stack in the background.
- `npm run dev` builds and starts the stack in the foreground.
- `npm run down` stops the stack; `npm run logs` follows its logs.
- `PYTHONPATH=services/agent-core/src python -m unittest discover -s services/agent-core/tests` runs the Python unit tests.
- `npm run build --prefix services/whatsapp-gateway` type-checks and builds the gateway with TypeScript.

Copy `.env.example` to `.env` for local configuration. Keep credentials and runtime data out of commits. See `docs/local-startup.md` for local service setup.

## Coding Style & Naming Conventions

Follow the surrounding code. Python uses four-space indentation, type hints, and `snake_case`; TypeScript and JavaScript use the existing module style and `camelCase`. Keep FastAPI routes in `agent_core/main.py` focused on request handling, place agent behavior in its runtime/tooling modules, and keep gateway routes in `services/whatsapp-gateway/src/`. No repository-wide formatter or linter is configured; the gateway TypeScript build checks types.

## Testing Guidelines

Python tests use the standard-library `unittest` framework and `test_*.py` names. Run the suite with the command above, or target one file with `python -m unittest discover -s services/agent-core/tests -p 'test_tool_registry.py'`. The WhatsApp gateway has a TypeScript build check but no configured test script. Do not report the build as a test run.

## Commit & Pull Request Guidelines

Recent commits use concise conventional prefixes such as `feat:` and `docs(architecture):`. Use a short type and summary where appropriate. Pull requests should explain the behavior changed, list verification commands and results, link related issues, and include UI screenshots when frontend appearance changes. Call out configuration or persisted-data effects.

## Security & Configuration

Never commit `.env`, API keys, WhatsApp session credentials, or personal data. Treat admin endpoints, access policies, and workspace tools as security boundaries; avoid exposing local services beyond their intended network.
