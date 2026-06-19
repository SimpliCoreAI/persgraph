"""
Base worker class for MVP sub-agents.

Provides a standardized interface for workers to:
  - Declare their tool/scope requirements
  - Receive capability-filtered payloads
  - Report results with tracing

Inheritance:
    class MyWorker(BaseWorker):
        def execute(self, payload: dict) -> str:
            # worker logic here
            return result

Usage:
    worker = MyWorker(WorkerType.INBOX_TRIAGE)
    result = worker.run(routed_task)
"""

from abc import ABC, abstractmethod
from agents.orchestrator.worker_registry import WorkerType, get_capabilities


class BaseWorker(ABC):
    """Abstract base for all workers in the MVP."""

    def __init__(self, worker_type: WorkerType):
        """
        Initialize a worker.

        Args:
            worker_type: The WorkerType this worker implements.
        """
        self.worker_type = worker_type
        self.capabilities = get_capabilities(worker_type)

    @abstractmethod
    def execute(self, payload: dict) -> str:
        """
        Execute the worker's primary logic.

        Args:
            payload: Task payload from the router (includes command, args, user context).

        Returns:
            Result string to return to user.
        """
        raise NotImplementedError

    def run(self, routed_task) -> str:
        """
        Execute the worker with capability validation.

        Args:
            routed_task: RoutedTask from router.route_command().

        Returns:
            Result string or error message.
        """
        try:
            # Validate worker type matches
            if routed_task.worker_type != self.worker_type:
                return (
                    f"❌ Worker type mismatch: expected {self.worker_type.value}, "
                    f"got {routed_task.worker_type.value if routed_task.worker_type else 'None'}"
                )

            # Execute the worker
            result = self.execute(routed_task.payload)
            return result

        except Exception as e:
            return f"❌ Worker error: {str(e)}"

    def can_use(self, tool: str) -> bool:
        """Check if this worker can use a tool."""
        if not self.capabilities:
            return False
        return self.capabilities.can_use(tool)

    def can_access(self, service: str) -> bool:
        """Check if this worker can access a service."""
        if not self.capabilities:
            return False
        return self.capabilities.can_access(service)
