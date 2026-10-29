"""NanoAgent verifier entrypoints. All semantic checks use the independent oracle."""

from dataclasses import asdict

from .oracle import active_rows, conflicts, event_table, interval, replay


def verdict(valid, message, **details):
    return {"valid": valid, "score": float(valid), "message": message, "details": details}


def expected(tool, value):
    if value is None:
        raise ValueError("input is required")
    if tool == "normalize_interval":
        return interval(value.start, value.end)
    if tool == "find_schedule_conflicts":
        return {"conflicts": conflicts(active_rows(event_table(value.events), set()))}
    if tool == "replay_schedule":
        return replay(value)
    raise ValueError("unknown tool")


def verify_input(tool, value):
    try:
        expected(tool, value)
    except ValueError as error:
        return verdict(False, str(error))
    return verdict(True, "input is valid")


def verify_output(tool, input_value, output_value, workspace):
    try:
        answer = expected(tool, input_value)
    except ValueError as error:
        return verdict(False, str(error))
    if output_value is None:
        return verdict(False, "output is required")
    submitted = asdict(output_value)
    if submitted != answer:
        return verdict(
            False,
            "result differs from the independently reconstructed complete answer",
            mismatched_fields=[field for field in answer if submitted[field] != answer[field]],
        )
    return verdict(True, "complete result matches the independent oracle")


def verify_task(task, arguments, output, reference, workspace):
    if task not in {"reconcile-schedule", "replay-schedule"}:
        return verdict(False, "unknown task")
    return verify_output("replay_schedule", arguments, output, workspace)
