# Tools

Per-tool reference. Each tool's underlying implementation lives in [`extended_openai_conversation/functions/`](https://github.com/jekalmin/extended_openai_conversation/tree/main/custom_components/extended_openai_conversation/functions).

## execute_services

Call any Home Assistant service. The model picks `domain.service` + `service_data` and HA dispatches it.

**Example prompts:**
- "Turn on the kitchen lights"
- "Set the bedroom thermostat to 70"
- "Run my morning script"
- "Restart the matterbridge addon"

Anything available under Developer Tools → Services is reachable.

## get_attributes

Read state + attributes of any entity. Template-based — calls `state_attr` under the hood.

**Example prompts:**
- "What's the temperature in the living room?"
- "Is the front door locked?"

## load_skill

Load a markdown file from `/config/extended_openai_conversation/skills/<name>/<file>`. Used by the integration's "skills" feature for multi-file capability bundles.

## bash *(workspace-scoped)*

Execute shell commands. By default `cwd = /config/extended_openai_conversation/` and `restrict_to_workspace = true`, which blocks paths that resolve outside the workspace.

**Example prompts:**
- "Save a quick note about the laundry running to scratch.md"
- "List my saved notes"

To allow broader access in a specific call, pass `restrict_to_workspace: false` (the integration supports this per-call). Use sparingly — that's why this repo adds `read_file` as a structured alternative.

## read_file *(added by this repo)*

Read a file anywhere under `/config`. Configured with `allow_dir: ["/config"]`.

**Example prompts:**
- "Read configuration.yaml and tell me what integrations are loaded"
- "Show me the contents of automations.yaml"

**Safety note:** The system prompt instructs Claude to avoid `/config/secrets.yaml` and `/config/.storage/*`. This is a model-side guardrail, not a filesystem permission.

## query_history *(added by this repo)*

Run a SQLite SELECT against HA's recorder database. The function rejects non-SELECT verbs.

Key tables:
- `states` — `state_id`, `state`, `last_updated_ts` (Unix epoch float), `metadata_id`
- `states_meta` — `metadata_id`, `entity_id`

**Example prompts:**
- "When did the front door last open?"
- "How many times did the doorbell ring yesterday?"
- "What was the bedroom temperature at 3 AM?"

**Joining states + states_meta:**
```sql
SELECT s.state, datetime(s.last_updated_ts, 'unixepoch') AS ts
FROM states s
JOIN states_meta m ON s.metadata_id = m.metadata_id
WHERE m.entity_id = 'binary_sensor.front_door'
  AND s.state = 'on'
ORDER BY s.last_updated_ts DESC
LIMIT 1;
```

Claude knows this pattern from the tool description.
