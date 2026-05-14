# Voice Assistant Workspace

Working directory for Claude's `bash` tool (extended_openai_conversation HACS integration).

## Tools available to the assistant
- `execute_services` — call any Home Assistant service
- `get_attributes` — read entity state and attributes
- `load_skill` — read files from `skills/` subdir
- `bash` — execute shell inside HA core container, starting in this dir

## Useful paths from bash
- /config/automations.yaml      - automations
- /config/scripts.yaml          - scripts
- /config/configuration.yaml    - top-level HA config
- /config/esphome/              - ESPHome device YAMLs
- /config/custom_components/    - HACS integrations
- /config/secrets.yaml          - DO NOT print verbatim
- /config/.storage/             - HA-managed; avoid writing here

## Safety notes
- Never quote /config/secrets.yaml or /config/.storage/* contents back to the user
- Before editing automations.yaml or configuration.yaml: back up to ./backups/
- Validate YAML before saving:
    python3 -c 'import yaml,sys; yaml.safe_load(open(sys.argv[1]))' path/to/file.yaml
- Use `ha core check` or `ha core restart` only when explicitly asked
