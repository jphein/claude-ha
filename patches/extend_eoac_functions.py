#!/usr/bin/env python3
"""Patch the extended_openai_conversation Claude subentry to add read_file + query_history tools.

Operates on /config/.storage/core.config_entries. Must be run with HA core stopped
(otherwise HA writes back its in-memory state and overwrites this patch).

Usage:
    sudo python3 extend_eoac_functions.py [--entry-id ENTRY_ID] [--subentry-id SUBENTRY_ID]

If entry/subentry IDs are omitted, the script picks the first conversation subentry
under the first extended_openai_conversation entry it finds.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import yaml

STORAGE = Path("/config/.storage/core.config_entries")

EXTRA_TOOLS = [
    {
        "spec": {
            "name": "read_file",
            "description": (
                "Read a file from anywhere under /config (read-only). Use for inspecting "
                "automations.yaml, configuration.yaml, scripts.yaml, esphome configs, etc. "
                "Do NOT read /config/secrets.yaml or anything under /config/.storage/."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Absolute path beginning with /config, or path relative to "
                            "/config/extended_openai_conversation."
                        ),
                    }
                },
                "required": ["path"],
            },
        },
        "function": {
            "type": "read_file",
            "path": "{{ path }}",
            "allow_dir": ["/config"],
        },
    },
    {
        "spec": {
            "name": "query_history",
            "description": (
                "Run a SQLite SELECT on the Home Assistant recorder database. "
                "Useful tables: states (state_id, state, last_updated_ts, metadata_id), "
                "states_meta (metadata_id, entity_id). SELECT only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQLite SELECT statement"}
                },
                "required": ["query"],
            },
        },
        "function": {"type": "sqlite", "query": "{{ query }}"},
    },
]


def find_target(data: dict, entry_id: str | None, subentry_id: str | None) -> dict:
    """Locate the conversation subentry to patch."""
    for entry in data["data"]["entries"]:
        if entry.get("domain") != "extended_openai_conversation":
            continue
        if entry_id and entry.get("entry_id") != entry_id:
            continue
        for sub in entry.get("subentries", []):
            if sub.get("subentry_type") != "conversation":
                continue
            if subentry_id and sub.get("subentry_id") != subentry_id:
                continue
            return sub
    sys.exit("no extended_openai_conversation conversation subentry found")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry-id")
    ap.add_argument("--subentry-id")
    args = ap.parse_args()

    if os.geteuid() != 0:
        sys.exit("must run as root (sudo)")

    data = json.loads(STORAGE.read_text())
    sub = find_target(data, args.entry_id, args.subentry_id)

    existing = yaml.safe_load(sub["data"]["functions"]) or []
    existing_names = {t["spec"]["name"] for t in existing}
    added = []
    for tool in EXTRA_TOOLS:
        if tool["spec"]["name"] in existing_names:
            continue
        existing.append(tool)
        added.append(tool["spec"]["name"])

    if not added:
        print("no changes — tools already present:", sorted(existing_names))
        return

    sub["data"]["functions"] = yaml.dump(existing, sort_keys=False, default_flow_style=False)

    tmp = STORAGE.with_suffix(STORAGE.suffix + ".new")
    tmp.write_text(json.dumps(data, indent=4))
    os.replace(tmp, STORAGE)
    print(f"added: {added}")
    print(f"functions YAML now {len(sub['data']['functions'])} chars")


if __name__ == "__main__":
    main()
