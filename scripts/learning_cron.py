#!/usr/bin/env python3
"""
Scheduled learning loop for PersGraph.

Meant to be called via cron every 15–60 minutes:
  */15 * * * * cd /root/AgenticHub/Persgraph && PYTHONPATH=. .venv/bin/python scripts/learning_cron.py

Safe to run multiple times (checkpoint ensures no reprocessing).
"""

import sys
import os
import logging

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Setup logging
log_dir = os.path.join(BASE_DIR, "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(log_dir, "learning_cron.log"), mode="a")
    ]
)
logger = logging.getLogger(__name__)

try:
    from second_brain.learning_learner import run_learner
    
    logger.info("Starting learning cron job")
    result = run_learner(verbose=False)
    
    if result["status"] == "success":
        logger.info(
            f"Learning loop completed: "
            f"{result['outcomes_processed']} outcomes, "
            f"{len(result['skills_created'])} skills, "
            f"{len(result['preferences_set'])} prefs"
        )
    elif result["status"] == "no_new_records":
        logger.debug(f"No new outcomes to process")
    else:
        logger.error(f"Learning loop error: {result['error']}")
        sys.exit(1)
        
except Exception as e:
    logger.exception(f"Learning cron job crashed: {e}")
    sys.exit(1)
