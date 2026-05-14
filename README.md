# claude-ha

Configuration and provisioning for **Claude Opus via LiteLLM/Bedrock** as the conversation backend for a Home Assistant voice assistant, expanding the [extended_openai_conversation](https://github.com/jekalmin/extended_openai_conversation) HACS **integration** (a `custom_component`, not an addon) with broader tool access.

> **Terminology:** "HACS integration" ≠ "HACS addon". Integrations are Python custom_components that run inside HA core (lives at `/config/custom_components/<name>/`). Addons are standalone Docker containers (lives at `/addons/` or installed via Supervisor). This repo configures an integration.

## What this gives Claude

Six tools, in order of blast radius:

| Tool | Scope | Purpose |
|---|---|---|
| `execute_services` | any HA service | Toggle/set anything (lights, climate, scripts, automations…) |
| `get_attributes` | any entity | Read state + attributes |
| `load_skill` | `skills/` subdir | Read skill files |
| `read_file` | anywhere under `/config` | Inspect automations.yaml, configuration.yaml, esphome configs, etc. **Do not read `secrets.yaml` or `.storage/`.** |
| `query_history` | recorder DB (SELECT only) | Query state history — "when did the door last open?" |
| `bash` | `/config/extended_openai_conversation/` only | Shell with cwd in the workspace, blocked from `/config/` siblings |

Stock extended_openai_conversation only enables `execute_services`, `get_attributes`, `load_skill`, `bash`. This repo adds `read_file` + `query_history` and provisions the workspace dir that `bash` requires.

## Architecture

```
M5Stack ATOM Echo  →  Wyoming  →  faster-whisper STT
                                       ↓
              conversation.extended_openai_conversation
                                       ↓
                                LiteLLM (e.g., ubox0:4000)
                                       ↓
                                  AWS Bedrock
                                       ↓
                                Claude Opus 4.7
                                       ↓
                                  piper TTS
                                       ↓
                                 Speaker out
```

The voice satellite uses an on-device wake word (e.g., `donkee` or `Okay Nabu` via `micro_wake_word`) that runs entirely on the ESP32. STT and TTS run locally in HA. Only the LLM hop goes to Bedrock.

## Install

Prereqs:
- Home Assistant OS or Supervised
- The HACS `extended_openai_conversation` integration installed and configured against LiteLLM (or any OpenAI-compatible endpoint)
- SSH access to the HA host (via the Advanced SSH & Web Terminal addon)
- A long-lived access token for HA REST API
- Optional: a firewall rule allowing the M5Stack's VLAN to reach HA's Caddy/proxy on 443 (see [docs/firewall.md](docs/firewall.md))

Provision:

```bash
HA_HOST=10.0.6.108 HA_URL=https://ha.example HA_TOKEN=$(bw get password ha-llat) \
  ./provision.sh
```

This will:
1. Create `/config/extended_openai_conversation/` with `README.md`, `backups/`, `skills/`
2. Back up `/config/.storage/core.config_entries`
3. **Stop HA core** (required — HA debounce-writes its in-memory state and overwrites edits while running)
4. Patch the Claude conversation subentry's `functions` YAML to add `read_file` and `query_history`
5. Start HA core
6. Verify the new tools are reported by the conversation API

After install you should be able to ask:
- "Read configuration.yaml and tell me what integrations are loaded" → `read_file`
- "When did the front door last open?" → `query_history`
- "Save a note about the laundry cycle in the workspace" → `bash`

## Safety

`bash` is sandboxed to `/config/extended_openai_conversation/` via the integration's `restrict_to_workspace` default. `read_file` is broad (`allow_dir: /config`) but Claude is prompted to avoid `secrets.yaml` and `.storage/`. `query_history` runs through the integration's SQLite wrapper which rejects non-SELECT statements.

This is appropriate for a **single-household voice assistant**. For multi-tenant or networked deployments, see [docs/safety.md](docs/safety.md) for hardening tips.

## Files in this repo

- `provision.sh` — orchestrator
- `patches/extend_eoac_functions.py` — adds `read_file` + `query_history` to the conversation subentry YAML
- `patches/voice_prompt.txt` — trimmed system prompt that delegates entity discovery to tool calls (cache-friendly)
- `workspace-template/` — files seeded into `/config/extended_openai_conversation/`
- `docs/tools.md` — per-tool reference with example prompts
- `docs/safety.md` — threat model + hardening
- `docs/performance.md` — latency stack + Bedrock prompt-caching setup

## Status

Production at home as of 2026-05-14. Tested against:
- Home Assistant 2026.5.1 + Supervisor 2026.05.0
- extended_openai_conversation (jekalmin fork)
- LiteLLM → AWS Bedrock → Claude Opus 4.7
- M5Stack ATOM Echo voice satellite (ESP-IDF, micro_wake_word)
