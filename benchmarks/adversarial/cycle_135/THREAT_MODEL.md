# THREAT_MODEL — vary-parse (cycle_135)

Cycle: 135
Repo: vary-parse v0.1.0
Commit under audit: 48ba168

## TM1 — System context

`vary-parse` is a **stateless Python library** plus a **CLI** that converts
HTTP response `Vary` header values into a parsed structure, and optionally
into a cache-key fragment given a request-header map. It is intended to be
embedded inside an HTTP cache, CDN edge node, reverse proxy, or web server
test harness. Per the SPEC it has zero runtime dependencies and ships with
a typed module (`py.typed`).

The repo's own README is the primary deployment story: a developer pulls
this in via `pip install git+https://github.com/.../vary-parse.git` and
calls `parse_vary(vary_header_string)` on bytes received from a network
peer, or runs the CLI as a debugging aid.

There is no separate daemon, no network listener, no persistent storage.

## TM2 — Attacker model

### TM2.1 — Direct attacker (network-adjacent)

A remote party who can inject HTTP response headers into the victim's
input stream. This is realistic because:
- `Vary` is an HTTP **response** header. A successful MITM, a compromised
  origin server, a hostile CDN upstream, or a request smuggling
  accomplice could feed arbitrary bytes into the parser.
- The Vary header is typically read by an HTTP cache that does not
  authenticate upstream responses (trust on first use; TLS only).

Capabilities:
- Choose any string up to the upstream-imposed header-size limit
  (typically 8 KiB to 16 KiB).
- Choose the number of comma-separated fields (zero to ~header_size/2).
- Insert any byte sequence — including NULs, control characters, CRLF,
  DEL, multi-byte UTF-8.
- Repeat header values across multiple requests.

What the attacker CANNOT do:
- Hold a TCP connection open arbitrarily (timeout enforced by the HTTP
  server, not by vary-parse).
- Cause the parser to read more bytes than the header-size cap permits
  (enforced upstream of vary-parse).

### TM2.2 — Local-library caller

A developer using vary-parse as a Python library. Less likely to be
malicious but might pass:
- `None`, integers, lists, dicts (should raise `TypeError`).
- Bytes (a common mistake when reading from a socket — `socket.recv`
  returns `bytes`).
- Surrogate-half strings (`"\udcff"`) — Python permits these in `str`.
- Pre-decoded UTF-8 with NULs or control chars.

### TM2.3 — CLI user

A shell user invoking `vary-parse --parse "..."`. The value is parsed by
`argparse` which guarantees it is a `str` and does not invoke a shell.
The attack surface here is "script kiddie" — a malicious file containing
the string `--parse "value"` is not a threat.

## TM3 — Worst-case impact analysis

For each attack class, the worst-case outcome if vary-parse failed:

| Class | Worst-case if mishandled | Likelihood given current impl |
|---|---|---|
| 1. Massive field lists | CPU/memory exhaustion (DoS) | Low — `parse_vary` is O(n) over tokens; 10k-field test exists |
| 2. 1 MiB single token | OOM | Low — same; pre-allocated `str` is bounded by upstream header cap |
| 3. Non-string type confusion | `AttributeError` → uncaught exception → service crash | None — explicit `TypeError` raised and tested (Cat-H) |
| 4. CRLF / binary chars | Header smuggling, response splitting downstream | Low — `parse_vary` keeps raw bytes in a tuple; serializer joins with `, ` (no CRLF re-emission); see TM4.3 |
| 5. Empty/whitespace | Logic bug → cache-key always present → cache poisoning | Mitigated — `Vary((), False)` returned, `vary_cache_key` returns `{}` (tested Cat-G) |
| 6. CLI injection | RCE | None — no shell, no subprocess |
| 7. JSON escape | Invalid JSON | None — `json.dumps` escapes control chars by default |
| 8. Cache-key type confusion | `AttributeError` → service crash | None — `TypeError` raised (tested Cat-H) |
| 9. Unicode normalization | Cache miss / cache hit mismatch | Low — case-insensitive lookup is `str.lower()` only; no NFC/NFD normalization; see TM4.4 |
| 10. Wildcard precedence | Cache miss → cache poisoning | Mitigated — `*, Accept` → `Vary((), True)` → no cache (tested Cat-B) |
| 11. Case preservation | Cache miss | By design — original case preserved in output (tested Cat-D) |
| 12. Empty entries | Cache miss | Mitigated — empty entries dropped (tested Cat-E) |

## TM4 — Notable threat discussions

### TM4.1 — ReDoS resistance

The single regex in the source, `_TOKEN_RE` (`_vary_parse.py:25`), is a
flat character class `[!#$%&'*+\-.^_`|~0-9A-Za-z]+`. This is one of the
safest regex shapes: a single character class with a single quantifier
(no nesting, no alternation). Python's `re` engine compiles this to a
linear state machine in CPython. It is invoked via `re.fullmatch` which
anchors both ends and backtracks at most once on a no-match. **ReDoS is
structurally impossible.**

A more dangerous regex would look like `^[A-Za-z]+(A+)+$` (nested
quantifier). We have none of those.

### TM4.2 — Linear-time guarantee

`parse_vary` performs:
- One `str.strip()` — O(n) over input length.
- One `str.replace("\t", " ")` — O(n).
- One `str.split(",")` — O(n).
- One `chunk.strip()` per chunk — O(n).
- One `_TOKEN_RE.fullmatch(p)` per chunk — O(len(p)).
- One `any(...)` and one `all(...)` over chunks — O(num_chunks).

Sum: O(n) time, O(num_chunks) memory.

For an n-byte input the parser visits each byte a constant number of
times. **No quadratic behavior is possible from the implementation.**
The risk would be Python interpreter overhead in pathological cases (e.g.
millions of tiny comma-separated tokens), but the implementation never
revisits or copies chunks unnecessarily.

### TM4.3 — CRLF and response splitting

`parse_vary` accepts `\r` and `\n` inside a token chunk as ordinary bytes
because they are not in the token ABNF (RFC 9110 §5.6.2), so the
`_TOKEN_RE.fullmatch` check rejects them and the chunk is dropped
(`_vary_parse.py:86-91`). This means an attacker cannot smuggle CRLF
**into** the parsed `field_names` tuple.

The serializer (`serialize_vary`) joins with `, ` (`:107`), which
contains neither CR nor LF. So even a malicious Vary that somehow
contained CRLF would not re-emit it via `serialize_vary`. **Response
splitting via the Vary round-trip is impossible.**

The CLI's `--json` mode uses `json.dumps` which by default escapes
control characters (`json.dumps('"\u0000"')` → `"\"\\u0000\""`). So JSON
output is safe.

### TM4.4 — Unicode normalization (NFC vs NFD)

RFC 9110 §5.6.2 defines the token ABNF in terms of tchar (a set of
specific ASCII bytes). Vary field names are ASCII-only by construction.
However, RFC 9110 §5.5 allows field names with non-ASCII bytes when
received over the wire, but treats them as opaque bytes for cache key
purposes.

Our implementation uses Python `str.lower()` for case-insensitive
comparison (`_vary_parse.py:150`). This is **codepoint-based**, not
locale-aware, and does not perform NFC/NFD normalization. So
`parse_vary("Café")` (NFD, "Cafe\u0301") and `parse_vary("Café")` (NFC,
single codepoint) are considered **different** field names — they will
not collide in the cache key.

This is a known limitation: a hostile origin could pick a normalization
form that causes cache lookups to miss. However:
1. The HTTP cache key is determined by what the **request** sends, not
   what the origin chooses; both forms are equally cacheable.
2. The SPEC §4 explicitly defines field-name matching as
   case-insensitive on `str.lower()` only — NFC/NFD is **not** a
   documented requirement.
3. HTTP field names are ASCII per RFC 9110 §5.6.2 in any practical
   deployment; non-ASCII header names are undefined behavior territory.

**Status: Info, not a defect.** Recorded for future SPEC update if
real-world attackers exploit it.

### TM4.5 — `vary_cache_key` request_headers trust

The function accepts an arbitrary `Mapping[str, str]` (`_vary_parse.py:142`).
A malicious caller could pass a `Mapping` whose `.items()` yields objects
whose values are not strings (e.g., bytes, ints). The `v = lower_map.get(name.lower())`
line (`:150`) would put that non-string value into the output dict.
The subsequent `out[f"vary_{name.lower()}"] = v` (`:152`) does not
type-check `v`. The output `dict[str, str]` annotation is **not enforced
at runtime** — Python `dict[str, str]` is purely static.

If a downstream consumer (e.g., a JSON serializer) then iterates the
dict and tries `str(v)`, the value will be silently stringified. If the
consumer tries to write the value to a cache backend that expects
bytes, the backend may raise.

**Status: Low.** A future iteration could add `isinstance(v, str)` checks
in `vary_cache_key`. For now this is a documented trust boundary: callers
must pass real string values. The function is internal to the HTTP cache
codebase; the threat is mis-integration, not malicious input.

### TM4.6 — Mapping key type

`vary_cache_key` calls `request_headers.items()` (`:148`) without type
checking the keys. If a caller passes a `Mapping[int, str]` (unusual but
legal), `key.lower()` will raise `AttributeError`. The function does NOT
catch this — it propagates.

**Status: Info.** Callers are expected to pass `Mapping[str, str]`. The
type signature says so. No malicious surface — just sloppy-caller defense.

## TM5 — Trust-boundary summary

| Boundary | Direction | Trust |
|---|---|---|
| Bytes on the wire → caller | Inbound | Untrusted |
| Caller → `parse_vary` | Inbound | Untrusted (must be `str`) |
| Caller → `vary_cache_key` | Inbound | Untrusted (must be `Mapping[str, str]`) |
| `parse_vary` → caller | Outbound | Trusted shape (`Vary` NamedTuple) |
| `serialize_vary` → caller | Outbound | Trusted string, no CRLF |
| `vary_cache_key` → caller | Outbound | Trusted shape (`Optional[dict[str, str]]`) |
| `vary_parse` package → user module | Import | No side effects on import (verified — `__init__.py` is re-exports only) |

## TM6 — Adversarial playbook (what T2 harnesses will exercise)

Card 02 (harnesses) must hit at least these:

1. `core_parse` — fuzz `parse_vary` with random `str` of length 0–10,000.
   Assert no crash, return value is `Vary`, time < 100 ms.
2. `core_serialize` — fuzz `serialize_vary` with random `Vary` instances
   (including 10,000-field tuples). Assert round-trip stability.
3. `core_cache_key` — fuzz `vary_cache_key` with random `Vary` and random
   `dict[str, str]` of varying sizes.
4. `cli_parse` — subprocess-invoke `vary-parse --parse` with random
   strings, assert exit 0 + CSV output shape.
5. `cli_json` — subprocess-invoke `vary-parse --json` with strings
   containing control chars; assert JSON output is parseable.
6. `cli_cache_key` — subprocess-invoke `vary-parse --cache-key` with
   malformed `name=value` pairs; assert exit 2.
7. `cli_injection` — pass shell metas as `--parse` value; assert no
   shell effects (argv isolation).
8. `wildcard_precedence` — random fuzz around `*`-bearing inputs.
9. `massive_input` — 1 MiB single token + 10,000-field list. Time-bounded.
10. `unicode_edge` — NFD/NFC pairs, surrogate halves, very high
    codepoints.
