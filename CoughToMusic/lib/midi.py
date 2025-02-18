import magenta.music as mm
from magenta.models.music_vae import TrainedModel, configs
import pretty_midi
import mido
from mido import MidiFile, MidiTrack, MetaMessage, Message

def get_tempo(midi_path):
    # Get the tempo of the midi file
    md = MidiFile(midi_path)

    for msg in md:
        if msg.type == 'set_tempo':
            return round(60000000 / msg.tempo)
        
        
def path_to_note_seq(midi_path_start, midi_path_end):
    print('Converting to NoteSequence...', end='')
    start_pm = pretty_midi.PrettyMIDI(midi_path_start)
    end_pm = pretty_midi.PrettyMIDI(midi_path_end)
    start_note_seq = mm.midi_to_note_sequence(start_pm)
    end_note_seq = mm.midi_to_note_sequence(end_pm)
    
    print('Done')
    return start_note_seq, end_note_seq

def note_seq_to_tensor(start_note_seq, end_note_seq):
    config_name = 'cat-mel_2bar_big'

    print('Converting to tensors...')
    start_tensors = configs.CONFIG_MAP[config_name].data_converter.from_tensors(
        configs.CONFIG_MAP[config_name].data_converter.to_tensors(start_note_seq)[1])
    print('start_tensors:', start_tensors)
    end_tensors = configs.CONFIG_MAP[config_name].data_converter.from_tensors(
        configs.CONFIG_MAP[config_name].data_converter.to_tensors(end_note_seq)[1])
    print(type(end_tensors[0]))
    
    tensors = start_tensors + end_tensors

    return tensors


def adjust_bpm(midi, target_bpm):
    """調整 MIDI 檔案的 BPM"""
    tempo = mido.bpm2tempo(target_bpm)
    new_midi = MidiFile(ticks_per_beat=220)
    for track in midi.tracks:
        new_track = MidiTrack()
        new_midi.tracks.append(new_track)
        for msg in track:
            if msg.type == 'set_tempo':
                new_track.append(MetaMessage('set_tempo', tempo=tempo))
            else:
                new_track.append(msg)
    return new_midi

from mido import MidiFile, MidiTrack

def concat_midi_files(mids):
    combined_midi = MidiFile(ticks_per_beat=220)

    for mid in mids:
        for track in mid.tracks:
            combined_midi.tracks.append(track)

    return combined_midi


def calculate_measures(mid):
    """計算 MIDI 檔案的小節數和 tempo"""
    tempo = mido.bpm2tempo(120)  # 預設 120 BPM，如果 MIDI 中有 tempo 事件，應該使用該值
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                tempo = msg.tempo
                break
    
    ticks_per_beat = mid.ticks_per_beat
    total_ticks = sum(msg.time for track in mid.tracks for msg in track)
    total_seconds = mido.tick2second(total_ticks, ticks_per_beat, tempo)
    beats_per_minute = mido.tempo2bpm(tempo)
    total_beats = total_seconds / (60 / beats_per_minute)
    bar_num = total_beats / 4  # 在 4/4 情況下，每個小節有 4 拍

    return bar_num, tempo
            
def adjust_ticks_per_beat(mid, new_ticks_per_beat=220):
    original_ticks_per_beat = mid.ticks_per_beat

    # 計算時間調整因子
    time_adjustment_factor = original_ticks_per_beat / new_ticks_per_beat

    new_mid = MidiFile(ticks_per_beat=new_ticks_per_beat)
    for track in mid.tracks:
        new_track = MidiTrack()
        new_mid.tracks.append(new_track)
        for msg in track:
            # 調整消息時間
            adjusted_time = int(msg.time / time_adjustment_factor)
            new_msg = msg.copy(time=adjusted_time)
            new_track.append(new_msg)

    return new_mid

def to_2bars(ori_midi_path, preprocessed_midi_path, default_tempo=True):
    mid = MidiFile(ori_midi_path)

    bar_num, tempo = calculate_measures(mid)
    target_bars = 2
    time_factor = target_bars / bar_num if bar_num != 0 else 1
    target_tempo = round(tempo / time_factor) if not default_tempo else mido.bpm2tempo(120)

    new_mid = MidiFile(ticks_per_beat=mid.ticks_per_beat)
    for track in mid.tracks:
        new_track = MidiTrack()
        new_mid.tracks.append(new_track)
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                new_msg = msg.copy(time=int(msg.time * time_factor))
                new_track.append(new_msg)
            elif not msg.is_meta or msg.type != 'set_tempo':
                new_track.append(msg)
            else:
                new_track.append(MetaMessage('set_tempo', tempo=target_tempo))

    new_mid = adjust_ticks_per_beat(new_mid, 220)
    new_mid.save(preprocessed_midi_path)
    print(f"Converted {ori_midi_path} to {preprocessed_midi_path} with 2 bars, 120 QPM, and 220 ticks per quarter note.")

  
    
def get_tempo(midi_path):
    md = MidiFile(midi_path)
    for msg in md:
        if msg.type == 'set_tempo':
            return round(60000000 / msg.tempo)
    return 120  # Default tempo if not set in MIDI

def adjust_bpm(midi, target_bpm):
    tempo = mido.bpm2tempo(target_bpm)
    new_midi = MidiFile(ticks_per_beat=midi.ticks_per_beat)
    for track in midi.tracks:
        new_track = MidiTrack()
        new_midi.tracks.append(new_track)
        for msg in track:
            if msg.type == 'set_tempo':
                new_track.append(MetaMessage('set_tempo', tempo=tempo))
            else:
                new_track.append(msg)
    return new_midi

def calculate_measures(mid):
    tempo = mido.bpm2tempo(120)
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                tempo = msg.tempo
                break
    
    ticks_per_beat = mid.ticks_per_beat
    total_ticks = sum(msg.time for track in mid.tracks for msg in track)
    total_seconds = mido.tick2second(total_ticks, ticks_per_beat, tempo)
    beats_per_minute = mido.tempo2bpm(tempo)
    total_beats = total_seconds / (60 / beats_per_minute)
    bar_num = total_beats / 4

    return bar_num, tempo

def adjust_ticks_per_beat(mid, new_ticks_per_beat=220):
    original_ticks_per_beat = mid.ticks_per_beat
    time_adjustment_factor = original_ticks_per_beat / new_ticks_per_beat

    new_mid = MidiFile(ticks_per_beat=new_ticks_per_beat)
    for track in mid.tracks:
        new_track = MidiTrack()
        new_mid.tracks.append(new_track)
        for msg in track:
            adjusted_time = int(msg.time / time_adjustment_factor)
            new_msg = msg.copy(time=adjusted_time)
            new_track.append(new_msg)
    return new_mid

