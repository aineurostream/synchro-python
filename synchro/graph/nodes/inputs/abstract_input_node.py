from abc import ABC

from synchro.graph.graph_node import EmittingNodeMixin, GraphNode


class AbstractInputNode(GraphNode, EmittingNodeMixin, ABC):
    pass
