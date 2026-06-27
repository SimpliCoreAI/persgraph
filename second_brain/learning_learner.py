"""
PersGraph Learning Loop — Process stored events/outcomes into skills/preferences

Minimal learner that:
1. Reads new events/outcomes since last checkpoint
2. Infers patterns (e.g., user prefers high-rated restaurants)
3. Updates skills and preferences
4. Advances checkpoint

Safe to run on cron; uses checkpoint to avoid reprocessing.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# Root relative to this file
ROOT = Path(__file__).parent.parent

try:
    from second_brain import learning_db
except ImportError:
    from learning_db import learning_db


# Checkpoint file: tracks last processed timestamp
CHECKPOINT_PATH = ROOT / "data" / "learning_checkpoint.json"


def get_checkpoint() -> str:
    """Load last processed timestamp (ISO 8601 UTC)."""
    if CHECKPOINT_PATH.exists():
        try:
            data = json.loads(CHECKPOINT_PATH.read_text())
            return data.get("last_processed_at", "1970-01-01T00:00:00Z")
        except Exception as e:
            logger.warning(f"Failed to read checkpoint: {e}")
            return "1970-01-01T00:00:00Z"
    return "1970-01-01T00:00:00Z"


def set_checkpoint(timestamp: str) -> None:
    """Save checkpoint after processing."""
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = {
            "last_processed_at": timestamp,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        CHECKPOINT_PATH.write_text(json.dumps(data, indent=2))
        logger.debug(f"Checkpoint saved: {timestamp}")
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")


def process_outcomes_into_skills(outcomes: list[dict[str, Any]]) -> dict[str, str]:
    """Infer skills from recent outcomes."""
    skills_created = {}
    
    if not outcomes:
        return skills_created
    
    # Pattern 1: User clicks/accepts high-rated items
    high_rated = [
        o for o in outcomes
        if o.get("outcome_type") in ("clicked", "accepted", "bookmarked")
        and o.get("suggestion_title")
    ]
    
    if high_rated:
        # Infer: user engages with items quickly (good matches)
        engagements = [o.get("engagement_seconds", 0) for o in high_rated if o.get("engagement_seconds") is not None]
        avg_engagement = sum(engagements) / max(len(engagements), 1) if engagements else 0
        
        skill_id = learning_db.create_skill(
            skill_name="user_engagement_pattern",
            skill_category="preference",
            confidence=min(0.5 + len(high_rated) * 0.1, 0.95),
            signal_strength=len(high_rated),
            skill_data={
                "avg_engagement_seconds": avg_engagement,
                "click_accept_rate": len(high_rated) / max(len(outcomes), 1),
            }
        )
        if skill_id:
            skills_created["engagement"] = skill_id
            logger.info(f"Created skill: user_engagement_pattern ({skill_id})")
    
    # Pattern 2: User skips certain categories
    skipped = [
        o for o in outcomes
        if o.get("outcome_type") == "skipped"
    ]
    
    if skipped:
        skill_id = learning_db.create_skill(
            skill_name="user_skip_pattern",
            skill_category="filter",
            confidence=min(0.5 + len(skipped) * 0.1, 0.95),
            signal_strength=len(skipped),
            skill_data={
                "skip_count": len(skipped),
                "skip_rate": len(skipped) / max(len(outcomes), 1),
            }
        )
        if skill_id:
            skills_created["skip"] = skill_id
            logger.info(f"Created skill: user_skip_pattern ({skill_id})")

    # Pattern 3: Judged responses influence response-quality skills
    judged = [o for o in outcomes if o.get("outcome_type") == "judged"]
    if judged:
        overall_scores = []
        usefulness_scores = []
        for o in judged:
            meta = o.get("metadata", {}) or {}
            scores = meta.get("scores", {}) or {}
            if isinstance(scores.get("overall_score"), (int, float)):
                overall_scores.append(float(scores["overall_score"]))
            if isinstance(scores.get("usefulness"), (int, float)):
                usefulness_scores.append(float(scores["usefulness"]))

        if overall_scores:
            avg_overall = sum(overall_scores) / len(overall_scores)
            skill_id = learning_db.create_skill(
                skill_name="response_quality_pattern",
                skill_category="quality",
                confidence=min(avg_overall / 5.0, 0.95),
                signal_strength=len(overall_scores),
                skill_data={
                    "avg_overall_score": avg_overall,
                    "judged_count": len(overall_scores),
                },
            )
            if skill_id:
                skills_created["judged_quality"] = skill_id
                logger.info(f"Created skill: response_quality_pattern ({skill_id})")

        if usefulness_scores:
            avg_usefulness = sum(usefulness_scores) / len(usefulness_scores)
            if avg_usefulness < 2.5:
                pref_id = learning_db.set_preference(
                    "response_usefulness_alert",
                    "low",
                    source="learned",
                    confidence=0.7,
                )
                if pref_id:
                    prefs_set["response_usefulness_alert"] = pref_id
                    logger.info(f"Updated preference: response_usefulness_alert=low ({pref_id})")
    
    return skills_created


def infer_preferences_from_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, str]:
    """Infer user preferences from outcome patterns."""
    prefs_set = {}
    
    if not outcomes:
        return prefs_set
    
    # Preference 1: exploration intensity based on engagement
    high_engagement = sum(
        1 for o in outcomes
        if (o.get("engagement_seconds") is not None and o.get("engagement_seconds") < 5) 
           and o.get("outcome_type") in ("clicked", "accepted")
    )
    
    if high_engagement > len(outcomes) * 0.5:
        pref_id = learning_db.set_preference(
            "explore_intensity",
            "high",
            source="learned",
            confidence=0.7
        )
        if pref_id:
            prefs_set["intensity"] = pref_id
            logger.info(f"Updated preference: explore_intensity=high ({pref_id})")
    
    # Preference 2: cadence based on skip patterns
    skip_rate = sum(1 for o in outcomes if o.get("outcome_type") == "skipped") / max(len(outcomes), 1)
    
    if skip_rate > 0.4:
        # User skips frequently; suggest longer cadence
        pref_id = learning_db.set_preference(
            "explore_cadence_minutes",
            90,
            source="learned",
            confidence=0.6
        )
        if pref_id:
            prefs_set["cadence"] = pref_id
            logger.info(f"Updated preference: explore_cadence_minutes=90 ({pref_id})")
    elif skip_rate < 0.2:
        # User rarely skips; shorter cadence OK
        pref_id = learning_db.set_preference(
            "explore_cadence_minutes",
            30,
            source="learned",
            confidence=0.6
        )
        if pref_id:
            prefs_set["cadence"] = pref_id
            logger.info(f"Updated preference: explore_cadence_minutes=30 ({pref_id})")
    
    return prefs_set


def run_learner(verbose: bool = False) -> dict[str, Any]:
    """Run the learning loop: read new outcomes, infer skills/prefs, advance checkpoint."""
    result = {
        "status": "pending",
        "outcomes_processed": 0,
        "skills_created": {},
        "preferences_set": {},
        "checkpoint_advanced_from": None,
        "checkpoint_advanced_to": None,
        "error": None,
    }
    
    try:
        # Get checkpoint
        last_checkpoint = get_checkpoint()
        result["checkpoint_advanced_from"] = last_checkpoint
        
        if verbose:
            logger.info(f"Learning loop starting from checkpoint: {last_checkpoint}")
        
        # Read all outcomes (we'll filter by timestamp)
        all_outcomes = learning_db.get_outcome_summary(limit=1000)
        
        # Filter: only outcomes after checkpoint
        # Note: timestamps may have timezone info (Z or +00:00), compare strings
        def normalize_ts(ts: str) -> str:
            """Normalize timestamp for comparison (strip timezone if present)."""
            if ts and (ts.endswith('Z') or '+' in ts):
                return ts.split('+')[0].split('Z')[0]
            return ts
        
        norm_checkpoint = normalize_ts(last_checkpoint)
        new_outcomes = [
            o for o in all_outcomes
            if normalize_ts(o.get("timestamp_utc", "")) > norm_checkpoint
        ]
        
        result["outcomes_processed"] = len(new_outcomes)
        
        if not new_outcomes:
            result["status"] = "no_new_records"
            return result
        
        if verbose:
            logger.info(f"Processing {len(new_outcomes)} new outcomes")
        
        # Infer skills and preferences
        skills = process_outcomes_into_skills(new_outcomes)
        prefs = infer_preferences_from_outcomes(new_outcomes)
        
        result["skills_created"] = skills
        result["preferences_set"] = prefs
        
        # Advance checkpoint to now
        now = datetime.now(timezone.utc).isoformat()
        set_checkpoint(now)
        result["checkpoint_advanced_to"] = now
        result["status"] = "success"
        
        if verbose:
            logger.info(f"Learning loop completed: {len(skills)} skills, {len(prefs)} prefs")
        
        return result
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error(f"Learning loop failed: {e}")
        return result


def get_learner_summary() -> dict[str, Any]:
    """Get a quick summary of learned state (for Morning Brief)."""
    try:
        skills = learning_db.get_skill_summary(limit=10)
        prefs = learning_db.get_preferences(source="learned")
        checkpoint = get_checkpoint()
        
        return {
            "checkpoint": checkpoint,
            "learned_skills_count": len(skills),
            "learned_preferences_count": len(prefs),
            "top_skills": [
                {
                    "name": s.get("skill_name"),
                    "confidence": s.get("confidence", 0.0),
                    "signal_strength": s.get("signal_strength", 0),
                }
                for s in skills[:3]
            ],
            "learned_prefs": {k: v for k, v in prefs.items()},
        }
    except Exception as e:
        logger.error(f"Failed to get learner summary: {e}")
        return {
            "checkpoint": None,
            "learned_skills_count": 0,
            "learned_preferences_count": 0,
            "error": str(e),
        }


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s"
    )
    
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    result = run_learner(verbose=verbose)
    
    if result["status"] == "success":
        print(f"✅ Learning loop completed")
        print(f"   Outcomes processed: {result['outcomes_processed']}")
        print(f"   Skills created: {len(result['skills_created'])}")
        print(f"   Preferences set: {len(result['preferences_set'])}")
        print(f"   Checkpoint: {result['checkpoint_advanced_from']} → {result['checkpoint_advanced_to']}")
    elif result["status"] == "no_new_records":
        print(f"⏭️  No new outcomes since checkpoint ({result['checkpoint_advanced_from']})")
    else:
        print(f"❌ Learning loop failed: {result['error']}")
        sys.exit(1)
