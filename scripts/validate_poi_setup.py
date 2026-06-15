#!/usr/bin/env python3
"""
Validate POI Provider Setup for Explore Mode

This script checks:
- Which providers are configured and available
- What environment variables are needed
- Whether the POI API scaffolding is properly wired

Safe to run; reports only, no changes made.
"""

import sys
from pathlib import Path

# Add second_brain to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    print("=" * 70)
    print("PersGraph POI Provider Setup Validation")
    print("=" * 70)
    print()

    # Check POI provider availability
    print("📍 POI Provider Status")
    print("-" * 70)
    try:
        from second_brain.poi_provider import (
            get_registry,
            validate_provider_config,
        )

        registry = get_registry()
        config = validate_provider_config()

        for provider_name, info in config.items():
            if provider_name == "primary":
                continue

            status = "✓" if info.get("available") else "✗"
            msg = info.get("status", "unknown")
            print(f"{status} {provider_name.upper():15} — {msg}")

            if "config_key" in info:
                print(f"   Set via: {info['config_key']}")

        print()
        primary = config.get("primary")
        print(f"Primary provider: {primary or 'NONE (fallback only)'}")
        print()

    except Exception as e:
        print(f"✗ Error checking providers: {e}")
        return 1

    # Check Explore Mode integration
    print("🗺 Explore Mode Integration")
    print("-" * 70)
    try:
        from second_brain.explore_poi import check_explore_config, get_missing_env_vars

        missing = get_missing_env_vars()
        if missing:
            print("Missing environment variables:")
            for var in missing:
                print(f"  - {var}")
        else:
            print("✓ All recommended env vars are configured")

        print()

    except Exception as e:
        print(f"✗ Error checking explore integration: {e}")
        return 1

    # Check places_db availability (local fallback)
    print("💾 Local Fallback (places_db)")
    print("-" * 70)
    try:
        from second_brain import places_db

        count = places_db.count()
        cities = places_db.cities()
        print(f"✓ places_db available")
        print(f"   Saved places: {count}")
        if cities:
            print(f"   Cities: {', '.join(cities[:5])}" + ("..." if len(cities) > 5 else ""))
        print()

    except ImportError:
        print("✗ places_db not available (local fallback will use empty DB)")
        print()
    except Exception as e:
        print(f"✗ Error checking places_db: {e}")
        print()

    # Files summary
    print("📁 Required Files")
    print("-" * 70)
    files_to_check = [
        ("second_brain/poi_provider.py", "POI Provider abstraction"),
        ("second_brain/explore_poi.py", "Explore Mode POI integration"),
        ("scripts/explore_mode.py", "Explore Mode core logic"),
        ("data/explore_state.json", "Explore Mode state (created on first run)"),
    ]

    for rel_path, description in files_to_check:
        full_path = ROOT / rel_path
        status = "✓" if full_path.exists() else "✗"
        print(f"{status} {rel_path:40} — {description}")

    print()
    print("=" * 70)
    print("✅ POI scaffolding ready. Next steps:")
    print()
    print("1. Set GOOGLE_MAPS_API_KEY in .env (optional, enables Maps API)")
    print("2. Test with: python scripts/explore_mode.py --status")
    print("3. Enable Explore Mode with: /TripToggle On")
    print("4. Monitor: tail -f data/explore_audit.json")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
