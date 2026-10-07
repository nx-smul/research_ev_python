"""Main Command-Line Interface (CLI) entrypoint for Dhaka EVCS research project."""

import argparse
import os
import sys

from src.pipeline import run_full_pipeline
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
        help="Execution mode: 'data' generates raw/processed datasets, 'full' runs the complete pipeline."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/default_config.yaml",
        help="Path to YAML configuration file (only used in 'full' mode)."
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=50,
        help="Number of NSGA-II generations (only used in 'full' mode)."
    )
    parser.add_argument(
        "--population",
        type=int,
        default=40,
        help="Population size for NSGA-II (only used in 'full' mode)."
    )

    args = parser.parse_args()
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if args.mode == "data":
        print("Generating datasets...")
        generate_all_data(base_dir)
        print("Datasets generated successfully!")
    elif args.mode == "full":
        print(f"Running full pipeline with config: {args.config}")
        print(f"  Generations: {args.generations}, Population: {args.population}")
        run_full_pipeline(args.config, generations=args.generations, population=args.population, base_dir=base_dir)
    else:
        parser.error(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    main()
