import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx

def plot_similarity_heatmap(similarity_matrix, labels):
    plt.figure(figsize=(8, 6))
    sns.heatmap(similarity_matrix, annot=True, fmt=".2f", xticklabels=labels, yticklabels=labels, cmap="magma", cbar=True)
    plt.title("Pairwise similarity of selected melody segments")
    plt.show()

def plot_similarity_graph(similarity_matrix, labels):
    graph = nx.Graph()
    for i, label in enumerate(labels):
        graph.add_node(label)

    edges = [(labels[i], labels[j], similarity_matrix[i][j]) for i in range(len(labels)) for j in range(i + 1, len(labels))]
    edges = sorted(edges, key=lambda x: x[2], reverse=True)

    selected_edges = []
    degree = {label: 0 for label in labels}
    for u, v, weight in edges:
        if degree[u] < 2 and degree[v] < 2:
            selected_edges.append((u, v, weight))
            degree[u] += 1
            degree[v] += 1

    for u, v, weight in selected_edges:
        graph.add_edge(u, v, weight=weight)

    pos = nx.spring_layout(graph)
    weights = nx.get_edge_attributes(graph, "weight")
    
    plt.figure(figsize=(8, 6))
    nx.draw(graph, pos, with_labels=True, node_color='lightblue', node_size=2000, font_size=10)
    nx.draw_networkx_edge_labels(graph, pos, edge_labels={k: f"{v:.2f}" for k, v in weights.items()})
    plt.title("Constructed Graph Based on Similarity Matrix")
    plt.show()
