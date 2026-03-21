# CoughDjangoServer Diagrams

This file holds the human-oriented system diagrams that were previously embedded in `README.md`.

Use `README.md` for the concise operating model and repo guidance. Use this file when you want a visual map of the request flow and subsystem boundaries.

## System Diagram

```mermaid
flowchart TD
    client["Client App"]

    subgraph django["Django Request Layer"]
        urls["CoughToMusic/urls.py"]

        subgraph views["CoughToMusic/views/"]
            users_view["users.py\nsign_up\nget/set user info\nrecording/survey endpoints"]
            cough_view["cough.py\ncreate_cough_audio\nget_coughs"]
            gen_view["generation.py\ngenerate\ngenerate_status_view\nsave_music\nsave_music_cocreate"]
            library_view["library.py\nget_music\nget_uploads_file\nlibrary/statistics/public upload endpoints"]
        end

        users_service["services/users.py"]
        uploads_service["services/uploads.py"]
        generation_service["services/generation.py"]
        library_service["services/library.py"]
    end

    subgraph worker["Subprocess Worker Boundary"]
        util_helpers["util.py\nfilter_coughs\nclassify_cough_event\nclustering"]
        runner["utils/runner.py\nrun_cli"]
        yamnet["yamnet_worker/run_yamnet_worker.py\nfilter/classify/cluster"]
    end

    subgraph runtime["In-Memory Generation Runtime"]
        queue["runtime/generation_queue.py\nQueue plus lazy daemon thread"]
        job["task.py\nGenerateJob"]
        modes["services/generation_modes.py\nmode-specific generation"]
    end

    subgraph storage["Filesystem plus CSV State Under media/"]
        user_csv["media/{user}/{user}.csv\nuser metadata"]
        cough_audio["media/{user}/cough_audio/*.wav"]
        cough_csv["media/{user}/cough_audio/cough_table.csv"]
        public_cough["media/public_cough/*.wav"]
        temp_outputs["media/{user}/temp_*"]
        final_outputs["media/{user}/generated_*"]
        music_csv["media/{user}/generated_music/music_table.csv"]
    end

    client --> urls
    urls --> users_view
    urls --> cough_view
    urls --> gen_view
    urls --> library_view

    users_view --> users_service
    users_service --> user_csv

    cough_view --> uploads_service
    uploads_service --> cough_audio
    uploads_service --> util_helpers
    util_helpers --> runner
    runner --> yamnet
    yamnet --> runner
    runner --> util_helpers
    uploads_service --> cough_csv
    uploads_service --> public_cough

    gen_view --> generation_service
    generation_service --> queue
    queue --> job
    job --> modes
    modes --> temp_outputs
    gen_view --> queue
    generation_service --> final_outputs
    generation_service --> music_csv

    library_view --> library_service
    library_service --> final_outputs
    library_service --> cough_csv
    library_service --> music_csv
    library_service --> public_cough
```

Reading the diagram from top to bottom:

- the client talks only to Django endpoints
- routed endpoints now live directly in the modular `views/` modules, with shared filesystem and CSV logic extracted into `services/` where needed
- Django writes durable files and CSVs under `media/`
- filtering, classification, and clustering cross into a separate worker process
- generation is queued in memory and processed by a background runtime worker that starts lazily
- final outputs are moved from temp folders into permanent user folders

## YAMNet Worker Data Flow

```mermaid
flowchart TD
    upload["Client upload request"]
    view["views/cough.py\ncreate_cough_audio"]
    service["services/uploads.py\nprocess_cough_upload"]
    wav["media/{user}/cough_audio/{name}.wav"]

    subgraph django["Django process"]
        filter_call["util.py\nfilter_coughs\nmode=filter"]
        classify_call["util.py\nclassify_cough_event\nmode=classify"]
        cluster_call["util.py\nclustering\nmode=cluster"]
        cough_csv["media/{user}/cough_audio/cough_table.csv"]
        public_cough["media/public_cough/*.wav"]
        split_wavs["media/{user}/cough_audio/{name}_1.wav\nmedia/{user}/cough_audio/{name}_2.wav"]
        realtime["runtime enqueue\nrealtime mode only"]
    end

    subgraph worker["YAMNet worker subprocess"]
        entry["run_yamnet_worker.py"]
        loader["yamnet_loader.py\nload yamnet.h5 once per worker process"]
        filter_mode["filter_core.py\nread wav -> detect cough -> rewrite wav"]
        classify_mode["cough_cluster_core.py\nextract features -> classify user/non-user"]
        cluster_mode["cough_cluster_core.py\nextract features -> assign cluster_id"]
    end

    upload --> view --> service --> wav
    service --> filter_call --> entry
    entry --> loader
    entry --> filter_mode
    filter_mode --> wav

    service --> classify_call --> entry
    entry --> classify_mode
    classify_mode --> split_wavs

    service --> cluster_call --> entry
    entry --> cluster_mode

    classify_mode -. JSON flags and separated arrays .-> service
    cluster_mode -. JSON cluster_id .-> service
    filter_mode -. JSON segment metadata .-> service

    service --> cough_csv
    service --> public_cough
    service --> realtime
```

## Co-Create Dataflow

```mermaid
flowchart TD
    client["Client"]
    generate_view["views/generation.py<br/>generate"]
    gen_service["services/generation.py<br/>enqueue_generation_request"]
    queue["runtime/generation_queue.py<br/>lazy in-memory queue"]
    job["task.py<br/>GenerateJob.run"]
    modes["services/generation_modes.py<br/>trio / trio_manual / drum / drum_manual"]
    workflows["cocreate/workflows.py<br/>active orchestration"]
    storage["cocreate/storage.py<br/>paths + CSV lookup"]

    subgraph cocreate["CoughToMusic/cocreate/lib"]
        cough2mid["cough2mid.py<br/>cough WAV -> motif MIDI"]
        melody["generation.py<br/>MusicVAE interpolation"]
        drum["drum.py<br/>cough ranking -> drum MIDI"]
        midi["midi.py<br/>normalize/render MIDI -> WAV"]
    end

    subgraph inputs["Read-side inputs"]
        user_wavs["media/{user}/cough_audio/*.wav"]
        cough_csv["media/{user}/cough_audio/cough_table.csv"]
        public_cough["media/public_cough/*.wav"]
        public_motifs["media/public_motif/* and related public motif dirs"]
        models["CoughToMusic/cocreate/model/*"]
        soundfonts["CoughToMusic/cocreate/soundfonts/*"]
    end

    subgraph temp["Temp outputs"]
        temp_trio["media/{user}/temp_trio"]
        temp_manual_trio["media/{user}/temp_manual_trio"]
        temp_manual_drum["media/{user}/temp_manual_drum"]
        temp_autofill_drum["media/{user}/temp_autofill_drum"]
    end

    status["views/generation.py<br/>generate_status_view"]
    save_view["views/generation.py<br/>save_music"]
    save_service["services/generation.py<br/>save_music_result"]
    move["util.py<br/>save_music_move"]

    subgraph final["Finalized outputs"]
        gen_trio["media/{user}/generated_trio"]
        gen_manual_trio["media/{user}/generated_manual_trio"]
        gen_manual_drum["media/{user}/generated_manual_drum"]
        gen_auto_drum["media/{user}/generated_autofill_drum"]
        music_csv["media/{user}/generated_music/music_table.csv"]
    end

    legacy["views/generation.py<br/>save_music_cocreate (compatibility)"]
    cocreate_save["services/generation.py<br/>save_cocreate_result"]
    cocreate_finalize["cocreate/finalize.py<br/>finalize_cocreate_result"]

    client --> generate_view --> gen_service --> queue --> job --> modes --> workflows
    gen_service --> user_wavs
    workflows --> storage
    workflows --> cough_csv
    workflows --> user_wavs
    workflows --> public_cough
    workflows --> public_motifs
    workflows --> cough2mid
    workflows --> melody
    workflows --> drum
    cough2mid --> midi
    melody --> midi
    drum --> midi
    melody --> models
    midi --> soundfonts

    workflows --> temp_trio
    workflows --> temp_manual_trio
    workflows --> temp_manual_drum
    workflows --> temp_autofill_drum

    client --> status
    status --> queue

    client --> save_view --> save_service --> move
    move --> temp_trio
    move --> temp_manual_trio
    move --> temp_manual_drum
    move --> temp_autofill_drum
    move --> gen_trio
    move --> gen_manual_trio
    move --> gen_manual_drum
    move --> gen_auto_drum
    move --> music_csv

    client -. compatibility endpoint .-> legacy
    legacy -. same active finalize contract .-> cocreate_save --> cocreate_finalize
    cocreate_finalize --> gen_trio
    cocreate_finalize --> gen_manual_trio
    cocreate_finalize --> gen_manual_drum
    cocreate_finalize --> gen_auto_drum
    cocreate_finalize --> music_csv
```
