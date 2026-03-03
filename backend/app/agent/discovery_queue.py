"""Discovery Queue — Priority BFS frontier for the RLM engine.

Provides a priority queue with a visited set for deduplication.
Items are processed breadth-first: at equal priority, shallower depth wins.

Usage:
    queue = DiscoveryQueue(max_depth=3)
    queue.enqueue(target_type="entity", target_id="hud-federal",
                  priority=1, discovered_from="sector:federal", depth=0)
    while not queue.is_empty():
        item = queue.pop()
        ...  # process item, enqueue children
"""

from __future__ import annotations

import heapq
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(order=True)
class QueueItem:
    """A single work item in the discovery queue.

    Ordering: (priority, depth, _seq) so that heapq pops the
    lowest-priority-number, shallowest-depth item first.
    _seq is a tie-breaker for FIFO stability.
    """

    priority: int
    depth: int
    _seq: int = field(compare=True, repr=False)

    # Non-comparison payload fields
    target_type: str = field(compare=False)  # "entity" | "source" | "program"
    target_id: str = field(compare=False)
    discovered_from: str = field(compare=False, default="")
    metadata: dict[str, Any] = field(compare=False, default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "priority": self.priority,
            "depth": self.depth,
            "discovered_from": self.discovered_from,
            "metadata": self.metadata,
        }


class DiscoveryQueue:
    """Priority queue with visited-set dedup for BFS discovery.

    Parameters:
        max_depth: Maximum depth allowed. Items beyond this are silently rejected.
        max_size: Maximum queue size. Items beyond this are silently rejected.
    """

    def __init__(self, max_depth: int = 3, max_size: int = 2000) -> None:
        self._heap: list[QueueItem] = []
        self._visited: set[str] = set()
        self._seq: int = 0
        self.max_depth = max_depth
        self.max_size = max_size

        # Counters for stats
        self._enqueued_total: int = 0
        self._dequeued_total: int = 0
        self._rejected_depth: int = 0
        self._rejected_visited: int = 0
        self._rejected_full: int = 0

    def enqueue(
        self,
        *,
        target_type: str,
        target_id: str,
        priority: int = 10,
        discovered_from: str = "",
        depth: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Add an item to the queue.

        Returns True if enqueued, False if rejected (visited/depth/full).
        """
        if depth > self.max_depth:
            self._rejected_depth += 1
            logger.debug(
                "[queue] rejected depth=%d > max=%d for %s:%s",
                depth, self.max_depth, target_type, target_id,
            )
            return False

        if target_id in self._visited:
            self._rejected_visited += 1
            return False

        if len(self._heap) >= self.max_size:
            self._rejected_full += 1
            logger.warning(
                "[queue] at capacity (%d) — rejecting %s:%s",
                self.max_size, target_type, target_id,
            )
            return False

        self._seq += 1
        item = QueueItem(
            priority=priority,
            depth=depth,
            _seq=self._seq,
            target_type=target_type,
            target_id=target_id,
            discovered_from=discovered_from,
            metadata=metadata or {},
        )
        heapq.heappush(self._heap, item)
        self._visited.add(target_id)
        self._enqueued_total += 1
        return True

    def pop(self) -> QueueItem | None:
        """Remove and return the highest-priority (lowest number) item.

        Returns None if the queue is empty.
        """
        if not self._heap:
            return None
        item = heapq.heappop(self._heap)
        self._dequeued_total += 1
        return item

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def is_visited(self, target_id: str) -> bool:
        return target_id in self._visited

    def mark_visited(self, target_id: str) -> None:
        """Mark an ID as visited without enqueuing (e.g. for pre-seeded items)."""
        self._visited.add(target_id)

    def size(self) -> int:
        return len(self._heap)

    def stats(self) -> dict[str, Any]:
        """Return queue statistics for logging and SSE events."""
        depth_counts: Counter[int] = Counter()
        type_counts: Counter[str] = Counter()
        for item in self._heap:
            depth_counts[item.depth] += 1
            type_counts[item.target_type] += 1

        return {
            "pending": len(self._heap),
            "visited": len(self._visited),
            "enqueued_total": self._enqueued_total,
            "dequeued_total": self._dequeued_total,
            "rejected_depth": self._rejected_depth,
            "rejected_visited": self._rejected_visited,
            "rejected_full": self._rejected_full,
            "by_depth": dict(sorted(depth_counts.items())),
            "by_type": dict(sorted(type_counts.items())),
        }
