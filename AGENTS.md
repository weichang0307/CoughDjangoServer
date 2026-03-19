# AGENTS.md

This file is for coding agents working in this repository.

## Maintenance Rule

Keep both `README.md` and `AGENTS.md` up to date whenever changes materially affect:

- architecture or dataflow
- setup or runtime requirements
- storage locations or source-of-truth assumptions
- background job behavior
- worker/subprocess contracts
- development or verification workflow

If your code change would make either document misleading, update the document in the same task.

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
- `CoughToMusic/co_create_utils.py`

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
- then filters the file through the subprocess worker boundary
- then classifies and clusters it
- then appends rows to `cough_table.csv`

Generation:

- `generate` converts request data into a `GenerateJob`
- jobs are queued in-process
- the runtime layer starts a daemon thread lazily on first generation use
- `GenerateJob.run()` delegates mode-specific generation to `CoughToMusic/services/generation_modes.py`

Finalize:

- `save_music` moves temp outputs into final folders and appends metadata
- `save_music_cocreate` finalizes co-create outputs

Readback:

- `get_coughs`, `get_music`, and `get_uploads_file` expose saved artifacts

## Key Paths

Per-user:

- `media/<user>/cough_audio/`
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
- mode-specific generation in `CoughToMusic/services/generation_modes.py`
- co-create generation helpers in `CoughToMusic/co_create_utils.py`

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
- confirm `cough_table.csv` reflects the intended row state
- confirm a failed filter request does not poison the next upload in the same Django process
- prefer request-level tests that fail once and then succeed on a second upload, ideally at the `run_cli(...)` seam if full worker execution is impractical in tests
- prefer startup probes that verify helper imports do not eagerly load the heavy audio stack or generation helpers

For generation changes:

- confirm queueing works
- confirm status polling still reports usable information
- confirm temp output is created
- confirm final save moves output into the expected permanent folder
- confirm runtime startup stays lazy until generation is first requested

For rename/delete changes:

- confirm file paths and CSV entries stay aligned

Be skeptical of existing tests:

- `CoughToMusic/tests.py` now includes request-level coverage for failed-then-successful upload behavior around the filter wrapper
- `test.py` appears stale

## Environment Notes

Current repo reality:

- `environment.yml` defines the main app environment
- `k_yamnet.yml` defines the worker environment
- `runserver.ps1` activates `env_itcough`
- `environment.yml` says `DjangoEnv2`
- `settings.py` hardcodes the worker interpreter path

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
