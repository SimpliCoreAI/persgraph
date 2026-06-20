"""Langfuse observation poller: fetch observations, calculate costs, persist state."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agents.cost_agent.core.calculator import CostCalculator
from agents.cost_agent.core.attribution import AttributionExtractor
from agents.cost_agent.shared.constants import (
    STATE_FILE,
    COST_BY_USER_FILE,
    COST_BY_OPERATION_FILE,
    COST_BY_MODEL_FILE,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_BACKOFF_BASE_SECONDS,
    empty_cost_state,
    empty_cost_by_user,
    empty_cost_by_operation,
    empty_cost_by_model,
)
from agents.cost_agent.shared.formatters import (
    read_json_file,
    write_json_file,
    format_json,
)

logger = logging.getLogger(__name__)


class PollerClient:
    """Fetch Langfuse observations and calculate costs."""
    
    def __init__(self):
        self.calculator = CostCalculator()
        self.attribution = AttributionExtractor()
        self._init_langfuse()
    
    def _init_langfuse(self) -> bool:
        """Initialize Langfuse client. Returns True if enabled, False otherwise."""
        try:
            # Lazy import to avoid dependencies if not using Langfuse
            from second_brain.tracing import init_tracing
            init_tracing()
            self.langfuse_enabled = True
            logger.info("Langfuse initialized for cost agent")
            return True
        except Exception as e:
            logger.warning(f"Langfuse initialization failed: {e}. Poller will run in offline mode.")
            self.langfuse_enabled = False
            return False
    
    async def poll_and_update(self) -> dict:
        """
        Poll Langfuse for new observations and update cost records.
        
        Returns:
            Dict with poll result: {
                "observations_fetched": int,
                "observations_processed": int,
                "cost_calculated_usd": float,
                "last_trace_id": str,
                "errors": list[str],
            }
        """
        logger.info("Starting cost agent poller...")
        
        if not self.langfuse_enabled:
            logger.warning("Langfuse not available; poller skipping")
            return {
                "observations_fetched": 0,
                "observations_processed": 0,
                "cost_calculated_usd": 0.0,
                "last_trace_id": None,
                "errors": ["Langfuse not enabled"],
            }
        
        result = {
            "observations_fetched": 0,
            "observations_processed": 0,
            "cost_calculated_usd": 0.0,
            "last_trace_id": None,
            "errors": [],
        }
        
        try:
            # Load current state
            state = self._load_state()
            last_timestamp = state.get("last_seen_timestamp")
            
            # Fetch observations (mock for now; would call Langfuse API in production)
            observations = await self._fetch_observations(after_timestamp=last_timestamp)
            result["observations_fetched"] = len(observations)
            logger.info(f"Fetched {len(observations)} observations")
            
            # Process each observation
            total_cost = 0.0
            for obs in observations:
                try:
                    cost = self._process_observation(obs)
                    total_cost += cost
                    result["observations_processed"] += 1
                    result["last_trace_id"] = obs.get("trace_id")
                except Exception as e:
                    logger.error(f"Error processing observation {obs.get('trace_id')}: {e}")
                    result["errors"].append(str(e))
            
            result["cost_calculated_usd"] = round(total_cost, 6)
            
            # Update state
            if observations:
                state["last_seen_timestamp"] = datetime.now(timezone.utc).isoformat()
                state["last_seen_trace_id"] = result["last_trace_id"]
                state["observations_processed"] += result["observations_processed"]
                state["last_poll_time"] = datetime.now(timezone.utc).isoformat()
                self._save_state(state)
                logger.info(f"Updated state: {result['observations_processed']} observations processed")
            
        except Exception as e:
            logger.error(f"Poller error: {e}")
            result["errors"].append(str(e))
        
        logger.info(f"Poller complete: {result}")
        return result
    
    async def _fetch_observations(
        self,
        after_timestamp: Optional[str] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> list[dict]:
        """
        Fetch observations from Langfuse via SDK.
        
        Uses Langfuse SDK's observations.get_many() with cursor pagination.
        Implements exponential backoff for failed requests.
        
        Args:
            after_timestamp: ISO timestamp to fetch observations after
            batch_size: Number of observations per page
            max_retries: Max retry attempts for failed fetches
        
        Returns:
            List of observation dicts
        """
        from datetime import datetime as dt, timezone
        import time
        
        try:
            from langfuse import Langfuse
            client = Langfuse()
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse client: {e}")
            return []
        
        observations = []
        cursor = None
        retry_count = 0
        backoff_base = DEFAULT_BACKOFF_BASE_SECONDS
        
        # Parse after_timestamp if provided
        from_start_time = None
        if after_timestamp:
            try:
                from_start_time = dt.fromisoformat(after_timestamp.replace('Z', '+00:00'))
            except (ValueError, AttributeError) as e:
                logger.warning(f"Invalid timestamp {after_timestamp}: {e}")
        
        while retry_count < max_retries:
            try:
                # Call Langfuse API with pagination
                response = client.api.observations.get_many(
                    limit=batch_size,
                    cursor=cursor,
                    from_start_time=from_start_time,
                    fields="all",
                    expand_metadata=True,
                )
                
                # Extract observations from response
                # The response contains Observation objects; convert to dicts
                if hasattr(response, 'data') and response.data:
                    for obs_obj in response.data:
                        # Convert Langfuse observation object to dict
                        if hasattr(obs_obj, '__dict__'):
                            obs_dict = {k: v for k, v in obs_obj.__dict__.items() if not k.startswith('_')}
                        else:
                            obs_dict = obs_obj if isinstance(obs_obj, dict) else {}
                        
                        if obs_dict:
                            observations.append(obs_dict)
                    
                    logger.debug(f"Fetched {len(response.data)} observations (cursor={cursor})")
                    
                    # Check for more pages
                    if hasattr(response, 'meta') and hasattr(response.meta, 'next_cursor'):
                        cursor = response.meta.next_cursor
                        if not cursor:
                            # No more pages
                            break
                    else:
                        # No pagination info; assume done
                        break
                else:
                    # Empty response
                    break
                
                # Reset retry count on success
                retry_count = 0
                
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    backoff = backoff_base * (2 ** (retry_count - 1))  # exponential backoff
                    logger.warning(f"Fetch attempt {retry_count} failed: {e}. Retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                else:
                    logger.error(f"Fetch failed after {max_retries} retries: {e}")
        
        logger.info(f"Fetched {len(observations)} total observations")
        return observations
    
    def _process_observation(self, observation: dict) -> float:
        """
        Process a single observation: extract attribution, calculate cost, update records.
        
        Returns:
            Cost in USD
        """
        # Extract metadata
        user_id = self.attribution.extract_user_id(observation)
        operation = self.attribution.extract_operation(observation)
        model = observation.get("model", "unknown")
        input_tokens, output_tokens = self.attribution.extract_tokens(observation)
        
        # Calculate cost
        cost, provider = self.calculator.calculate(model, input_tokens, output_tokens)
        
        # Update cost records
        if cost > 0:
            date_str = self._get_date_from_observation(observation)
            
            # Update cost by user
            if user_id:
                self._update_cost_record(
                    COST_BY_USER_FILE,
                    empty_cost_by_user,
                    date_str,
                    user_id,
                    cost,
                )
            
            # Update cost by operation
            if operation:
                self._update_cost_record(
                    COST_BY_OPERATION_FILE,
                    empty_cost_by_operation,
                    date_str,
                    operation,
                    cost,
                )
            
            # Update cost by model
            self._update_cost_record(
                COST_BY_MODEL_FILE,
                empty_cost_by_model,
                date_str,
                model,
                cost,
            )
        
        return cost
    
    def _update_cost_record(
        self,
        file_path: Path,
        template_fn: callable,
        date_str: str,
        key: str,
        cost: float,
    ) -> None:
        """Update a cost record file atomically."""
        data = read_json_file(file_path)
        if not data:
            data = template_fn()
        
        # Update daily
        if "daily" not in data:
            data["daily"] = {}
        if date_str not in data["daily"]:
            data["daily"][date_str] = {}
        
        current = data["daily"][date_str].get(key, 0.0)
        data["daily"][date_str][key] = round(current + cost, 6)
        
        # Update total
        if "total" not in data:
            data["total"] = {}
        
        current_total = data["total"].get(key, 0.0)
        data["total"][key] = round(current_total + cost, 6)
        
        # Persist
        write_json_file(file_path, data)
    
    def _get_date_from_observation(self, observation: dict) -> str:
        """Extract date from observation (ISO format: YYYY-MM-DD)."""
        timestamp = observation.get("start_time") or observation.get("created_at")
        if timestamp:
            # Handle ISO format timestamps
            if "T" in str(timestamp):
                return str(timestamp).split("T")[0]
        return datetime.now(timezone.utc).date().isoformat()
    
    def _load_state(self) -> dict:
        """Load poller state from file. Returns empty state if file doesn't exist."""
        data = read_json_file(STATE_FILE)
        if not data:
            data = empty_cost_state()
        return data
    
    def _save_state(self, state: dict) -> bool:
        """Save poller state to file."""
        return write_json_file(STATE_FILE, state)


async def run_poller_once() -> dict:
    """Convenience function: create poller and run once."""
    poller = PollerClient()
    return await poller.poll_and_update()


if __name__ == "__main__":
    # Quick test
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    poller = PollerClient()
    result = asyncio.run(poller.poll_and_update())
    print(f"\nPoller result:\n{format_json(result)}")
