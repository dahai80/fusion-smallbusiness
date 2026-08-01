# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This is a **new/empty project** within the `fusion` monorepo (`/Users/dahai/fusion/`). No source code, build system, or tests exist yet. The project name suggests a small business oriented application built on the Fusion platform.

## Monorepo Context

`fusion-smallbusiness` sits alongside many sibling Fusion projects:
- `fusion-core` — core libraries
- `fusion-cli` — CLI tooling
- `fusion-gateway` — API gateway
- `fusion-agent-studio`, `fusion-cowork`, `fusion-studio` — agent/studio apps
- `fusion-model-hub` — model management
- `fusion-plugins-ecosystem` — plugin system
- `fusion-kb`, `fusion-doc` — knowledge base / docs

Cross-project changes follow the upstream workflow: file issue → PR → merge → update downstream code. Do not modify sibling projects directly.

## Environment Setup

```bash
cd /Users/dahai/fusion/fusion-smallbusiness
source .venv/bin/activate   # activate once a venv exists
```

## Fusion-MLX Integration

If testing requires a local LLM:
- Start: `~/claude-home/fusion-mlx/start.sh start`
- Stop: `~/claude-home/fusion-mlx/start.sh stop`
- Model downloads: use mirror `https://hf-mirror.com`
