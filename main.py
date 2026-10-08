"""Main Command-Line Interface (CLI) entrypoint for Dhaka EVCS research project."""

import argparse
import os
import sys

from src.pipeline import RealDataPreflightError, run_full_pipeline
from src.data_generator import generate_all_data


def main():
    """Main CLI entrypoint for Dhaka EVCS research project."""
    parser = argparse.ArgumentParser(
        description="Optimal Electric Vehicle Charging Station (EVCS) Placement & Grid Impact Analysis."
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["full", "data"],
        default="full",
        help="Execution mode: 'data' explicitly generates SYNTHETIC demo datasets; 'full' runs the pipeline (real inputs required unless --data-mode demo)."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/default_config.yaml",
        help="Path to YAML configuration file (only used in 'full' mode)."
    )
    parser.add_argument(
        "--settings",
        type=str,
        default="configs/user_settings.yaml",
        help="Partial YAML settings file merged over --config (default: configs/user_settings.yaml)."
    )
    parser.add_argument(
        "--data-mode",
        choices=["real", "demo"],
        default="real",
        help="Input mode for full pipeline: real requires provenance-verified sources; demo explicitly generates synthetic benchmark data.",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=None,
        help="Optional NSGA-II generation override (otherwise uses YAML settings)."
    )
    parser.add_argument(
        "--population",
        type=int,
        default=None,
        help="Optional NSGA-II population override (otherwise uses YAML settings)."
    )
    parser.add_argument(
        "--sensitivity",
        action="store_true",
        help="Run additional demand, budget, and service-radius sensitivity scenarios.",
    )

    args = parser.parse_args()
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if args.mode == "data":
        print("Generating SYNTHETIC demo datasets only; these are not real observations or official data.")
        generate_all_data(base_dir)
        print("Synthetic demo datasets generated successfully.")
    elif args.mode == "full":
        print(f"Running full pipeline with config: {args.config}")
        if args.settings:
            print(f"  User settings: {args.settings}")
        try:
            run_full_pipeline(
                args.config,
                settings_path=args.settings,
                generations=args.generations,
                population=args.population,
                base_dir=base_dir,
                data_mode=args.data_mode,
                sensitivity=args.sensitivity,
            )
        except RealDataPreflightError as exc:
            parser.error(f"{exc}\nRun `python main.py --data-mode demo` for synthetic demonstration data.")
    else:
        parser.error(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    main()
