from abc import ABC

from synchro.graph.graph_node import ContextualGraphNode, EmittingNodeMixin


class AbstractInputNode(ContextualGraphNode, EmittingNodeMixin, ABC):
    pass
