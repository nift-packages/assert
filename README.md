# assert

Lightweight assertion and matcher helpers for Nift scripts and package tests.

`assert` is a pure, no-process package. It exists so Nift scripts and package
test files can stop re-implementing a local `fn(expect(condition, label))` that
"aborts with `missing.value`" and instead use a small, consistent matcher
surface with deterministic diagnostics.

## Installation

```text
nift add nift-packages/assert
```

## Import

```text
@import("assert")
```

## API

```text
assert.ok(value, message?)
assert.falsy(value, message?)
assert.eq(actual, expected, message?)
assert.ne(actual, expected, message?)
assert.is_null(value, message?)
assert.not_null(value, message?)
assert.contains(container, value, message?)
assert.throws(callable, message?)
```

Every matcher returns `true` on success. Every matcher accepts one optional
trailing `message?` that is appended to the failure diagnostic.

```text
@import("assert")

assert.eq(url.parse("https://a/b").path, "/b")
assert.contains(["b", "c"], "b")
fn(boom()) { throw error("expected") }
assert.throws(boom)
```

## Naming note

Nift reserves `false` and `null` as identifiers, so they cannot be used as
method names. This package therefore provides `falsy` (assert a value is
falsy) and `is_null` (assert a value is null) instead of `assert.false(...)`
and `assert.null(...)`.

## Failure model

A failed assertion throws an Error via Nift's `throw` statement. In an ordinary
script that aborts the script with a non-zero exit code and a deterministic
diagnostic on stderr, for example:

```text
error: script.f:3:1: assert.eq failed: expected 1 == 2: message
```

Callers may also catch the failure with Nift's `try { ... } catch (e) { ... }`;
`e.message` holds the same diagnostic text.

`throws(callable)` calls the callable inside a try/catch and returns true if an
error was raised, otherwise it throws `assert.throws failed: callable did not
raise an error`. Nift's `catch` handles explicitly thrown errors and recoverable
operation failures; it does not intercept fatal immediate script errors such as
a division by zero, so `assert.throws` is only guaranteed for callables that
fail by throwing (or by a recoverable error).

## Equality and truthiness

`eq`/`ne` use Nift's `==`, which deep-compares arrays, objects and bytes, so
structural equality is asserted for JSON-shaped values. Truthiness matches
Nift's `if` semantics: falsy means `null`, `false`, `0`, `""`, and empty
arrays/objects.

`contains` checks:

```text
string   contains value as a substring
array    contains an element equal to value
object   has value as a key
```

## Diagnostics

Compared values are rendered with `stringify()` and truncated to 200 characters
per value, so huge structures produce a bounded message rather than a dump.

## Limits and robustness

Matchers validate their arguments and throw a deterministic failure for wrong
argument types (for example `assert.contains(42, "x")`). There are no
configurable options objects and no documented resource limits beyond the
diagnostic truncation cap.

## Tests

```sh
python3 -B tests/test_assert.py /path/to/nift
```

The suite verifies every success and failure path from outside the package
(including abort diagnostics on stderr and catchable failures), optional
messages, deep equality, truncation, determinism, privacy and a bounded deep
equality performance check.

Version: 0.1.0