# bad-dudes — ARCHIVED (merged)

**Status:** archived — merged into [`ttrpg-neuro-engine/src/bestiary/`](https://github.com/flehmenwtf/ttrpg-neuro-engine/tree/main/src/bestiary) on 2026-05-28.

This was the villain-bestiary content pipeline for Project Dracula's Muse — a scheduled Python tool that crawls villain wikis (default: villains.fandom.com), uses Mistral to extract character traits, and re-formats each villain across three campaign eras (Space Hate, Agis, Wicca Falls).

It now lives inside the TTRPG neuro-engine because the bestiary is a content source for the engine's Long-Term Memory, not an independent product.

## Where things went

| bad-dudes file | New location in ttrpg-neuro-engine |
|---|---|
| `app.py` | `src/bestiary/pipeline.py` |
| `config.yaml.example` | `src/bestiary/config.yaml.example` |
| `requirements.txt` | `src/bestiary/requirements.txt` |

Run from the new location: `python -m src.bestiary.pipeline` (after `pip install -r src/bestiary/requirements.txt`).

For everything else — architecture, the three-era schema, scheduling notes — see the ttrpg-neuro-engine `CLAUDE.md` under "Bestiary pipeline".
