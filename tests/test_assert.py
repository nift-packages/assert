#!/usr/bin/env python3
"""Certification tests for the assert Nift package.

Failures are verified from outside the package: failed assertions abort the
Nift script (non-zero exit) with a deterministic diagnostic on stderr, and can
also be caught with Nift's try/catch. The harness drives both paths.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

NIFT = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/nick/Repositories/nift/nift/nift").resolve()
PACKAGE = Path(__file__).resolve().parent.parent
TESTS = PACKAGE / "tests"
SOURCE = PACKAGE / "src" / "assert.f"

manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
if manifest != {"name": "assert", "version": "0.1.0", "entry": "src/assert.f",
                "description": "Lightweight assertion and matcher helpers for Nift"}:
    raise SystemExit(f"FAIL unexpected package manifest: {manifest!r}")

source = SOURCE.read_text(encoding="utf-8")
exports = re.findall(r"^export\(([^)]+)\)$", source, re.MULTILINE)
public_methods = re.findall(r"^    fn\(([A-Za-z_][A-Za-z0-9_]*)\(", source, re.MULTILINE)
expected_public = ["ok", "falsy", "eq", "ne", "is_null", "not_null", "contains", "throws"]
if exports != ["assert"] or public_methods != expected_public:
    raise SystemExit(f"FAIL unexpected public surface: exports={exports!r} methods={public_methods!r}")


def require(condition, message, result=None):
    if condition:
        return
    if result is not None:
        message += f"\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}\nreturn code: {result.returncode}"
    raise SystemExit("FAIL " + message)


def qs(text):
    return json.dumps(text, ensure_ascii=False)


def run(args, cwd):
    return subprocess.run([str(NIFT), *args], cwd=cwd, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=60, check=False)


WORK = Path(tempfile.mkdtemp(prefix=".assert-tests-", dir=TESTS))
try:
    consumer = WORK / "consumer"
    consumer.mkdir()
    (consumer / ".nift").mkdir()
    added = run(["add", str(PACKAGE)], consumer)
    require(added.returncode == 0, "nift add into fresh consumer failed", added)

    def run_script(name, body, use_stderr=False):
        (consumer / name).write_text(body, encoding="utf-8")
        return run([name], consumer)

    # 1. All success paths.
    success = """@import("assert")
assert.ok(true)
assert.ok(1)
assert.ok("x")
assert.falsy(false)
assert.falsy(0)
assert.falsy("")
assert.falsy(null)
assert.eq(1, 1)
assert.eq(1.0, 1.0)
assert.eq("é😀", "é😀")
assert.eq([1, 2, {"a": 3}], [1, 2, {"a": 3}])
assert.ne(1, 2)
assert.is_null(null)
assert.not_null("x")
assert.contains("hello world", "world")
assert.contains([1, 2, 3], 2)
assert.contains({"a": 1}, "a")
fn(boom()) { throw error("inner boom") }
assert.throws(boom)
print("PASS")
"""
    res = run_script("success.f", success)
    require(res.returncode == 0 and res.stdout.strip() == "PASS",
            "success paths failed", res)

    # 2. Each failure path aborts with a deterministic diagnostic.
    failure_cases = [
        ("ok.f", '@import("assert")\nassert.ok(false)\n', "assert.ok failed"),
        ("ok-msg.f", '@import("assert")\nassert.ok(0, "custom ok message")\n', "custom ok message"),
        ("falsy.f", '@import("assert")\nassert.falsy(1)\n', "assert.falsy failed"),
        ("eq.f", '@import("assert")\nassert.eq(1, 2)\n', "assert.eq failed: expected 1 == 2"),
        ("eq-msg.f", '@import("assert")\nassert.eq([1], [2], "custom eq message")\n', "custom eq message"),
        ("eq-deep.f", '@import("assert")\nassert.eq({"a": [1]}, {"a": [2]})\n', "assert.eq failed"),
        ("ne.f", '@import("assert")\nassert.ne(5, 5)\n', "assert.ne failed"),
        ("isnull.f", '@import("assert")\nassert.is_null("x")\n', "assert.is_null failed"),
        ("notnull.f", '@import("assert")\nassert.not_null(null)\n', "assert.not_null failed"),
        ("contains-str.f", '@import("assert")\nassert.contains("hello", "nope")\n', "assert.contains failed"),
        ("contains-arr.f", '@import("assert")\nassert.contains([1, 2], 9)\n', "assert.contains failed"),
        ("contains-obj.f", '@import("assert")\nassert.contains({"a": 1}, "b")\n', "assert.contains failed"),
        ("contains-type.f", '@import("assert")\nassert.contains(42, "x")\n', "assert.contains failed"),
        ("throws-none.f", '@import("assert")\nfn(nofail()) { return 1 }\nassert.throws(nofail)\n', "assert.throws failed"),
        ("throws-notcallable.f", '@import("assert")\nassert.throws(42)\n', "assert.throws failed"),
    ]
    for name, body, needle in failure_cases:
        res = run_script(name, body)
        require(res.returncode != 0, f"failure path {name} did not abort", res)
        require(needle in res.stderr, f"failure path {name} missing diagnostic {needle!r}", res)

    # 3. Failures are catchable (recoverable), including our own thrown errors.
    catchable = '@import("assert")\ntry { assert.ok(false, "boom") } catch(e) { print("caught " + e.message) }\n'
    res = run_script("catch.f", catchable)
    require(res.returncode == 0 and res.stdout.strip() == "caught assert.ok failed: expected a truthy value: boom",
            "failure was not catchable", res)

    # 4. throws passes when the callable throws (already covered) and returns
    #    the successful assertion result.
    throws_many = """@import("assert")
fn(a()) { throw error("a") }
fn(b()) { throw error("b") }
assert.throws(a)
assert.throws(b)
print("PASS")
"""
    res = run_script("throws.f", throws_many)
    require(res.returncode == 0 and res.stdout.strip() == "PASS", "throws paths failed", res)

    # 5. Message truncation is bounded (full value not dumped).
    longv = "verylongstring" * 30
    body = ('@import("assert")\n'
            'try { assert.eq(' + qs(longv) + ', "other") } catch(e) { print(e.message.length() < 260) }\n')
    res = run_script("trunc.f", body)
    require(res.returncode == 0 and res.stdout.strip() == "true",
            "diagnostic message not bounded", res)

    # 6. Determinism.
    res = run_script("det.f", '@import("assert")\ni := 0\nwhile(i < 30) { assert.eq(i, i); i += 1 }\nprint("done")\n')
    require(res.returncode == 0 and res.stdout.strip() == "done", "deterministic matching failed", res)

    # 7. Privacy.
    for helper in ["truthy", "brief", "trim", "fail"]:
        (consumer / "privacy.f").write_text(f'@import("assert")\nassert.{helper}("x")\n', encoding="utf-8")
        res = run(["privacy.f"], consumer)
        require(res.returncode != 0, f"private helper {helper} was accessible")
    (consumer / "privateglobal.f").write_text("@import(\"assert\")\nprint(assert_max_brief_chars)\n", encoding="utf-8")
    require(run(["privateglobal.f"], consumer).returncode != 0, "module global assert_max_brief_chars leaked")

    # 8. Performance sanity: deep equality on a large nested structure remains bounded.
    body = ('@import("assert")\n'
            'a := []\ni := 0\nwhile(i < 200) { a.push({"k": i}); i += 1 }\n'
            'assert.eq(a, a)\n'
            'j := 0\nwhile(j < 100) { assert.eq(a, a); j += 1 }\nprint("done")\n')
    start = time.time()
    res = run_script("perf.f", body)
    elapsed = time.time() - start
    require(res.returncode == 0 and res.stdout.strip() == "done", "deep equality workload failed", res)
    require(elapsed < 15.0, f"100 deep eq on 200-element arrays took {elapsed:.2f}s")

finally:
    shutil.rmtree(WORK, ignore_errors=True)

print("PASS assert package tests")