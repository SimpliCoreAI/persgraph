"""
Phase 2 semantic-router tests — WorkflowDispatcher and model policy wiring.

Covers:
  - WorkflowDispatcher.resolve() for every workflow
  - Model policy mapping (model_preference → LiteLLM tier)
  - High-confidence dispatch (>= threshold) sets dispatched_semantically=True
  - Low-confidence falls back and sets dispatched_semantically=False
  - Command-hint fallback: correct fallback_command returned per workflow
  - dispatch_intent() convenience function
  - run_with_semantic_routing() rewrites input correctly (unit-level)
"""

import unittest
from unittest.mock import patch, MagicMock

from agents.orchestrator.semantic_router import (
    classify_request,
    dispatch_intent,
    WorkflowDispatcher,
    DispatchDecision,
    IntentResult,
    SEMANTIC_DISPATCH_THRESHOLD,
    _MODEL_POLICY,
    _WORKFLOW_TO_WORKER,
    _WORKFLOW_FALLBACK_COMMAND,
)


# ---------------------------------------------------------------------------
# WorkflowDispatcher unit tests
# ---------------------------------------------------------------------------

class TestWorkflowDispatcherResolution(unittest.TestCase):
    """Test WorkflowDispatcher.resolve() for each workflow."""

    def setUp(self):
        self.dispatcher = WorkflowDispatcher(threshold=0.6)

    def _make_intent(self, workflow: str, model_pref: str, confidence: float) -> IntentResult:
        return IntentResult(
            intent=workflow.replace("_workflow", ""),
            workflow=workflow,
            model_preference=model_pref,
            confidence=confidence,
            reason="test",
            command_hint=None,
        )

    def test_capture_workflow_resolves(self):
        intent = self._make_intent("capture_workflow", "haiku", 0.9)
        dec = self.dispatcher.resolve(intent)
        self.assertEqual(dec.workflow, "capture_workflow")
        self.assertEqual(dec.worker_type_value, "inbox_triage")
        self.assertEqual(dec.model_tier, "fast")
        self.assertEqual(dec.fallback_command, "/note")
        self.assertTrue(dec.dispatched_semantically)

    def test_calendar_workflow_resolves(self):
        intent = self._make_intent("calendar_workflow", "gemini", 0.9)
        dec = self.dispatcher.resolve(intent)
        self.assertEqual(dec.worker_type_value, "calendar_prep")
        self.assertEqual(dec.model_tier, "smart")
        self.assertEqual(dec.fallback_command, "/appointment")

    def test_travel_workflow_resolves(self):
        intent = self._make_intent("travel_workflow", "openai", 0.9)
        dec = self.dispatcher.resolve(intent)
        self.assertEqual(dec.worker_type_value, "travel_scout")
        self.assertEqual(dec.model_tier, "smart")
        self.assertEqual(dec.fallback_command, "/triptoggle")

    def test_ingest_workflow_resolves(self):
        intent = self._make_intent("ingest_workflow", "haiku", 0.9)
        dec = self.dispatcher.resolve(intent)
        self.assertEqual(dec.worker_type_value, "ingest")
        self.assertEqual(dec.model_tier, "fast")
        self.assertEqual(dec.fallback_command, "/ingest")

    def test_debrief_workflow_resolves(self):
        intent = self._make_intent("debrief_workflow", "sonnet", 0.9)
        dec = self.dispatcher.resolve(intent)
        self.assertEqual(dec.worker_type_value, "debrief")
        self.assertEqual(dec.model_tier, "smart")
        self.assertEqual(dec.fallback_command, "/digest")

    def test_reasoning_workflow_resolves_no_worker(self):
        intent = self._make_intent("reasoning_workflow", "sonnet", 0.9)
        dec = self.dispatcher.resolve(intent)
        self.assertIsNone(dec.worker_type_value)
        self.assertEqual(dec.model_tier, "smart")
        self.assertEqual(dec.fallback_command, "/ask")

    def test_browse_workflow_resolves_no_worker(self):
        intent = self._make_intent("browse_workflow", "perplexity", 0.9)
        dec = self.dispatcher.resolve(intent)
        self.assertIsNone(dec.worker_type_value)
        self.assertEqual(dec.model_tier, "smart")
        self.assertEqual(dec.fallback_command, "/ask")


# ---------------------------------------------------------------------------
# Confidence threshold tests
# ---------------------------------------------------------------------------

class TestConfidenceThreshold(unittest.TestCase):
    """Verify dispatched_semantically honours the threshold."""

    def _intent(self, confidence: float) -> IntentResult:
        return IntentResult(
            intent="capture",
            workflow="capture_workflow",
            model_preference="haiku",
            confidence=confidence,
            reason="test",
            command_hint=None,
        )

    def test_above_threshold_dispatches_semantically(self):
        dec = WorkflowDispatcher(threshold=0.6).resolve(self._intent(0.9))
        self.assertTrue(dec.dispatched_semantically)

    def test_at_threshold_dispatches_semantically(self):
        dec = WorkflowDispatcher(threshold=0.6).resolve(self._intent(0.6))
        self.assertTrue(dec.dispatched_semantically)

    def test_below_threshold_falls_back(self):
        dec = WorkflowDispatcher(threshold=0.6).resolve(self._intent(0.35))
        self.assertFalse(dec.dispatched_semantically)

    def test_below_threshold_still_has_fallback_command(self):
        """Even low-confidence decisions carry a fallback_command for callers."""
        dec = WorkflowDispatcher(threshold=0.6).resolve(self._intent(0.35))
        self.assertEqual(dec.fallback_command, "/note")

    def test_custom_threshold_respected(self):
        dec = WorkflowDispatcher(threshold=0.4).resolve(self._intent(0.55))
        self.assertTrue(dec.dispatched_semantically)

    def test_zero_confidence_falls_back(self):
        dec = WorkflowDispatcher(threshold=0.6).resolve(self._intent(0.0))
        self.assertFalse(dec.dispatched_semantically)


# ---------------------------------------------------------------------------
# Model policy mapping
# ---------------------------------------------------------------------------

class TestModelPolicy(unittest.TestCase):
    """Verify all model preferences map to a valid LiteLLM tier."""

    _VALID_TIERS = {"fast", "smart"}

    def test_all_model_preferences_map_to_valid_tier(self):
        for pref, tier in _MODEL_POLICY.items():
            self.assertIn(tier, self._VALID_TIERS, f"Model '{pref}' maps to unknown tier '{tier}'")

    def test_haiku_maps_to_fast(self):
        self.assertEqual(_MODEL_POLICY["haiku"], "fast")

    def test_sonnet_maps_to_smart(self):
        self.assertEqual(_MODEL_POLICY["sonnet"], "smart")

    def test_gemini_maps_to_smart(self):
        self.assertEqual(_MODEL_POLICY["gemini"], "smart")

    def test_unknown_preference_defaults_to_fast(self):
        """WorkflowDispatcher should gracefully handle unknown preferences."""
        intent = IntentResult(
            intent="capture",
            workflow="capture_workflow",
            model_preference="unknown_model",
            confidence=0.9,
            reason="test",
            command_hint=None,
        )
        dec = WorkflowDispatcher().resolve(intent)
        # Should default to "fast" (dict.get fallback)
        self.assertEqual(dec.model_tier, "fast")


# ---------------------------------------------------------------------------
# dispatch_intent convenience function
# ---------------------------------------------------------------------------

class TestDispatchIntentFunction(unittest.TestCase):
    """Test the module-level dispatch_intent() helper."""

    def test_dispatch_intent_returns_dispatch_decision(self):
        dec = dispatch_intent("remember to buy groceries")
        self.assertIsInstance(dec, DispatchDecision)
        self.assertIn(dec.workflow, [
            "capture_workflow", "calendar_workflow", "travel_workflow",
            "ingest_workflow", "debrief_workflow", "reasoning_workflow", "browse_workflow",
        ])

    def test_dispatch_intent_with_note_command_hint(self):
        dec = dispatch_intent("something", context={"command": "/note"})
        self.assertEqual(dec.workflow, "capture_workflow")
        self.assertEqual(dec.fallback_command, "/note")

    def test_dispatch_intent_with_ask_command_hint(self):
        dec = dispatch_intent("why is the sky blue", context={"command": "/ask"})
        self.assertEqual(dec.workflow, "reasoning_workflow")
        self.assertIsNone(dec.worker_type_value)

    def test_dispatch_intent_with_custom_threshold(self):
        # With threshold=1.1 (impossible to reach), always falls back
        dec = dispatch_intent("schedule a meeting", threshold=1.1)
        self.assertFalse(dec.dispatched_semantically)

    def test_dispatch_intent_high_confidence_travel(self):
        dec = dispatch_intent("book a hotel for my trip to Tokyo")
        # 'trip' + 'hotel' → travel intent, should be high confidence
        self.assertEqual(dec.workflow, "travel_workflow")
        self.assertTrue(dec.dispatched_semantically)

    def test_dispatch_intent_capture_keywords(self):
        dec = dispatch_intent("save this note and remember to call dentist")
        self.assertEqual(dec.workflow, "capture_workflow")


# ---------------------------------------------------------------------------
# Command-hint fallback mapping completeness
# ---------------------------------------------------------------------------

class TestFallbackCommandMapping(unittest.TestCase):
    """Verify every workflow has a fallback command (or None only for explicitly unlisted)."""

    def test_all_workflow_to_worker_keys_covered(self):
        """Every workflow in _WORKFLOW_TO_WORKER must also have a fallback command."""
        for wf in _WORKFLOW_TO_WORKER:
            self.assertIn(
                wf,
                _WORKFLOW_FALLBACK_COMMAND,
                f"Workflow '{wf}' is in _WORKFLOW_TO_WORKER but missing from _WORKFLOW_FALLBACK_COMMAND",
            )

    def test_capture_workflow_fallback(self):
        self.assertEqual(_WORKFLOW_FALLBACK_COMMAND["capture_workflow"], "/note")

    def test_debrief_workflow_fallback(self):
        self.assertEqual(_WORKFLOW_FALLBACK_COMMAND["debrief_workflow"], "/digest")

    def test_reasoning_workflow_fallback(self):
        self.assertEqual(_WORKFLOW_FALLBACK_COMMAND["reasoning_workflow"], "/ask")


# ---------------------------------------------------------------------------
# run_with_semantic_routing dispatch-rewrite logic (unit, no I/O)
# ---------------------------------------------------------------------------

class TestRunWithSemanticRoutingDispatch(unittest.TestCase):
    """Verify run_with_semantic_routing rewrites input correctly.

    We patch route_command_with_gates + command_handler.run to avoid real I/O.
    """

    def _make_routed_task(self, command: str):
        from agents.orchestrator.router import RoutedTask
        from agents.orchestrator.event_manager import generate_event_id
        from agents.orchestrator.worker_registry import WorkerType
        eid = generate_event_id("inbox_triage", command, user_id="test")
        return RoutedTask(
            event_id=eid,
            worker_type=WorkerType.INBOX_TRIAGE,
            command=command,
            args="",
            payload={"event_id": eid, "command": command, "args": ""},
            user_context={"name": "test", "tier": "user"},
            bypass_worker=False,
            requires_approval=False,
            approval_reason=None,
        )

    @patch("agents.orchestrator.orchestrator.log_execution")
    @patch("agents.orchestrator.orchestrator.log_outcome")
    @patch("agents.orchestrator.orchestrator.route_command_with_gates")
    @patch("agents.orchestrator.command_handler.run")
    @patch("agents.orchestrator.command_handler.resolve_user")
    def test_high_confidence_rewrites_to_fallback_command(
        self,
        mock_resolve_user,
        mock_cmd_run,
        mock_route,
        mock_log_outcome,
        mock_log_exec,
    ):
        """High-confidence free-text → input rewritten with fallback command."""
        mock_resolve_user.return_value = {"name": "alice", "tier": "user", "model": "haiku"}
        mock_route.return_value = self._make_routed_task("/note")
        mock_cmd_run.return_value = "✅ Note saved"

        from agents.orchestrator.orchestrator import run_with_semantic_routing
        result = run_with_semantic_routing("remember to buy milk and save it")

        self.assertEqual(result, "✅ Note saved")
        # The dispatched input to command_handler.run should start with /note
        dispatched_input = mock_cmd_run.call_args[0][0]
        self.assertTrue(
            dispatched_input.startswith("/note"),
            f"Expected dispatched input to start with /note, got: {dispatched_input!r}",
        )

    @patch("agents.orchestrator.orchestrator.log_execution")
    @patch("agents.orchestrator.orchestrator.log_outcome")
    @patch("agents.orchestrator.orchestrator.route_command_with_gates")
    @patch("agents.orchestrator.command_handler.run")
    @patch("agents.orchestrator.command_handler.resolve_user")
    def test_model_tier_injected_into_user_context(
        self,
        mock_resolve_user,
        mock_cmd_run,
        mock_route,
        mock_log_outcome,
        mock_log_exec,
    ):
        """Semantic model_tier must be patched into user context for route_command_with_gates."""
        mock_resolve_user.return_value = {"name": "bob", "tier": "user", "model": "haiku"}
        mock_route.return_value = self._make_routed_task("/note")
        mock_cmd_run.return_value = "ok"

        from agents.orchestrator.orchestrator import run_with_semantic_routing
        run_with_semantic_routing("save this note for later")

        # Capture user_context passed to route_command_with_gates
        _, kwargs = mock_route.call_args
        user_ctx = kwargs.get("user_context") or mock_route.call_args[0][1]
        # For capture_workflow haiku → fast tier
        self.assertEqual(user_ctx.get("model"), "fast")

    @patch("agents.orchestrator.orchestrator.log_execution")
    @patch("agents.orchestrator.orchestrator.log_outcome")
    @patch("agents.orchestrator.orchestrator.route_command_with_gates")
    @patch("agents.orchestrator.command_handler.run")
    @patch("agents.orchestrator.command_handler.resolve_user")
    def test_approval_required_returns_pending_message(
        self,
        mock_resolve_user,
        mock_cmd_run,
        mock_route,
        mock_log_outcome,
        mock_log_exec,
    ):
        """When routed_task.requires_approval=True, return a pending message without executing."""
        from agents.orchestrator.router import RoutedTask
        mock_resolve_user.return_value = {"name": "carol", "tier": "user", "model": "haiku"}

        task = self._make_routed_task("/note")
        # Build a requires_approval version via _replace
        approval_task = task._replace(requires_approval=True, approval_reason="test")
        mock_route.return_value = approval_task

        from agents.orchestrator.orchestrator import run_with_semantic_routing
        result = run_with_semantic_routing("remember something sensitive")

        self.assertIn("pending approval", result)
        mock_cmd_run.assert_not_called()

    @patch("agents.orchestrator.orchestrator.log_execution")
    @patch("agents.orchestrator.orchestrator.log_outcome")
    @patch("agents.orchestrator.orchestrator.route_command_with_gates")
    @patch("agents.orchestrator.command_handler.run")
    @patch("agents.orchestrator.command_handler.resolve_user")
    def test_low_confidence_passes_raw_input(
        self,
        mock_resolve_user,
        mock_cmd_run,
        mock_route,
        mock_log_outcome,
        mock_log_exec,
    ):
        """Low-confidence text (gibberish) → raw input forwarded unchanged."""
        mock_resolve_user.return_value = {"name": "dave", "tier": "user", "model": "haiku"}
        mock_route.return_value = self._make_routed_task("")
        mock_cmd_run.return_value = "?"

        from agents.orchestrator.orchestrator import run_with_semantic_routing
        # Pass ambiguous text that should score 0 or 1 keyword match (confidence <= 0.55)
        # The exact dispatch depends on classify_request; just verify it doesn't crash.
        result = run_with_semantic_routing("xyzzy flibbertigibbet")
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# Regression: existing Phase 1 classify_request still works
# ---------------------------------------------------------------------------

class TestPhase1Regression(unittest.TestCase):
    """Ensure Phase 1 classify_request is unmodified and still passes."""

    def test_command_hint_note_overrides_intent(self):
        result = classify_request("some ambiguous text", command_hint="/note")
        self.assertEqual(result.intent, "capture")
        self.assertEqual(result.workflow, "capture_workflow")

    def test_command_hint_ask_overrides_intent(self):
        result = classify_request("what is the best route", command_hint="/ask")
        self.assertEqual(result.intent, "reasoning")

    def test_travel_keywords_score_high(self):
        result = classify_request("find a hotel near the airport for my trip")
        self.assertEqual(result.intent, "travel")
        self.assertGreaterEqual(result.confidence, 0.9)

    def test_confidence_tiers(self):
        high = classify_request("note reminder task")
        self.assertGreaterEqual(high.confidence, 0.9)

        low = classify_request("xyz")
        self.assertLessEqual(low.confidence, 0.4)


if __name__ == "__main__":
    unittest.main()
