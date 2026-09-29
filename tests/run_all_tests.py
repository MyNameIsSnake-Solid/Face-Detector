import sys
import os
import subprocess
 
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
TESTS = [
    ("DATABASE ", "tests/test_database.py"),
    ("AUTH     ", "tests/test_auth.py"),
    ("EMBEDDING", "tests/test_embedding.py"),
    ("ROUTES   ", "tests/test_routes.py"),
]
 
def run_suite(name, path):
    print(f"\n{'═'*50}")
    print(f"  Running {name} tests...")
    print(f"{'═'*50}")
 
    result = subprocess.run(
        [sys.executable, path],
        capture_output=False
    )
 
    return result.returncode == 0
 
 
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════╗")
    print("║       FULL TEST SUITE RUNNER         ║")
    print("╚══════════════════════════════════════╝")
 
    passed = []
    failed = []
 
    for name, path in TESTS:
        success = run_suite(name, path)
        if success:
            passed.append(name.strip())
        else:
            failed.append(name.strip())
            print(f"\n  ✗ {name.strip()} tests FAILED — stopping here")
            print("    Fix errors above before running the next suite.\n")
            break
 
    print(f"\n{'═'*50}")
    print(f"  RESULTS")
    print(f"{'═'*50}")
    for name in passed:
        print(f"  ✓  {name}")
    for name in failed:
        print(f"  ✗  {name}")
 
    if not failed:
        print(f"\n  All {len(passed)} test suites passed!")
        print("  Backend is ready — move on to the frontend.\n")
    else:
        print(f"\n  {len(failed)} suite(s) failed. Fix before proceeding.\n")
        sys.exit(1)