# Schedule Change Reconciler

A `nanoagent.plugin/v0001` plugin for this task:

> Reconstruct the final conference schedule after these announcements and
> corrections, and identify remaining conflicts.

The agent tracks cancellations, reinstatements, room moves, room swaps and
rescheduling across an ordered message history. Explicit UTC offsets determine
every instant. A separate deterministic verifier reconstructs the answer from
the original task input and checks the complete event table and conflict pairs.
All bundled conference data and identities are synthetic and original.

## Tools

| Tool | Input → output | Purpose |
|---|---|---|
| `normalize_interval` | `IntervalInput` → `IntervalOutput` | Convert an interval to UTC and calculate its duration in seconds |
| `find_schedule_conflicts` | `ScheduleInput` → `ConflictsOutput` | Check a candidate active schedule for every room or speaker collision |
| `replay_schedule` | `ReconcileInput` → `ReconcileOutput` | Replay the complete history deterministically for offline validation |

| Task | Runner | Tools available |
|---|---|---|
| `reconcile-schedule` | `agent` | `normalize_interval`, `find_schedule_conflicts` |
| `replay-schedule` | `tool` | `replay_schedule` |

`reconcile-schedule` is the benchmark task. Its agent must reconstruct the state
itself; it cannot call the full replay tool. The two helpers calculate times and
conflicts for the candidate the agent supplies. The final verifier always uses
the original history, so a self-consistent but incorrect candidate fails.
Both tasks have `reference: null`; the verifier does not trust a tool's answer
as ground truth. `replay-schedule` exercises the same input and output contract
without model credentials and provides a repeatable integration check.

### Inputs and announcement language

`ReconcileInput` contains `initial_events` and `messages`. Every initial event has
`event_id`, `title`, `room`, `speakers`, `start`, and `end`. Every message has a
unique `message_id` and a `text` containing exactly one supported sentence:

```text
Cancel EVENT.
Reinstate EVENT.
Move EVENT to room ROOM.
Swap rooms of EVENT and OTHER.
Reschedule EVENT to START through END.
```

Any sentence may have the exact prefix `Correction: `:

```text
Correction: Reschedule E02 to 2026-11-02T20:00:00+05:30 through 2026-11-02T21:00:00+05:30.
```

Capitalization, single spaces and the final period are required. The syntax
intentionally makes every message unambiguous and mechanically verifiable.
Arbitrary prose, quoted replies, undo commands and inferred time zones are outside
this task. Use the typed input in [example.json](tests/fixtures/example.json)
or [long-history.json](tests/fixtures/long-history.json) as an executable example.

### Replay rules

- Initial events are active. Event, room, speaker and message IDs are case-sensitive
  and match `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`. Event IDs and message IDs are unique
  in their respective lists. Speaker IDs are unique within each event; an empty
  speaker list is valid. Titles must contain a non-whitespace character.
- **Message list order is authoritative.** IDs are labels, never sorting keys.
  The fixtures deliberately use message IDs out of chronological order.
- A correction applies at its own list position. It replaces only its named
  fields; it does not retroactively delete or rerun an earlier message. Later
  assignments to a field win. Every earlier message must still be valid.
- A room move changes only the room. A room swap exchanges the two current rooms
  simultaneously. The events must be distinct and known; their times, titles and
  speakers stay associated with their original event IDs. Equal-room swaps are valid.
- Rescheduling replaces both endpoints, preserving all other fields. Both the
  initial interval and every intermediate replacement must be valid.
- Cancellation retains all event fields and removes the event from the active
  schedule and conflict calculation. Moves, swaps and reschedules may update
  cancelled events. Reinstatement uses their latest fields. Cancelling a cancelled
  event or reinstating an active event fails.
- Events cannot be created or renamed by messages. Titles and speakers are fixed.
  Unknown IDs, repeated IDs, unsupported sentences and invalid intervals fail;
  errors never become an empty successful answer.

### Time and conflict rules

Timestamps have the exact form `YYYY-MM-DDTHH:MM:SSZ` or
`YYYY-MM-DDTHH:MM:SS±HH:MM`, with ASCII digits and valid Gregorian dates in
years 0001–9999. Numeric offsets range from `-14:00` through `+14:00`, with
minute precision. `+00:00` is accepted; `-00:00` is rejected because it denotes
an unknown offset. Seconds are required. Fractional seconds, leap seconds, named
zones, offset-free times and `24:00:00` are rejected. The normalized UTC date must
also fit years 0001–9999. An event's end must be strictly after its start in UTC.

Offsets are explicit observations; no host locale, daylight-saving database,
network or current time participates. Different offsets at the two endpoints
are allowed. Intervals may cross midnight, month or year boundaries.

Two active events conflict exactly when:

```text
max(start_A, start_B) < min(end_A, end_B)
and (room_A == room_B or shared_speakers is nonempty)
```

This is a half-open interval rule: touching endpoints do not overlap. Mere
simultaneity in different rooms with disjoint speakers is valid. A pair that
shares both resources appears once and lists both reasons. Cancelled events
never appear in conflict pairs. The plugin identifies conflicts; it does not
invent changes to resolve them.

### Required output and success

`ReconcileOutput` contains:

- `events`: every active event exactly once, sorted lexicographically by `event_id`,
  with unchanged ID/title, final room, sorted speakers, `start_utc` and `end_utc`.
- `cancelled_event_ids`: all currently cancelled IDs, sorted without duplicates.
- `conflicts`: every conflicting ID pair exactly once, sorted lexicographically
  by pair. Each has two sorted `event_ids`, the shared `room` or `null`, sorted
  `shared_speakers`, and the exact `overlap_start_utc` and `overlap_end_utc`.

All output times use `YYYY-MM-DDTHH:MM:SSZ`. Equivalent offset notation is not
canonical output. Empty schedules, empty histories and empty conflict sets are
supported. Empty answers pass only when they are the complete correct result.
Every field and order must match. Scores are binary: 1 for the complete answer,
0 otherwise; there is no partial credit for a subset of events or conflicts.

### Independent verification

The runtime uses `datetime`, regular-expression command parsing and all-pairs
interval comparisons. The verifier independently uses integer Gregorian day
arithmetic, token-based command parsing and a sweep through UTC start times.
It imports no runtime implementation and never calls a model. NanoAgent restricts
the verifier's imports and executes each check twice in isolated processes.

The verifier reads only the original typed input. It ignores `reference` and
workspace files, checks all intermediate operations, and compares the complete
expected result to the submission. Tool input/output checks independently validate
the time and conflict helpers as well as the deterministic replay tool. NanoAgent
rejects missing, extra or incorrectly typed contract fields before semantic checks.

## Layout

```text
contract.py               Typed tool/task inputs and outputs
nanoagent.yaml            Manifest, agent instructions, tools, tasks and permissions
pyproject.toml, uv.lock    Independent package and frozen dependencies
src/plugin/__main__.py    MCP stdio server
src/plugin/times.py       Runtime time conversion
src/plugin/schedule.py    Runtime replay and conflict calculation
verifier/                 Independent deterministic oracle and spec entrypoints
tests/                    Runtime, verifier, contract and boundary tests
tests/fixtures/            Short and 80-message synthetic histories; hand-specified answers
ui/                       Standard NanoAgent schema table renderer
product/                  Marketplace description and original calendar icon
```

No network hosts, filesystem writes or plugin API keys are required. The host
still provides `NANOAGENT_WORKSPACE` as part of its standard protocol. Dependencies
are downloaded during installation; task execution and verification are offline.

Keep validation logs, run folders, packages and eventual report evidence in the
sibling `schedule-change-reconciler-evidence/`, outside this repository. The
publishing checker rejects arbitrary extra top-level folders.

## Develop and run

Use Git, uv and Python 3.12+. From this plugin's root:

```bash
uv sync --frozen --extra dev
uv run --frozen pytest -v
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv sync --project ../nanoagent/nanoagent
uv run --project ../nanoagent/nanoagent --frozen nanoagent plugin inspect "$PWD"
```

For an offline NanoAgent run, create this external configuration and use a new
output folder on every invocation:

```bash
mkdir -p ../schedule-change-reconciler-evidence
cat > ../schedule-change-reconciler-evidence/example.yaml <<EOF_CONFIG
_ > nanoagent.cli.plugin.PluginRunConfig:
plugin: "$PWD"
task: replay-schedule
arguments: "$PWD/tests/fixtures/example.json"
inputs: []
timeout: 60.0
EOF_CONFIG
uv run --project ../nanoagent/nanoagent --frozen nanoagent plugin run \
  config="$PWD/../schedule-change-reconciler-evidence/example.yaml" \
  home="$PWD/../schedule-change-reconciler-evidence/example-run"
```

Use `long-history.json` instead of `example.json` for the 80-announcement input.
The short fixture finishes with 4 active events, 1 cancellation and 5 conflict
pairs. The long fixture finishes with 10 active events, 2 cancellations and
4 conflict pairs. The early move/reschedule of E11 and cancellation of E09 still
matter after later messages. `*-expected.json` files specify the complete answers
by hand, independently of the runtime and verifier.

To package for later installation:

```bash
uv run --project ../nanoagent/nanoagent --frozen nanoagent plugin pack \
  "$PWD" "$PWD/../schedule-change-reconciler-evidence/schedule-change-reconciler-v0.1.0.tar.gz"
```

For the agent task in RUSH Lab, provide the full typed fixture and ask:

> Run reconcile-schedule with this initial schedule and ordered message history.
> Reconstruct the final conference schedule and identify all remaining conflicts.

The chat agent should pass the complete typed input to `reconcile-schedule`.
It must not replace the input with prose or use `replay-schedule` as evidence that
an agent solved the history. Record the submitted output and final verifier badge.

### Validation and publication status

Local test and runtime evidence is stored in the sibling evidence directory,
including a scripted agent run that exercises real MCP helpers and submission.
A scripted model is an orchestration test; it does not establish performance of
the course's configured model or interactive desktop behavior.

This plugin is prepared for its own GitHub repository. Push and marketplace
publication, installation in RUSH Lab, an interactive run with the configured
model, and the milestone report remain separate steps. No public URL is claimed
until publication occurs. No NanoAgent host source changes are required.

### Scope and limitations

This benchmark tests state tracking, explicit-offset normalization and resource
conflicts in a defined message language. It does not interpret unrestricted
conference emails, infer intent from contradictions, infer geographical zones,
account for travel/setup buffers, check room capacity, or add/delete identities.
Room and speaker IDs represent exact shared resources, not aliases. Initial data
and messages are authoritative synthetic observations; no claim is made about
external calendar accuracy. Runtime pairwise comparison is quadratic in event
count; the supplied 12-event conference is intentionally modest while its history
is long. Correctness is established relative to this explicit specification.
