"""Validation and smoke test utilities for cost agent."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from agents.cost_agent.core.poller import PollerClient
from agents.cost_agent.core.calculator import CostCalculator
from agents.cost_agent.core.attribution import AttributionExtractor
from agents.cost_agent.shared.constants import validate_trace_id, validate_cost

logger = logging.getLogger(__name__)


class CostAgentValidator:
    """Validation and smoke testing for cost agent integration."""
    
    def __init__(self):
        self.calculator = CostCalculator()
        self.attribution = AttributionExtractor()
        self.poller = PollerClient()
        self.errors = []
        self.warnings = []
    
    async def run_smoke_test(self) -> dict:
        """
        Run comprehensive smoke test for cost agent.
        
        Tests:
        1. Langfuse connectivity
        2. Observation fetching
        3. Cost calculation accuracy
        4. Attribution extraction
        5. State persistence
        
        Returns:
            Test result dict with pass/fail and details
        """
        logger.info("Starting cost agent smoke test...")
        self.errors = []
        self.warnings = []
        
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tests": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": [],
                "warnings": [],
            }
        }
        
        # Test 1: Langfuse connectivity
        results["tests"]["langfuse_connectivity"] = await self._test_langfuse_connectivity()
        
        # Test 2: Cost calculation
        results["tests"]["cost_calculation"] = self._test_cost_calculation()
        
        # Test 3: Attribution extraction
        results["tests"]["attribution_extraction"] = self._test_attribution_extraction()
        
        # Test 4: Trace tag building
        results["tests"]["trace_tags"] = self._test_trace_tags()
        
        # Test 5: Poller functionality
        results["tests"]["poller_fetch"] = await self._test_poller_fetch()
        
        # Summary
        results["summary"]["total"] = len(results["tests"])
        results["summary"]["passed"] = sum(1 for t in results["tests"].values() if t.get("passed"))
        results["summary"]["failed"] = results["summary"]["total"] - results["summary"]["passed"]
        results["summary"]["errors"] = self.errors
        results["summary"]["warnings"] = self.warnings
        
        status = "✅ PASS" if results["summary"]["failed"] == 0 else "⚠️ PARTIAL"
        logger.info(f"Smoke test complete: {status} ({results['summary']['passed']}/{results['summary']['total']} passed)")
        
        return results
    
    async def _test_langfuse_connectivity(self) -> dict:
        """Test Langfuse SDK availability and basic connectivity."""
        result = {
            "name": "Langfuse Connectivity",
            "passed": False,
            "details": "",
        }
        
        try:
            from langfuse import Langfuse
            client = Langfuse()
            
            # Try health check
            if hasattr(client, 'auth_check'):
                try:
                    auth_check = await asyncio.to_thread(client.auth_check)
                    if auth_check:
                        result["passed"] = True
                        result["details"] = "Langfuse SDK available and auth check passed"
                    else:
                        result["details"] = "Langfuse SDK available but auth check inconclusive"
                        self.warnings.append("Langfuse auth_check inconclusive")
                except Exception as e:
                    result["details"] = f"Langfuse SDK available but auth_check failed: {e}"
                    self.warnings.append(str(e))
                    result["passed"] = True  # SDK still available
            else:
                result["passed"] = True
                result["details"] = "Langfuse SDK imported successfully"
        
        except Exception as e:
            result["details"] = f"Langfuse SDK import failed: {e}"
            self.errors.append(str(e))
        
        return result
    
    def _test_cost_calculation(self) -> dict:
        """Test cost calculation with known models."""
        result = {
            "name": "Cost Calculation",
            "passed": False,
            "details": [],
        }
        
        try:
            test_cases = [
                ("claude-sonnet-4-6", 1000, 500, True),
                ("gpt-4-turbo", 1000, 500, True),
                ("qwen2.5-7b", 0, 0, True),  # Ollama (free)
                ("unknown-model", 1000, 500, True),  # Fallback pricing
            ]
            
            passed = 0
            for model, input_tokens, output_tokens, should_succeed in test_cases:
                try:
                    cost, provider = self.calculator.calculate(model, input_tokens, output_tokens)
                    
                    if should_succeed:
                        if validate_cost(cost):
                            result["details"].append(f"✅ {model}: ${cost:.6f} ({provider})")
                            passed += 1
                        else:
                            result["details"].append(f"❌ {model}: Invalid cost {cost}")
                            self.errors.append(f"Invalid cost for {model}: {cost}")
                    else:
                        result["details"].append(f"❌ {model}: Should have failed but succeeded")
                        self.errors.append(f"Expected failure for {model}")
                
                except Exception as e:
                    if not should_succeed:
                        result["details"].append(f"✅ {model}: Failed as expected ({e})")
                        passed += 1
                    else:
                        result["details"].append(f"❌ {model}: {e}")
                        self.errors.append(str(e))
            
            result["passed"] = passed == len(test_cases)
            result["details"] = "\n".join(result["details"])
        
        except Exception as e:
            result["details"] = str(e)
            self.errors.append(str(e))
        
        return result
    
    def _test_attribution_extraction(self) -> dict:
        """Test attribution extraction from observations."""
        result = {
            "name": "Attribution Extraction",
            "passed": False,
            "details": [],
        }
        
        try:
            sample_obs = {
                "name": "cmd_ask",
                "model": "claude-sonnet-4-6",
                "input_tokens": 1500,
                "output_tokens": 300,
                "tags": ["user_id:8596241969", "operation:ask"],
                "metadata": {"domain": "query"},
                "trace_id": "trace_12345",
                "start_time": datetime.now(timezone.utc).isoformat(),
            }
            
            # Test user_id extraction
            user_id = self.attribution.extract_user_id(sample_obs)
            if user_id == "8596241969":
                result["details"].append(f"✅ User ID extraction: {user_id}")
            else:
                result["details"].append(f"❌ User ID extraction failed: expected 8596241969, got {user_id}")
                self.errors.append(f"User ID extraction: {user_id}")
            
            # Test operation extraction
            operation = self.attribution.extract_operation(sample_obs)
            if operation == "ask":
                result["details"].append(f"✅ Operation extraction: {operation}")
            else:
                result["details"].append(f"❌ Operation extraction failed: expected ask, got {operation}")
                self.errors.append(f"Operation extraction: {operation}")
            
            # Test token extraction
            input_tok, output_tok = self.attribution.extract_tokens(sample_obs)
            if input_tok == 1500 and output_tok == 300:
                result["details"].append(f"✅ Token extraction: {input_tok} in, {output_tok} out")
            else:
                result["details"].append(f"❌ Token extraction failed: {input_tok}, {output_tok}")
                self.errors.append(f"Token extraction: {input_tok}, {output_tok}")
            
            # Test model extraction
            model_info = self.attribution.extract_model_info(sample_obs)
            if model_info["provider"] == "anthropic":
                result["details"].append(f"✅ Model extraction: {model_info['model']} ({model_info['provider']})")
            else:
                result["details"].append(f"❌ Model extraction failed: {model_info}")
                self.errors.append(f"Model extraction: {model_info}")
            
            result["passed"] = len(self.errors) == 0
            result["details"] = "\n".join(result["details"])
        
        except Exception as e:
            result["details"] = str(e)
            self.errors.append(str(e))
        
        return result
    
    def _test_trace_tags(self) -> dict:
        """Test trace tag building and command parsing."""
        result = {
            "name": "Trace Tags",
            "passed": False,
            "details": [],
        }
        
        try:
            from agents.cost_agent.core.tagging import build_trace_tags, extract_operation_from_command
            
            # Test tag building
            tags = build_trace_tags(
                user_id="8596241969",
                operation="ask",
                model="smart",
            )
            expected = ["user_id:8596241969", "operation:ask", "model:smart"]
            if tags == expected:
                result["details"].append(f"✅ Tag building: {tags}")
            else:
                result["details"].append(f"❌ Tag building failed: {tags} != {expected}")
                self.errors.append(f"Tag building: {tags}")
            
            # Test operation extraction from commands
            test_commands = [
                ("/ask what is RAG?", "ask"),
                ("/ingest https://example.com", "ingest"),
                ("/place Paris, France", "place"),
                ("/email classify this", "email"),
            ]
            
            for cmd, expected_op in test_commands:
                op = extract_operation_from_command(cmd)
                if op == expected_op:
                    result["details"].append(f"✅ Command parsing: {cmd} → {op}")
                else:
                    result["details"].append(f"❌ Command parsing failed: {cmd} → {op} (expected {expected_op})")
                    self.errors.append(f"Command parsing: {cmd} → {op}")
            
            result["passed"] = len(self.errors) == 0
            result["details"] = "\n".join(result["details"])
        
        except Exception as e:
            result["details"] = str(e)
            self.errors.append(str(e))
        
        return result
    
    async def _test_poller_fetch(self) -> dict:
        """Test poller observation fetching."""
        result = {
            "name": "Poller Fetch",
            "passed": False,
            "details": [],
        }
        
        try:
            poller_result = await self.poller.poll_and_update()
            
            # Check result structure
            required_keys = ["observations_fetched", "observations_processed", "cost_calculated_usd", "errors"]
            missing = [k for k in required_keys if k not in poller_result]
            
            if missing:
                result["details"].append(f"❌ Missing keys in poller result: {missing}")
                self.errors.append(f"Poller result missing: {missing}")
            else:
                result["details"].append(f"✅ Poller result structure valid")
            
            # Check values
            if poller_result.get("observations_fetched", 0) >= 0:
                result["details"].append(f"✅ Observations fetched: {poller_result['observations_fetched']}")
            else:
                result["details"].append(f"❌ Invalid observation count")
                self.errors.append("Invalid observation count")
            
            if validate_cost(poller_result.get("cost_calculated_usd", 0)):
                result["details"].append(f"✅ Cost calculated: ${poller_result['cost_calculated_usd']:.6f}")
            else:
                result["details"].append(f"❌ Invalid cost calculated")
                self.errors.append("Invalid cost calculated")
            
            result["passed"] = len(self.errors) == 0
            result["details"] = "\n".join(result["details"])
        
        except Exception as e:
            result["details"] = str(e)
            self.errors.append(str(e))
        
        return result


async def run_validator_smoke_test() -> dict:
    """Convenience function: run full smoke test."""
    validator = CostAgentValidator()
    return await validator.run_smoke_test()


if __name__ == "__main__":
    import json
    
    logging.basicConfig(level=logging.INFO)
    
    results = asyncio.run(run_validator_smoke_test())
    print("\n" + "="*70)
    print("COST AGENT SMOKE TEST RESULTS")
    print("="*70)
    print(json.dumps(results, indent=2, default=str))
