
from pathlib import Path
from calculate_similarity.generate_order import generate_midi_sequence
from generation import generate_melody_from_sequence
from timbre_synthesize import generate_trio  
from drum import generate_drum_motif
from midi import write_from_midi

INPUT_MID_ID = 3
INST = 'string'

def main():
    # Step 1: Generate MIDI Order
    folder_path = Path("recorded_coughs")
    print("Step 1: Generating melody order...")
    input_midi_id = INPUT_MID_ID
    sequence = generate_midi_sequence(input_midi_id)
    print(f"MIDI sequence: {sequence}")

    print("Step 2: Generating melodies...")
    # generate_melody_from_sequence(sequence, 'mel', input_midi_id)
    # generate_melody_from_sequence(sequence, 'acc', input_midi_id)
    # generate_melody_from_sequence(sequence, 'bass', input_midi_id)
    

    print("Step 3: Applying timbre synthesis...")
    inst = INST
    # generate_trio(inst, input_midi_id)xx
    
    print("Step 4: Generating drum motif...")
    # drum_output = str(Path("results") / "drum_mid" / f"drum_{input_midi_id}.mid")
    # drum_wav = str(Path("results") / "drum_wav" / f"drum_{input_midi_id}.wav")
    # generate_drum_motif(folder_path, input_midi_id, drum_output)
    # write_from_midi(drum_output, drum_wav)
    write_from_midi( 'tracks\drum_mid\drum_1.mid',  'tracks\drum_wav\drum_1.wav')

    
    print("Pipeline Execution Completed.")

if __name__ == "__main__":
    main()
