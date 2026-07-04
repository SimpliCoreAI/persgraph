"""
Tests for the PersGraph MVP routing layer.

Validates:
  - Command → worker routing
  - Tool/scope boundary enforcement
  - Worker instantiation and capability checks
  - Backward compatibility with existing command_handler
"""

import unittest
from agents.orchestrator.router import route_command, validate_worker_access, RoutedTask
from agents.orchestrator.worker_registry import (
    WorkerType,
    get_worker_for_command,
    get_capabilities,
    describe_worker,
    list_workers,
)
from agents.orchestrator.orchestrator import describe_routing
from agents.inbox_triage.worker import InboxTriageWorker
from agents.calendar_prep.worker import CalendarPrepWorker
from agents.travel_scout_worker.worker import TravelScoutWorker
from agents.ingest_worker_mvp.worker import IngestWorker
from agents.debrief_worker.worker import DebriefWorker


class TestWorkerRegistry(unittest.TestCase):
    """Test worker_registry module."""

    def test_worker_types_exist(self):
        """Verify all worker types are defined."""
        workers = list_workers()
        self.assertEqual(len(workers), 5)
        self.assertIn(WorkerType.INBOX_TRIAGE, workers)
        self.assertIn(WorkerType.CALENDAR_PREP, workers)
        self.assertIn(WorkerType.TRAVEL_SCOUT, workers)
        self.assertIn(WorkerType.INGEST, workers)
        self.assertIn(WorkerType.DEBRIEF, workers)

    def test_inbox_triage_capabilities(self):
        """Verify inbox triage has correct tool scope."""
        cap = get_capabilities(WorkerType.INBOX_TRIAGE)
        self.assertIn("places_db", cap.allowed_tools)
        self.assertIn("notes_db", cap.allowed_tools)
        self.assertIn("task_db", cap.allowed_tools)
        self.assertNotIn("llm", cap.allowed_tools)
        self.assertNotIn("chroma", cap.allowed_tools)
        self.assertFalse(cap.requires_external_api)

    def test_ingest_capabilities(self):
        """Verify ingest worker has correct tool scope."""
        cap = get_capabilities(WorkerType.INGEST)
        self.assertIn("chroma", cap.allowed_tools)
        self.assertIn("ollama", cap.allowed_tools)
        self.assertIn("url_fetcher", cap.allowed_tools)
        self.assertNotIn("calendar_db", cap.allowed_tools)

    def test_travel_scout_requires_api(self):
        """Verify travel scout requires external API."""
        cap = get_capabilities(WorkerType.TRAVEL_SCOUT)
        self.assertTrue(cap.requires_external_api)
        self.assertIn("google_maps", cap.allowed_services)

    def test_command_to_worker_mapping(self):
        """Verify command → worker mappings are correct."""
        tests = [
            ("/note", WorkerType.INBOX_TRIAGE),
            ("/task", WorkerType.INBOX_TRIAGE),
            ("/place", WorkerType.INBOX_TRIAGE),
            ("/appointment", WorkerType.CALENDAR_PREP),
            ("/schedule", WorkerType.CALENDAR_PREP),
            ("/triptoggle", WorkerType.TRAVEL_SCOUT),
            ("/explore_accept", WorkerType.TRAVEL_SCOUT),
            ("/ingest", WorkerType.INGEST),
            ("/wiki-ingest", WorkerType.INGEST),
            ("/digest", WorkerType.DEBRIEF),
            ("/debrief", WorkerType.DEBRIEF),
        ]
        for cmd, expected_worker in tests:
            result = get_worker_for_command(cmd)
            self.assertEqual(
                result,
                expected_worker,
                f"Command {cmd} should map to {expected_worker.value}, got {result.value if result else None}",
            )

    def test_orchestrator_commands_have_no_worker(self):
        """Verify orchestrator commands don't map to workers."""
        tests = ["/ask", "/email", "/sport", "/pghelp", "/status"]
        for cmd in tests:
            result = get_worker_for_command(cmd)
            self.assertIsNone(result, f"Command {cmd} should not map to a worker")

    def test_describe_worker(self):
        """Verify describe_worker returns proper info."""
        desc = describe_worker(WorkerType.INBOX_TRIAGE)
        self.assertEqual(desc["type"], "inbox_triage")
        self.assertIn("allowed_tools", desc)
        self.assertIn("description", desc)
        self.assertIsInstance(desc["allowed_tools"], list)


class TestRouter(unittest.TestCase):
    """Test router module."""

    def test_route_note_command(self):
        """Verify /note is routed to inbox_triage."""
        routed = route_command("/note buy groceries", user_context={"tier": "user"})
        self.assertEqual(routed.worker_type, WorkerType.INBOX_TRIAGE)
        self.assertEqual(routed.command, "/note")
        self.assertEqual(routed.args, "buy groceries")
        self.assertFalse(routed.bypass_worker)

    def test_route_ask_command_bypasses_worker(self):
        """Verify /ask bypasses worker (handled by orchestrator)."""
        routed = route_command("/ask what is python", user_context={"tier": "user"})
        self.assertIsNone(routed.worker_type)
        self.assertTrue(routed.bypass_worker)

    def test_routed_task_payload(self):
        """Verify routed task payload is properly constructed."""
        user = {"name": "alice", "id": "123", "tier": "user"}
        routed = route_command("/task call dentist", user_context=user)
        self.assertEqual(routed.payload["command"], "/task")
        self.assertEqual(routed.payload["args"], "call dentist")
        self.assertEqual(routed.payload["user_name"], "alice")
        self.assertEqual(routed.payload["user_tier"], "user")

    def test_validate_worker_access_allowed(self):
        """Verify validate_worker_access allows known tools."""
        ok, denied = validate_worker_access(
            WorkerType.INBOX_TRIAGE, ["places_db", "notes_db"]
        )
        self.assertTrue(ok)
        self.assertEqual(len(denied), 0)

    def test_validate_worker_access_denied(self):
        """Verify validate_worker_access denies unknown tools."""
        ok, denied = validate_worker_access(
            WorkerType.INBOX_TRIAGE, ["places_db", "llm", "chroma"]
        )
        self.assertFalse(ok)
        self.assertIn("llm", denied)
        self.assertIn("chroma", denied)

    def test_validate_worker_mixed_tools(self):
        """Verify validate_worker_access handles mixed allowed/denied."""
        ok, denied = validate_worker_access(
            WorkerType.TRAVEL_SCOUT, ["places_db", "maps", "unknown_tool"]
        )
        self.assertFalse(ok)
        self.assertEqual(denied, ["unknown_tool"])


class TestWorkerInstantiation(unittest.TestCase):
    """Test worker instantiation and capability checks."""

    def test_inbox_triage_instantiate(self):
        """Verify InboxTriageWorker instantiates correctly."""
        worker = InboxTriageWorker()
        self.assertEqual(worker.worker_type, WorkerType.INBOX_TRIAGE)
        self.assertTrue(worker.can_use("places_db"))
        self.assertFalse(worker.can_use("llm"))

    def test_calendar_prep_instantiate(self):
        """Verify CalendarPrepWorker instantiates correctly."""
        worker = CalendarPrepWorker()
        self.assertEqual(worker.worker_type, WorkerType.CALENDAR_PREP)
        self.assertTrue(worker.can_use("calendar_db"))
        self.assertFalse(worker.can_use("chroma"))

    def test_travel_scout_instantiate(self):
        """Verify TravelScoutWorker instantiates correctly."""
        worker = TravelScoutWorker()
        self.assertEqual(worker.worker_type, WorkerType.TRAVEL_SCOUT)
        self.assertTrue(worker.can_use("maps"))
        self.assertFalse(worker.can_use("task_db"))

    def test_ingest_instantiate(self):
        """Verify IngestWorker instantiates correctly."""
        worker = IngestWorker()
        self.assertEqual(worker.worker_type, WorkerType.INGEST)
        self.assertTrue(worker.can_use("chroma"))
        self.assertTrue(worker.can_use("ollama"))
        self.assertFalse(worker.can_use("notes_db"))

    def test_debrief_instantiate(self):
        """Verify DebriefWorker instantiates correctly."""
        worker = DebriefWorker()
        self.assertEqual(worker.worker_type, WorkerType.DEBRIEF)
        self.assertTrue(worker.can_use("chroma"))
        self.assertTrue(worker.can_use("llm"))
        self.assertFalse(worker.can_use("url_fetcher"))


class TestOrchestrator(unittest.TestCase):
    """Test orchestrator module."""

    def test_describe_routing(self):
        """Verify describe_routing returns proper structure."""
        routing = describe_routing()
        self.assertIn("routing_table", routing)
        self.assertIn("workers", routing)

        # Check routing_table
        routing_table = routing["routing_table"]
        self.assertEqual(routing_table["/note"], "inbox_triage")
        self.assertEqual(routing_table["/appointment"], "calendar_prep")
        self.assertEqual(routing_table["/ask"], "orchestrator")

        # Check workers
        workers = routing["workers"]
        self.assertIn("inbox_triage", workers)
        self.assertIn("calendar_prep", workers)

    def test_routing_table_completeness(self):
        """Verify all major commands are in the routing table."""
        routing = describe_routing()
        routing_table = routing["routing_table"]

        expected_commands = [
            "/note",
            "/task",
            "/place",
            "/appointment",
            "/schedule",
            "/ingest",
            "/digest",
            "/debrief",
        ]
        for cmd in expected_commands:
            self.assertIn(cmd, routing_table, f"Command {cmd} missing from routing table")


class TestBackwardCompatibility(unittest.TestCase):
    """Verify backward compatibility with existing command_handler."""

    def test_command_handler_imports(self):
        """Verify command_handler module still imports."""
        from agents.orchestrator import command_handler

        self.assertGreater(len(command_handler.COMMANDS), 10)

    def test_command_handler_has_expected_commands(self):
        """Verify command_handler has expected commands."""
        from agents.orchestrator import command_handler

        expected = ["/note", "/task", "/place", "/ask", "/ingest", "/digest"]
        for cmd in expected:
            self.assertIn(cmd, command_handler.COMMANDS)


class TestSemanticRoutingFlag(unittest.TestCase):
    def test_run_with_semantic_routing_exists(self):
        from agents.orchestrator.orchestrator import run_with_semantic_routing
        self.assertTrue(callable(run_with_semantic_routing))

    def test_command_run_semantic_flag_present(self):
        from pathlib import Path
        command_py = Path('/root/AgenticHub/Persgraph/scripts/command.py').read_text()
        self.assertIn('PERSGRAPH_SEMANTIC_ROUTING', command_py)
        self.assertIn('run_with_semantic_routing', command_py)


if __name__ == "__main__":
    unittest.main()


class TestSemanticRouter(unittest.TestCase):
    def test_capture_intent_from_free_text(self):
        from agents.orchestrator.semantic_router import classify_request
        result = classify_request("remind me to buy milk and save it")
        self.assertEqual(result.intent, "capture")
        self.assertEqual(result.workflow, "capture_workflow")
        self.assertEqual(result.model_preference, "haiku")

    def test_calendar_intent_from_free_text(self):
        from agents.orchestrator.semantic_router import classify_request
        result = classify_request("schedule a meeting with Sam next Tuesday")
        self.assertEqual(result.intent, "calendar")
        self.assertEqual(result.workflow, "calendar_workflow")
        self.assertEqual(result.model_preference, "gemini")

    def test_reasoning_over_command_hint_when_ask(self):
        from agents.orchestrator.semantic_router import classify_request
        result = classify_request(
            "compare these two plans and explain tradeoffs", command_hint="/ask"
        )
        self.assertEqual(result.intent, "reasoning")
        self.assertEqual(result.model_preference, "sonnet")

    def test_command_hint_still_guides_capture(self):
        from agents.orchestrator.semantic_router import classify_request
        result = classify_request("something vague", command_hint="/note")
        self.assertEqual(result.intent, "capture")

    def test_route_semantically_returns_expected_shape(self):
        from agents.orchestrator.semantic_router import route_semantically
        routed = route_semantically("find the best sushi near downtown")
        self.assertIn("intent", routed)
        self.assertIn("workflow", routed)
        self.assertEqual(routed["route_kind"], "semantic-first")
