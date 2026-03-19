# CoughDjangoServer

`CoughDjangoServer` is a Django backend for recording cough audio, analyzing it, and generating music artifacts from those coughs.

This repo looks like a normal Django project, but the important application state is mostly stored on disk under `media/`, not in `db.sqlite3`.

## Documentation Maintenance

Keep this `README.md` up to date when changes materially affect:

- project purpose or scope
- request/dataflow
- storage model
- runtime setup
- generation modes
- operational caveats

If you change the repo in a way that would mislead a new contributor reading this file, update this file in the same task.

## What It Does

- accepts cough audio uploads from a client
- stores per-user recordings and metadata
- filters, classifies, and clusters cough events
- generates music from cough inputs in several modes
- serves cough and music files back to the client

## High-Level Architecture

Main Django project:

- `CoughToMusicDjango/settings.py`
- `CoughToMusicDjango/urls.py`

Main app:

- `CoughToMusic/urls.py`
- `CoughToMusic/views.py`
- `CoughToMusic/util.py`
- `CoughToMusic/task.py`
- `CoughToMusic/table.py`
- `CoughToMusic/co_create_utils.py`

Worker boundary:

- `CoughToMusic/utils/runner.py`
- `CoughToMusic/yamnet_worker/run_yamnet_worker.py`

## Dataflow

The main flow is:

1. A client calls `sign_up` to initialize the user folder and CSV files.
2. A client uploads cough audio through `create_cough_audio`.
3. The server writes the uploaded audio to `media/<user>/cough_audio/<name>.wav`.
4. The server filters the cough audio.
5. The server runs cough classification and clustering.
6. The server appends metadata to `cough_table.csv`.
7. If music generation is requested, the server enqueues a background `GenerateJob`.
8. The background worker writes temporary generated outputs under the user folder.
9. The client polls `generate_status_view`.
10. The client finalizes output through `save_music` or `save_music_cocreate`.

Mental model:

- HTTP endpoints orchestrate the workflow.
- WAV files and CSV files are the durable state.
- in-memory Python objects track transient generation jobs.
- a subprocess worker handles YAMNet-based classification and clustering.

## System Diagram

```text
+------------------+
|    Client App    |
+------------------+
          |
          v
+-------------------------------------------+
| Django endpoints                          |
| CoughToMusic/views.py                     |
+-------------------------------------------+
   |                |                  |
   |                |                  |
   v                v                  v
+----------+   +----------------+   +----------------------+
| sign_up  |   | create_cough_  |   | get_coughs /         |
|          |   | audio          |   | get_music /          |
+----------+   +----------------+   | get_uploads_file     |
   |                |               +----------------------+
   v                v
+----------------+  +--------------------------------------+
| create user    |  | save WAV                             |
| folders + CSVs |  | media/<user>/cough_audio/           |
+----------------+  +--------------------------------------+
                           |
                           v
                  +----------------------+
                  | filter cough audio   |
                  +----------------------+
                           |
                           v
                  +----------------------+
                  | YAMNet subprocess     |
                  | classify + cluster    |
                  +----------------------+
                      |              |
                      |              |
                      v              v
          +--------------------+   +----------------------+
          | append cough row   |   | optional public      |
          | cough_table.csv    |   | write public_cough/  |
          +--------------------+   +----------------------+
                      |
                      v
             +------------------+
             | generate         |
             +------------------+
                      |
                      v
             +------------------+
             | in-memory queue  |
             +------------------+
                      |
                      v
             +------------------+
             | worker thread    |
             +------------------+
                      |
                      v
             +------------------+
             | GenerateJob      |
             +------------------+
                      |
                      v
             +------------------------------+
             | temp outputs                 |
             | temp_music / temp_trio / ... |
             +------------------------------+
                      |
          +-----------+-----------+
          |                       |
          v                       v
+----------------------+   +----------------------+
| generate_status_view |   | save_music /         |
| reads in-memory job  |   | save_music_cocreate  |
| state                |   +----------------------+
+----------------------+              |
                                      v
                          +------------------------------+
                          | final saved outputs          |
                          | generated_music /            |
                          | generated_trio / generated_* |
                          +------------------------------+
                                      |
                                      v
                          +------------------------------+
                          | append music metadata        |
                          | music_table.csv              |
                          +------------------------------+
```

Reading the diagram from top to bottom:

- the client talks only to Django endpoints
- Django writes durable files and CSVs under `media/`
- classification and clustering cross into a separate worker process
- generation is queued in memory and processed by a background thread
- final outputs are moved from temp folders into permanent user folders

## Request Flow By Area

User setup:

- `sign_up` creates user directories and initializes CSV tables.

Upload and analysis:

- `create_cough_audio` saves the audio file early.
- It then filters the saved file.
- It calls helper code that classifies cough ownership and computes clustering.
- It may also publish audio into shared public folders.

Generation:

- `generate` normalizes the requested mode and creates a `GenerateJob`.
- A background thread consumes jobs from an in-process queue.
- Mode-specific generation is implemented in `CoughToMusic/task.py` and `CoughToMusic/co_create_utils.py`.

Readback:

- `get_coughs`, `get_music`, and `get_uploads_file` expose saved artifacts and metadata back to the client.

Finalize:

- `save_music` moves temp outputs into permanent per-user folders and appends music metadata.

## Storage Model

This project is primarily filesystem-backed.

Durable state:

- user folders under `media/<user>/`
- user CSV files such as `<user>.csv`, `cough_table.csv`, and `music_table.csv`
- saved WAV and MIDI artifacts
- shared public assets under `media/public_*`

Not durable:

- queued jobs in memory
- processing/completed job lists in memory

Important implication:

- restarting Django loses job state, but not the files already written to disk

## Important Directories

Shared directories created from settings:

- `media/public_cough/`
- `media/public_music/`
- `media/public_motif/`
- `media/import_cough/`

Common per-user directories:

- `media/<user>/cough_audio/`
- `media/<user>/cough_template/`
- `media/<user>/generated_music/`
- `media/<user>/generated_midi/`
- `media/<user>/generated_trio/`
- `media/<user>/generated_autofill_drum/`
- `media/<user>/generated_manual_trio/`
- `media/<user>/generated_manual_drum/`
- temporary folders such as `temp_music`, `temp_trio`, `temp_manual_trio`, and `temp_autofill_drum`

## Database Reality

`db.sqlite3` exists because this is a Django project, but the main cough-to-music flow does not use the ORM as its primary data store.

In practice:

- Django database tables are mostly framework scaffolding
- the core product state lives in files and CSVs

The model in `CoughToMusic/models.py` is not central to the main runtime flow.

## Running The Project

Standard Django entrypoint:

```powershell
python manage.py runserver
```

Repo helper:

```powershell
.\runserver.ps1
```

## Environment Requirements

This repo appears to depend on two Python environments:

- main Django app environment from `environment.yml`
- YAMNet worker environment from `k_yamnet.yml`

Important caveats:

- `runserver.ps1` activates `env_itcough`
- `environment.yml` declares an environment named `DjangoEnv2`
- `CoughToMusicDjango/settings.py` hardcodes `YAMNET_PYTHON_EXE`

That means environment setup is machine-specific and should be verified locally before assuming the project is portable as-is.

## Background Job Model

Generation is asynchronous, but simple:

- an in-process `Queue` stores jobs
- one daemon thread consumes them
- job status is kept in memory
- process restarts lose job metadata

This is not a durable queue system like Celery.

## Failure Behavior

The upload and generation flows are not transactional.

Practical consequences:

- if upload processing fails after the WAV is written, the file may remain on disk
- if a later metadata step fails, CSV state can diverge from saved files
- fake cough handling explicitly deletes files in some cases
- generation failures usually do not delete the original uploaded cough file

There is no built-in backup system for uploaded inputs.

## Verification Reality

Automated coverage is minimal.

- `CoughToMusic/tests.py` is a stub
- `test.py` appears stale and references an endpoint that is not currently routed

For most changes, real verification means exercising the relevant HTTP endpoints and inspecting the resulting files and CSV rows.

## Practical Advice For Contributors

- treat `media/` as the real application datastore
- inspect both file writes and CSV writes when changing behavior
- be careful with path changes and filename conventions
- keep the Django-to-worker subprocess contract stable unless you are intentionally redesigning it
- verify both the API response and the saved artifact path for generation changes
