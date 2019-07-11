import math, urllib3, json, re


# Step 1: For each node prepare the destination and predecessor
def initialize(graph, source):
    destination = {}  # Stands for destination
    predecessor = {}  # Stands for predecessor
    for node in graph:
        destination[node] = float('Inf')  # We start admiting that the rest of nodes are very very far
        predecessor[node] = None
    destination[source] = 0  # For the source we know how to reach
    return destination, predecessor


def relax(node, neighbour, graph, destination, predecessor):
    # If the distance between the node and the neighbour is lower than the one I have now
    if destination[neighbour] > destination[node] + graph[node][neighbour]:
        # Record this lower distance
        destination[neighbour] = destination[node] + graph[node][neighbour]
        predecessor[neighbour] = node


def retrace_negative_loop(predecessor, start):
    arbitrageLoop = [start]
    next_node = start
    while True:
        #print(predecessor)
        try:
            next_node = predecessor[next_node]
            if next_node not in arbitrageLoop:
                arbitrageLoop.append(next_node)
            else:
                arbitrageLoop.append(next_node)
                arbitrageLoop = arbitrageLoop[arbitrageLoop.index(next_node):]
                return arbitrageLoop
        except KeyError:
            return None


def bellman_ford(graph, source):
    destination, predecessor = initialize(graph, source)
    for i in range(len(graph) - 1):  # Run this until it converges
        for u in graph:
            for v in graph[u]:  # For each neighbour of u
                relax(u, v, graph, destination, predecessor)  # Lets relax it

    # Step 3: check for negative-weight cycles
    for u in graph:
        for v in graph[u]:
            if destination[v] < destination[u] + graph[u][v]:
                result = retrace_negative_loop(predecessor, source)
                if result:
                    return result
    return None
