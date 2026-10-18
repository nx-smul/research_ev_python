#!/usr/bin/env python3
"""Verification script for the EVCS optimizer rewrite.

This script validates that all refactored modules import correctly and that
the new architecture is properly structured.
"""

import sys
import ast
from pathlib import Path


def check_python_syntax():
    """Verify all Python files parse without syntax errors."""
    print("=" * 70)
    print("CHECKING PYTHON SYNTAX")
    print("=" * 70)

    files = list(Path('src').rglob('*.py')) + [Path('main.py')]
    ok = fail = 0

    for f in sorted(files):
        try:
            with open(f) as fh:
                ast.parse(fh.read())
            ok += 1
        except SyntaxError as e:
            print(f"✗ {f}:{e.lineno}: {e.msg}")
            fail += 1

    print(f"\nResult: {ok}/{ok+fail} files parse OK")
    return fail == 0


def check_imports():
    """Verify all modules import correctly."""
    print("\n" + "=" * 70)
    print("CHECKING MODULE IMPORTS")
    print("=" * 70)

    sys.path.insert(0, '.')

    checks = [
        ("Core infrastructure", [
            "src.core.exceptions",
            "src.core.geo_utils",
            "src.core.paths",
            "src.core.run_context",
        ]),
        ("Pipeline stages", [
            "src.stages.preflight",
            "src.stages.spatial_ranking",
            "src.stages.road_network",
            "src.stages.optimization",
            "src.stages.grid_analysis",
            "src.stages.visualization",
            "src.stages.reporting",
        ]),
        ("Research extensions", [
            "src.optimization.extensions.uncertainty",
            "src.optimization.extensions.equity",
            "src.optimization.extensions.time_profiles",
            "src.optimization.extensions.queueing",
            "src.optimization.extensions.grid_upgrade",
            "src.optimization.extensions.field_validation",
            "src.optimization.extensions.investment",
        ]),
        ("Main modules", [
            "src.config",
            "src.pipeline",
            "src.data_generator",
        ]),
    ]

    all_ok = True
    for category, modules in checks:
        print(f"\n{category}:")
        for module in modules:
            try:
                __import__(module)
                print(f"  ✓ {module}")
            except Exception as e:
                print(f"  ✗ {module}: {e}")
                all_ok = False

    return all_ok


def check_file_structure():
    """Verify the new directory structure exists."""
    print("\n" + "=" * 70)
    print("CHECKING FILE STRUCTURE")
    print("=" * 70)

    required_dirs = [
        "src/core",
        "src/stages",
        "src/optimization/extensions",
        "web/src/hooks",
        "web/src/components",
    ]

    all_ok = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists() and path.is_dir():
            file_count = len(list(path.glob('*.py')) + list(path.glob('*.js')) + list(path.glob('*.jsx')))
            print(f"✓ {dir_path}/ ({file_count} files)")
        else:
            print(f"✗ {dir_path}/ (missing)")
            all_ok = False

    return all_ok


def check_key_functions():
    """Verify key functions are accessible."""
    print("\n" + "=" * 70)
    print("CHECKING KEY FUNCTIONS")
    print("=" * 70)

    sys.path.insert(0, '.')

    checks = [
        ("Pipeline", "src.pipeline", ["run_full_pipeline", "validate_real_data_inputs"]),
        ("Config", "src.config", ["load_config", "validate_config"]),
        ("Core utils", "src.core.geo_utils", ["haversine_distance_m", "bpr_travel_time"]),
        ("Core paths", "src.core.paths", ["PathManager"]),
        ("Core context", "src.core.run_context", ["RunContext"]),
    ]

    all_ok = True
    for category, module, functions in checks:
        print(f"\n{category}:")
        try:
            mod = __import__(module, fromlist=functions)
            for func in functions:
                if hasattr(mod, func):
                    print(f"  ✓ {func}")
                else:
                    print(f"  ✗ {func} (not found)")
                    all_ok = False
        except Exception as e:
            print(f"  ✗ Module import failed: {e}")
            all_ok = False

    return all_ok


def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("EVCS OPTIMIZER REWRITE VERIFICATION")
    print("=" * 70)

    results = {
        "Python syntax": check_python_syntax(),
        "Module imports": check_imports(),
        "File structure": check_file_structure(),
        "Key functions": check_key_functions(),
    }

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check}")

    all_passed = all(results.values())

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL CHECKS PASSED")
        print("=" * 70)
        print("\nThe rewrite is complete and verified. All modules import correctly,")
        print("all files parse without errors, and the new architecture is in place.")
        return 0
    else:
        print("✗ SOME CHECKS FAILED")
        print("=" * 70)
        print("\nPlease review the errors above and fix any issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
