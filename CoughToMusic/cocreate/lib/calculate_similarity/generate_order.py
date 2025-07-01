from .segment_features import MelodySegment
from .similarity import calculate_motif_similarity, compute_similarity_matrix, construct_similarity_graph, get_midi_order
import os

def get_midi_files(folder_path, exclude_file):
    """Get all MIDI files in the folder except the target file."""
    return [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
            if f.endswith(".mid") and os.path.join(folder_path, f) != exclude_file]

def generate_midi_sequence(target_midi_file, folder_path):
    """
    Generate a sequence of similar MIDI files based on an input MIDI ID.

    Args:
        midi_id (int): The ID of the target MIDI file (e.g., 1 for mel_1.mid).
        folder_path (str): Path to the directory containing MIDI files.

    Returns:
        list: Ordered sequence of MIDI file IDs.
    """
    # Load the target melody
    melody1 = MelodySegment(target_midi_file)
    melodies = [melody1]
    similarity_scores = []
    # Get all MIDI files excluding the target file
    midi_files = get_midi_files(folder_path, target_midi_file)
    # Compute similarity scores
    for midi_file2 in midi_files:
        melody2 = MelodySegment(midi_file2)
        melodies.append(melody2)
        similarity = calculate_motif_similarity(melody1.features, melody2.features)
        similarity_scores.append((os.path.basename(midi_file2), similarity))

    # Sort similarity scores in descending order
    similarity_scores.sort(key=lambda x: x[1], reverse=True)

    print("Top Similar MIDI Files:")
    for filename, similarity in similarity_scores[:3]:
        print(f"{filename}: {similarity:.4f}")

    # Get the top 3 similar MIDI files
    top_three_files = [os.path.join(folder_path, x[0]) for x in similarity_scores[:3]]

    # Load selected MIDI files
    selected_files = [melody1] + [MelodySegment(midi) for midi in top_three_files]
    nodes = [os.path.basename(midi) for midi in [target_midi_file] + top_three_files]

    # Compute pairwise similarity matrix
    similarity_matrix = compute_similarity_matrix(selected_files)

    # Construct similarity graph
    target_filename = os.path.basename(target_midi_file)
    # Build graph ensuring user's target motif is included
    graph = construct_similarity_graph(nodes, similarity_matrix)


    # Get MIDI order based on the graph structure
    midi_order_filenames = get_midi_order(graph, os.path.basename(target_midi_file), similarity_matrix, nodes)
    print("MIDI Order Filenames:", midi_order_filenames)
    # Convert filenames back to MIDI IDs
    midi_order = [int(f.replace("mel_", "").replace(".mid", "")) for f in midi_order_filenames]

    print("Final MIDI Order:", midi_order)
    return midi_order

