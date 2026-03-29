# AGENTS.md

This file is for coding agents working in this repository.

## Maintenance Rule

Keep `README.md`, `AGENTS.md`, and `archive/ARCHIVE.md` up to date whenever changes materially affect:

- architecture or dataflow
- setup or runtime requirements
- storage locations or source-of-truth assumptions
- background job behavior
- worker/subprocess contracts
- development or verification workflow
- archived or retired code paths

If your code change would make any of those documents misleading, update them in the same task.

If a file or function is retired:

- move retired files into `archive/` when practical instead of leaving dead code in the active tree
- record the decision in `archive/ARCHIVE.md`
- update references in tests and docs so the active architecture description stays accurate

Treat `README.md` as the default concise repo guide for routine agent work. `DIAGRAMS.md` is a human-oriented companion for visual architecture and dataflow diagrams, so agents usually do not need to read or update it unless a change materially affects structure, subsystem boundaries, or the documented request/dataflow.

## Mission

Maintain and extend a Django backend that records cough audio, analyzes it, and generates music artifacts.

Do not treat this like a typical ORM-centered Django app. For most meaningful flows, the real state is the filesystem plus CSV metadata under `media/`.

## Read These Files First

Core request flow:

- `CoughToMusic/views/`
- `CoughToMusic/services/`
- `CoughToMusic/runtime/`
- `CoughToMusic/urls.py`
- `CoughToMusicDjango/urls.py`

Core helpers:

- `CoughToMusic/util.py`
- `CoughToMusic/table.py`
- `CoughToMusic/task.py`
- `CoughToMusic/cocreate/contracts.py`
- `CoughToMusic/cocreate/storage.py`
- `CoughToMusic/cocreate/workflows.py`
- `CoughToMusic/cocreate/trio_workflows.py`
- `CoughToMusic/cocreate/drum_workflows.py`
- `CoughToMusic/cocreate/trio_adapters.py`
- `CoughToMusic/cocreate/drum_adapters.py`

Runtime settings:

- `CoughToMusicDjango/settings.py`

Worker boundary:

- `CoughToMusic/utils/runner.py`
- `CoughToMusic/yamnet_worker/run_yamnet_worker.py`

## Source Of Truth

Use this model when reasoning about changes:

- filesystem and CSV files: durable application state
- in-memory Python objects: transient queue state
- `db.sqlite3`: mostly incidental Django scaffolding

Do not assume the ORM is authoritative for users, coughs, music, or jobs.

## Core Flows

User initialization:

- `sign_up` creates user directories and CSV files

Upload and analysis:

- `create_cough_audio` writes the uploaded WAV early
- `util.is_blank(...)` then runs against the saved WAV on the shared 4-second analysis window and treats uploads as blank when they cannot produce usable onset-plus-pitch MIDI material
- `util.is_blank(...)` now reads WAVs through a lightweight stdlib loader first and only then touches the heavier onset/pitch stack
- blank uploads are deleted immediately and skip the later upload-analysis flow
- `CoughToMusic/windowing.py` owns the shared 4-second window-selection rule used by `util.is_blank(...)`, `cough2midi(...)`, and drum analysis/render helpers in `CoughToMusic/cocreate/lib/drum.py`
- then classifies and clusters it
- split `_1.wav` and `_2.wav` classification artifacts are validated right before their own active CSV/public writes
- the main upload may be copied directly into `media/public_cough/` when publishable
- then appends rows to `cough_table.csv`

Generation:

- `generate` converts request data into a `GenerateJob`
- jobs are queued in-process
- the runtime layer starts a daemon thread lazily on first generation use
- `GenerateJob.run()` delegates mode-specific generation to `CoughToMusic/services/generation_modes.py`, which dispatches co-create modes through the stable facade in `CoughToMusic/cocreate/workflows.py`
- manual/autofill drum generation still prefers GrooVAE interpolation, but if staged drum MIDI cannot be tensorized for interpolation the adapter falls back to concatenating eight cumulative 2-bar motif stages instead of failing the request

Finalize:

- `save_music` moves temp outputs into final folders and appends metadata
- `save_music_cocreate` is compatibility-only and now delegates to the same active finalize contract as `save_music`

Readback:

- `get_coughs`, `get_music`, and `get_uploads_file` expose saved artifacts
- user/library routed endpoints now live directly in `CoughToMusic/views/users.py` and `CoughToMusic/views/library.py`, with shared CSV/file helpers in `CoughToMusic/services/users.py` and `CoughToMusic/services/library.py`
- blank existing cough archival is handled in `CoughToMusic/services/library.py`, which moves user/public WAVs out of active folders and preserves archived rows in a separate archive CSV

## Key Paths

Per-user:

- `media/<user>/cough_audio/`
- `media/<user>/cough_audio/archive/`
- `media/<user>/cough_audio/archive/cough_table.csv`
- `media/<user>/cough_template/`
- `media/<user>/generated_music/`
- `media/<user>/generated_midi/`
- `media/<user>/generated_trio/`
- `media/<user>/generated_autofill_drum/`
- `media/<user>/generated_manual_trio/`
- `media/<user>/generated_manual_drum/`

Shared:

- `media/public_cough/`
- `media/public_music/`
- `media/public_motif/`
- `media/import_cough/`
- `media/archive/public_cough/`

Active cough rows stay in `media/<user>/cough_audio/cough_table.csv`; archived blank cough rows are preserved in `media/<user>/cough_audio/archive/cough_table.csv`.

Temporary:

- `media/<user>/temp_music/`
- `media/<user>/temp_midi/`
- `media/<user>/temp_trio/`
- `media/<user>/temp_manual_trio/`
- `media/<user>/temp_manual_drum/`
- `media/<user>/temp_autofill_drum/`

## Queue Constraints

This project does not use a durable job runner.

Current behavior:

- queue is an in-process `Queue` owned by the runtime layer
- worker count is effectively one thread
- job status is tracked in Python lists and dicts
- a server restart drops queued and completed job state

Implications for agents:

- avoid assuming multi-process coordination
- be careful with import-time side effects
- keep status/reporting changes compatible with in-memory state

## Worker Boundary

Filtering, classification, and clustering cross a subprocess boundary.

Important facts:

- `util.py` calls `run_cli(...)` for the worker-backed filter/classify/cluster helpers
- `run_cli` launches a separate Python interpreter
- the worker script is `CoughToMusic/yamnet_worker/run_yamnet_worker.py`
- `YAMNET_PYTHON_EXE` is hardcoded in `settings.py`

Do not casually collapse this worker into Django. If you change the payload contract, update both sides.

## Common Failure Modes

- WAV file written, later step fails, CSV not updated
- blank existing cough moved, but archive CSV/public counterpart not updated consistently
- CSV updated, related file missing or renamed incorrectly
- temp generation output exists, finalize step never ran
- public asset folder assumptions break on a new machine
- queue state disappears after a restart
- absolute Windows paths break portability

This code has little transactional protection. Preserve current flow unless the task explicitly asks for a reliability redesign.

## Safe Edit Areas

Usually safe when scoped and verified:

- response shaping in `CoughToMusic/views/`
- CSV field handling in `CoughToMusic/table.py`
- orchestration helpers in `CoughToMusic/services/`
- runtime lifecycle helpers in `CoughToMusic/runtime/`
- path and save/move rules in `CoughToMusic/util.py`
- cocreate application-layer helpers in `CoughToMusic/cocreate/storage.py`, `CoughToMusic/cocreate/workflows.py`, `CoughToMusic/cocreate/trio_workflows.py`, `CoughToMusic/cocreate/drum_workflows.py`, `CoughToMusic/cocreate/trio_adapters.py`, and `CoughToMusic/cocreate/drum_adapters.py`
- mode-specific generation in `CoughToMusic/services/generation_modes.py`
- archival documentation and retired-code moves under `archive/`

Higher risk:

- `create_cough_audio`
- `save_music_move`
- queue startup and lifecycle in `CoughToMusic/runtime/`
- subprocess bridge in `util.py` and `utils/runner.py`
- path definitions in `settings.py`

## Before Editing

Before changing any flow, answer these questions:

1. Which files are written?
2. Which CSV rows are expected to exist afterward?
3. Does the flow touch any public asset directories?
4. Does the flow cross the YAMNet subprocess boundary?
5. Is the output temporary or finalized?

If you cannot answer those quickly, read the relevant path through the controller layer, `util.py`, and `table.py` first.

## Verification Expectations

Prefer flow-level checks over isolated unit assumptions.

For upload changes:

- confirm the WAV lands in the expected user folder
- confirm blank uploads are deleted before classify/cluster/public-copy work begins
- confirm `cough_table.csv` reflects the intended row state
- confirm classification or clustering failures do not leave active CSV/public state behind unexpectedly
- prefer startup probes that verify helper imports do not eagerly load the heavy audio stack or generation helpers

For generation changes:

- confirm queueing works
- confirm status polling still reports usable information
- confirm temp output is created
- confirm final save moves output into the expected permanent folder
- confirm MIDI-to-WAV rendering raises clearly if FluidSynth fails or no WAV is produced
- confirm runtime startup stays lazy until generation is first requested

For rename/delete changes:

- confirm file paths and CSV entries stay aligned

For blank-cough archival changes:

- confirm the user WAV leaves `media/<user>/cough_audio/`
- confirm the matching public WAV leaves `media/public_cough/` when `pubCoughID` is live
- confirm the active `cough_table.csv` row is removed
- confirm the archived row is preserved in `media/<user>/cough_audio/archive/cough_table.csv`
- confirm future public cough IDs do not reuse archived IDs

Be skeptical of existing tests:

- `CoughToMusic/tests/` now splits coverage by domain so upload, user view, library view, generation runtime, co-create, and import-safety tests can be run independently
- `CoughToMusic/tests/test_uploads.py` covers blank-upload short-circuit behavior, public-copy/source-of-truth handling, split-artifact blank suppression, and shared analysis-window integration points
- `CoughToMusic/tests/test_library_views.py` covers the migrated modular library endpoints, including CSV update behavior, file streaming, rename/delete alignment, shared public upload writes, and the CSRF regression probe
- `CoughToMusic/tests/test_user_views.py` covers the migrated modular user endpoints
- `CoughToMusic/tests/test_cocreate_refactor.py` covers the stable cocreate public surface, including package exports, `CoCreateResult` payload shape, generation mode dispatch, workflow-to-adapter delegation, and path resolution
- the split test modules still use repo-local `media/test_media_<uuid>/` scratch directories because Python `tempfile` directories were not writable for nested paths under the Windows Django test process in this workspace
- `CoughToMusic/tests/test_import_safety.py` includes the import-safety probes for `CoughToMusic.util`, `CoughToMusic.task`, `CoughToMusic.cocreate`, the split cocreate workflow/adapter modules, `CoughToMusic.cocreate.workflows`, and `CoughToMusic.views`
- when adding new cocreate helper modules, extend `test_import_safety.py` if those modules are intended to stay import-light
- `CoughToMusic/tests/support.py` is the shared source for temp media setup, CSV schema constants, common row/payload builders, and file/CSV assertion helpers; prefer extending it over duplicating test fixture dicts
- stale ad hoc scripts and orphaned modules are archive candidates once confirmed to have no live callers

## Archive Policy

Use `archive/` for retired code that is intentionally preserved for reference.

- `archive/ARCHIVE.md` is the source of truth for why code was retired and what replaced it
- archive code only after confirming there are no live imports, URLs, or worker paths that still rely on it
- when retiring a function inside an otherwise-active file, prefer deleting it; if the old implementation needs to be preserved, move that implementation into an archived module and log it
- do not describe archived code as part of the active request path

## Environment Notes

Current repo reality:

- `environment.yml` defines the main app environment
- `k_yamnet.yml` defines the worker environment
- `environment.yml` says `DjangoEnv2`
- `settings.py` hardcodes the worker interpreter path as `C:\ProgramData\anaconda3\envs\k_yamnet\python.exe`
- `runserver.ps1` launches `manage.py runserver` with `C:\ProgramData\anaconda3\envs\DjangoEnv2\python.exe`
- on this machine, bare `python` may resolve to a `pyenv` shim and `conda` may not be on `PATH`
- for reliable local verification, prefer direct interpreter invocations such as `C:\ProgramData\anaconda3\envs\DjangoEnv2\python.exe manage.py test CoughToMusic.tests`
- for narrower local runs, target the split modules directly, for example `... manage.py test CoughToMusic.tests.test_uploads CoughToMusic.tests.test_library_views`

Do not "clean this up" as a side effect of another task unless requested.

## Agent Working Style

- prefer small, surgical changes
- keep path conventions stable
- do not silently migrate storage from CSV/filesystem to database
- if you change filename or directory layout, update all readers and writers in the same flow
- mention verification gaps explicitly if you could not run full end-to-end generation

## If You Need A Quick Mental Model

Think of the app as:

- Django endpoints as orchestration
- `media/` as the datastore
- CSV files as metadata tables
- background generation as a local queue
- runtime helpers as the owner of lazy queue startup and in-memory job state
- YAMNet analysis as a subprocess service
- heavy audio and generation dependencies should stay lazily imported where practical so lightweight endpoints and tests are not blocked by module-load cost
- Django and the YAMNet worker set `NUMBA_CACHE_DIR` to `BASE_DIR/.numba_cache` before heavy audio imports so fresh-process `librosa` imports do not depend on the shared temp directory
- `.numba_cache/` is a repo-local generated runtime artifact and must be writable by the Django and worker interpreters
- one-time blank-cleanup runs may still emit noisy `crepe`/TensorFlow/librosa logs; rely on the per-file command logs for progress when debugging cleanup behavior
