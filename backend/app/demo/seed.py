"""
CLI script for seeding deterministic demo data in RecoverAI.

Usage:
    python -m app.demo.seed [--scenario SCENARIO] [--count COUNT] [--seed SEED] [--reset]
"""

import argparse
import sys

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.demo.service import DemoService


def main() -> None:
    """CLI entrypoint for seeding demo data."""
    settings = get_settings()

    parser = argparse.ArgumentParser(description="RecoverAI Demo Data Seeder")
    parser.add_argument(
        "--scenario",
        type=str,
        default="all",
        choices=["all", "success", "human_review", "retry", "failure", "blocked", "multi_channel", "high_volume"],
        help="Demo scenario to execute (default: all)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of synthetic cases to generate (default: 50)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=settings.DEMO_SEED or 42,
        help="Random seed for deterministic generation (default: 42)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset existing data before seeding",
    )

    args = parser.parse_args()

    print(f"[*] RecoverAI Demo Data Seeder")
    print(f"[*] Scenario: {args.scenario} | Count: {args.count} | Seed: {args.seed} | Reset: {args.reset}")
    print(f"[*] Environment: {settings.ENVIRONMENT} | Demo Mode: {settings.DEMO_MODE}")

    if not settings.DEMO_MODE:
        print("[!] ERROR: DEMO_MODE is disabled. Cannot seed data in production mode.")
        sys.exit(1)

    db = SessionLocal()
    try:
        if args.scenario != "all":
            print(f"[*] Running specific scenario: {args.scenario}...")
            res = DemoService.run_scenario(db, scenario_id=args.scenario, seed=args.seed)
            print(f"[+] Scenario completed: {res.scenario_name}")
            print(f"    Message: {res.message}")
            print(f"    Case State: {res.case_state} | Approval: {res.approval_status} | Job: {res.job_status}")
        else:
            print(f"[*] Generating synthetic dataset...")
            res = DemoService.seed_data(db, count=args.count, seed=args.seed, reset=args.reset)
            print(f"[+] Seeding completed successfully!")
            print(f"    Payments: {res.payments_created}")
            print(f"    Cases: {res.cases_created}")
            print(f"    Approvals: {res.approvals_created}")
            print(f"    Jobs: {res.jobs_created}")
            print(f"    Total Recoverable: ₹{res.total_recoverable_amount / 100:,.2f}")
            print(f"    Total Recovered: ₹{res.total_recovered_amount / 100:,.2f}")
            print(f"    {res.message}")
    except Exception as e:
        print(f"[!] Error during demo seeding: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
