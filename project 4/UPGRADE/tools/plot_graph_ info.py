import networkx as nx
import matplotlib.pyplot as plt

def plot_garph(G):
    # Choose a layout algorithm

    # Draw the graph
    pos = nx.spring_layout(G, k=0.5, iterations=50)  # Adjust k and iterations for better spacing

    # Draw nodes with labels
    plt.figure(figsize=(10, 8))  # Increase figure size
    nx.draw_networkx_nodes(G, pos, node_size=700, node_color='skyblue', alpha=0.9)
    nx.draw_networkx_labels(G, pos, font_size=20, font_family="sans-serif")

    # Draw edges with labels
    nx.draw_networkx_edges(G, pos, width=2)
    edge_labels = nx.get_edge_attributes(G, 'weight')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)

    # Draw the graph
    plt.title("Graph of the chemical setup", fontsize=20)

    # Show the plot
    plt.show()


if __name__ == "__main__":
    from BV_experiments.Example3_debenzylation.db_doc import G
    # Create a directed graph
    plot_garph(G)
    # Print the graph to verify
    # print("Nodes:", G.nodes(data=True))
    # print("Edges:", G.edges(data=True))