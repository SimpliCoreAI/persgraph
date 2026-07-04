"""Cost attribution: extract user_id, operation, model from Langfuse observations."""

import logging
from typing import Optional

from agents.cost_agent.shared.constants import OperationType, TRACE_TAGS

logger = logging.getLogger(__name__)


class AttributionExtractor:
    """Extract cost attribution metadata from Langfuse observations."""
    
    def extract_user_id(self, observation: dict) -> Optional[str]:
        """
        Extract user_id from observation.
        
        Looks in:
        1. observation["tags"] for user_id tag
        2. observation["metadata"] for user_id field
        3. observation["trace_id"] (fallback to trace ID if no user context)
        
        Returns:
            User ID string, or None if not found
        """
        if not observation:
            return None
        
        # Check tags first
        tags = observation.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.startswith("user_id:"):
                    return tag.split(":", 1)[1]
                # Also check for plain tag value if it looks like a Telegram ID
                if tag.isdigit() and len(tag) >= 9:  # Telegram IDs are typically 9-10 digits
                    return tag
        
        # Check metadata
        metadata = observation.get("metadata", {})
        if isinstance(metadata, dict):
            if "user_id" in metadata:
                return str(metadata["user_id"])
            if "telegram_id" in metadata:
                return str(metadata["telegram_id"])
        
        # Fallback to trace_id (not ideal, but better than None)
        # trace_id = observation.get("trace_id")
        # if trace_id:
        #     return trace_id
        
        return None
    
    def extract_operation(self, observation: dict) -> Optional[str]:
        """
        Extract operation type from observation.
        
        Looks in:
        1. observation["name"] (operation name / span name)
        2. observation["tags"] for operation tag
        3. observation["metadata"] for operation field
        
        Returns:
            Operation type string, or None if not found
        """
        if not observation:
            return None
        
        # Check span/operation name
        name = observation.get("name", "")
        if isinstance(name, str):
            name_lower = name.lower()
            # Try to match known operation types
            for op_type in OperationType:
                if op_type.value in name_lower:
                    return op_type.value
            # If name looks like an operation (contains _), return it as-is
            if "_" in name:
                return name
        
        # Check tags for operation tag
        tags = observation.get("tags", [])
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.startswith("operation:"):
                    return tag.split(":", 1)[1]
        
        # Check metadata
        metadata = observation.get("metadata", {})
        if isinstance(metadata, dict):
            if "operation" in metadata:
                return str(metadata["operation"])
            if "operation_type" in metadata:
                return str(metadata["operation_type"])
        
        # Default fallback — always return "other" rather than None
        return OperationType.OTHER.value
    
    def extract_model_info(self, observation: dict) -> dict:
        """
        Extract model and provider info from observation.
        
        Returns:
            Dict with keys: model, provider (inferred from model name or tags)
        """
        if not observation:
            return {"model": "unknown", "provider": "unknown"}
        
        model = observation.get("model", "unknown")
        if not isinstance(model, str):
            model = str(model) if model else "unknown"
        
        # Infer provider from model name
        provider = "unknown"
        if "claude" in model.lower():
            provider = "anthropic"
        elif "gpt" in model.lower():
            provider = "openai"
        elif "qwen" in model.lower() or "ollama" in model.lower():
            provider = "ollama"
        
        return {"model": model, "provider": provider}
    
    def extract_tokens(self, observation: dict) -> tuple[int, int]:
        """
        Extract input and output token counts from observation.
        
        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        if not observation:
            return 0, 0
        
        input_tokens = observation.get("input_tokens", 0)
        output_tokens = observation.get("output_tokens", 0)
        
        # Ensure they're integers
        try:
            input_tokens = int(input_tokens) if input_tokens else 0
            output_tokens = int(output_tokens) if output_tokens else 0
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse token counts: in={input_tokens}, out={output_tokens}")
            return 0, 0
        
        return input_tokens, output_tokens
    
    def extract_timestamps(self, observation: dict) -> tuple[Optional[str], Optional[str]]:
        """
        Extract start and end timestamps from observation.
        
        Returns:
            Tuple of (start_time, end_time) as ISO strings, or (None, None) if not found
        """
        if not observation:
            return None, None
        
        start_time = observation.get("start_time")
        end_time = observation.get("end_time")
        
        return start_time, end_time


if __name__ == "__main__":
    # Quick test
    extractor = AttributionExtractor()
    
    sample_obs = {
        "name": "cmd_ask",
        "model": "claude-sonnet-4-6",
        "input_tokens": 1500,
        "output_tokens": 300,
        "tags": ["user_id:8596241969", "llm", "ask"],
        "metadata": {"operation": "query_answer"},
        "trace_id": "trace_123",
    }
    
    print("User ID:", extractor.extract_user_id(sample_obs))
    print("Operation:", extractor.extract_operation(sample_obs))
    print("Model Info:", extractor.extract_model_info(sample_obs))
    print("Tokens:", extractor.extract_tokens(sample_obs))
