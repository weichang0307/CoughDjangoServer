import pretty_midi
import numpy as np
from mido import MidiFile

class MelodySegment:
    def __init__(self, midi_file, duration=4, window_size=2, hop_size=1):
        self.midi_file = midi_file
        self.duration = duration
        self.window_size = window_size
        self.hop_size = hop_size
        self.features = self.extract_features()
    
    def extract_features(self):
        midi_data = pretty_midi.PrettyMIDI(self.midi_file)
        results = []

        for start_time in np.arange(0, self.duration - self.window_size + self.hop_size, self.hop_size):
            end_time = start_time + self.window_size
            notes_in_window = [note for instrument in midi_data.instruments for note in instrument.notes
                            if note.start < end_time and note.end > start_time]
            
            note_durations = [min(note.end, end_time) - max(note.start, start_time) for note in notes_in_window]
            note_density = int(len(notes_in_window))
            avg_duration = int(np.mean(note_durations)) if note_durations else 0
            duration_variability = int(np.std(note_durations)) if len(note_durations) > 1 else 0

            pitches = [note.pitch for note in notes_in_window]
            min_pitch = int(min(pitches)) if pitches else 0
            max_pitch = int(max(pitches)) if pitches else 0
            avg_pitch = int(np.mean(pitches)) if pitches else 0
            transition_rate = int(sum(abs(pitches[i + 1] - pitches[i]) for i in range(len(pitches) - 1))
                                / self.window_size) if len(pitches) > 1 else 0

            results.append({
                "min_pitch": min_pitch,
                "max_pitch": max_pitch,
                "avg_pitch": avg_pitch,
                "transition_rate": transition_rate,
                "note_density": note_density,
                "avg_duration": avg_duration,
                "duration_variability": duration_variability
            })
        return results
