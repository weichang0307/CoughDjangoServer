import numpy as np
import networkx as nx
def calculate_window_similarity(window1, window2, max_pitch_diff=36, max_transition_rate=30):
    overlap = max(0, min(window1['max_pitch'], window2['max_pitch']) - max(window1['min_pitch'], window2['min_pitch']))
    combined_range = max(window1['max_pitch'], window2['max_pitch']) - min(window1['min_pitch'], window2['min_pitch'])
    range_similarity = overlap / combined_range if combined_range > 0 else 1

    pitch_diff = abs(window1['avg_pitch'] - window2['avg_pitch'])
    avg_pitch_similarity = 1 - min(pitch_diff / max_pitch_diff, 1) if max_pitch_diff > 0 else 1

    transition_diff = abs(window1['transition_rate'] - window2['transition_rate'])
    transition_rate_similarity = 1 - min(transition_diff / max_transition_rate, 1) if max_transition_rate > 0 else 1

    max_note_density = max(window1['note_density'], window2['note_density'])
    note_density_similarity = min(window1['note_density'], window2['note_density']) / max_note_density if max_note_density > 0 else 1

    avg_dur1, avg_dur2 = window1['avg_duration'], window2['avg_duration']
    dur_denom = max(avg_dur1, avg_dur2)
    if dur_denom > 0:
        avg_duration_similarity = 1 - min(abs(avg_dur1 - avg_dur2) / dur_denom, 1)
    else:
        avg_duration_similarity = 1

    var1, var2 = window1['duration_variability'], window2['duration_variability']
    max_var = max(var1, var2)
    if max_var > 0:
        duration_variability_similarity = 1 - min(abs(var1 - var2) / max_var, 1)
    else:
        duration_variability_similarity = 1

    similarity = (0.3 * range_similarity +
                  0.2 * avg_pitch_similarity +
                  0.2 * transition_rate_similarity +
                  0.1 * note_density_similarity +
                  0.1 * avg_duration_similarity +
                  0.1 * duration_variability_similarity)

    return similarity


def calculate_motif_similarity(motif1, motif2):
    similarities = [calculate_window_similarity(w1, w2) for w1, w2 in zip(motif1, motif2)]
    return np.mean(similarities) if similarities else 0

def compute_similarity_matrix(selected_files):
    """Calculate the pairwise similarity matrix between MIDI files."""
    num_files = len(selected_files)
    similarity_matrix = np.zeros((num_files, num_files))
    
    for i in range(num_files):
        for j in range(i, num_files):
            similarity = calculate_motif_similarity(selected_files[i].features, selected_files[j].features)
            similarity_matrix[i, j] = similarity
            similarity_matrix[j, i] = similarity  # Symmetric matrix
    
    return similarity_matrix

def construct_similarity_graph(nodes, similarity_matrix):
    """Construct a graph by connecting highest similarity nodes."""
    graph = nx.Graph()
    for node in nodes:
        graph.add_node(node)

    # Create edges sorted by weight (highest similarity first)
    edges = [(nodes[i], nodes[j], similarity_matrix[i][j]) for i in range(len(nodes)) for j in range(i + 1, len(nodes))]
    edges = sorted(edges, key=lambda x: x[2], reverse=True)

    # Select edges ensuring each node has at most 2 connections
    selected_edges = []
    degree = {node: 0 for node in nodes}
    for u, v, weight in edges:
        if degree[u] < 2 and degree[v] < 2:
            selected_edges.append((u, v, weight))
            degree[u] += 1
            degree[v] += 1

    # Add selected edges to the graph
    for u, v, weight in selected_edges:
        graph.add_edge(u, v, weight=weight)

    return graph


def get_midi_order(graph, target_mel, similarity_matrix, nodes):
    # print (f"similarity_matrix: {similarity_matrix}")
    """Extracts the MIDI sequence based on the structured graph."""
    components = list(nx.connected_components(graph))
    largest_component = max(components, key=len)
    subgraph = graph.subgraph(largest_component)

    # Get sorted edges by weight (descending)
    edges = sorted(subgraph.edges(data=True), key=lambda x: x[2]['weight'], reverse=True)

    # CASE 1: If 4 nodes are connected, remove the weakest edge
    if len(largest_component) == 4:
        weakest_edge = min(edges, key=lambda x: x[2]['weight'])  # Find the lowest-weight edge
        graph.remove_edge(weakest_edge[0], weakest_edge[1])  # Remove it

        # Get the new largest connected component (should be 3 nodes)
        largest_component = max(nx.connected_components(graph), key=len)
        return list(largest_component)

    # Try finding a cycle in the remaining component
    try:
        cycle = nx.find_cycle(subgraph)
    except nx.exception.NetworkXNoCycle:
        cycle = None  # No cycle found

    if len(largest_component) == 3 and target_mel in largest_component:
        # Find and sort cycle edges by weight
        cycle_edges = sorted(cycle, key=lambda x: graph[x[0]][x[1]]['weight'], reverse=True)
        # Print cycle edges for debugging
        # print("\n=== Cycle Edges (Sorted by Weight) ===")
        # for edge in cycle_edges:
            # print(f"{edge[0]} -- ({graph[edge[0]][edge[1]]['weight']:.2f}) -- {edge[1]}")

        # Pick the two strongest edges
        first_edge = cycle_edges[0]
        second_edge = cycle_edges[1]

        # Print selected edges
        # print("\n=== Selected Top 2 Strongest Edges ===")
        # print(f"1st: {first_edge[0]} -- ({graph[first_edge[0]][first_edge[1]]['weight']:.2f}) -- {first_edge[1]}")
        # print(f"2nd: {second_edge[0]} -- ({graph[second_edge[0]][second_edge[1]]['weight']:.2f}) -- {second_edge[1]}")

        # Find the common node (should be the middle node)
        middle_node = list(set(first_edge[:2]).intersection(set(second_edge[:2])))[0]
        # Identify the other two nodes
        remaining_nodes = list(set(first_edge[:2]).union(set(second_edge[:2])) - {middle_node})
        # Assign order ensuring the middle node is correctly placed
        final_order = [remaining_nodes[0], middle_node, remaining_nodes[1]]
        # Debugging Output
        # print("\n=== Final Order (Target in Middle) ===")
        # print(final_order)
        return final_order

    # CASE 3: If 3 nodes connected but target is outside the cycle
    elif len(largest_component) == 3 and target_mel not in largest_component:
        # Find the node with highest similarity to target_mel
        target_idx = nodes.index(target_mel)
        similarities = similarity_matrix[target_idx]

        # Get the most similar node (excluding target itself)
        most_similar_node = nodes[np.argsort(similarities)[-2]]  # Second highest (highest is itself)

        return [target_mel, most_similar_node]

    # Default case: return the largest connected component
    return list(largest_component)
