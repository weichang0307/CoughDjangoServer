# Archive

This folder holds retired code that is intentionally preserved for reference but is not part of the active runtime path.

## Archive Policy

- Move retired files here once live imports, URL routes, worker entrypoints, and tests no longer depend on them.
- For retired functions inside otherwise-active files, prefer deleting them. If the old implementation needs to be preserved, move it into an archived module here and log that move.
- Each archived item should record what replaced it and why the active tree no longer needs it.
- Do not treat archived code as part of the current architecture in `README.md` or `AGENTS.md`.

## Decision Log

### 2026-03-21: Archive `CoughToMusic/co_create_utils.py`

- Archived path: `archive/CoughToMusic/co_create_utils.py`
- Previous role: legacy co-create compatibility helpers, including the old `save_final_cocreate(...)` finalize path tied to the `temp_cocreate` / `generated_music_cocreate` layout
- Why retired:
  - active co-create generation already runs through `CoughToMusic/services/generation_modes.py`
  - active co-create orchestration already lives in `CoughToMusic/cocreate/workflows.py`
  - active co-create finalization already goes through `CoughToMusic/services/generation.py` into `CoughToMusic/cocreate/finalize.py`
  - current routed views no longer import `co_create_utils.py`
- Risks checked before archiving:
  - no active URL path imports it
  - no active view path calls `save_final_cocreate(...)`
  - remaining test coverage for the deprecated warning was removed because it only exercised the retired module
- Follow-up repo changes made in the same task:
  - removed the obsolete `test_legacy_save_final_cocreate_emits_warning`
  - updated `README.md` and `AGENTS.md` to require archiving and logging retired files/functions

### 2026-03-21: Archive `test.py`

- Archived path: `archive/test.py`
- Previous role: ad hoc manual integration script for an old `generate_trio` HTTP endpoint
- Why retired:
  - it targeted `http://127.0.0.1:8000/generate_trio/`, which is not part of the current routed API
  - it was not part of the automated Django test suite
  - keeping it at repo root made it look more current than it is
- Risks checked before archiving:
  - no active imports or test runners depended on it

### 2026-03-21: Archive `CoughToMusic/cocreate/lib/trio_drum.py`

- Archived path: `archive/CoughToMusic/cocreate/lib/trio_drum.py`
- Previous role: older standalone co-create pipeline script
- Why retired:
  - it has no callers in the current repo
  - active co-create orchestration now lives in `CoughToMusic/cocreate/workflows.py`
  - active lower-level co-create work already routes through the current `cocreate/lib/` modules that `workflows.py` imports directly
- Risks checked before archiving:
  - repo-wide search found no live imports or references

### 2026-03-21: Archive `CoughToMusic/audio.py`

- Archived path: `archive/CoughToMusic/audio.py`
- Previous role: old audio metadata wrapper classes
- Why retired:
  - the module has no callers in the current repo
  - the active request/runtime path does not construct these wrapper classes
  - keeping it in the active package suggested a supported abstraction that is no longer used
- Risks checked before archiving:
  - repo-wide search found no live imports or references
