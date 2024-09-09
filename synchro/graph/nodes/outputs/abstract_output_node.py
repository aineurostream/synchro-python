from abc import ABC

from synchro.graph.graph_node import ContextualGraphNode, ReceivingNodeMixin


class AbstractOutputNode(ContextualGraphNode, ReceivingNodeMixin, ABC):
    pass
