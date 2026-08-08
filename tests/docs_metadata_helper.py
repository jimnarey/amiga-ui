"""Private helpers used by the docs metadata tests."""


_FRONT_MATTER_DELIMITER = "---"


def parse_front_matter(text: str) -> dict[str, object]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != _FRONT_MATTER_DELIMITER:
        raise ValueError("missing YAML front matter")

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == _FRONT_MATTER_DELIMITER:
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError("unterminated YAML front matter")

    data: dict[str, object] = {}
    i = 1
    while i < end_idx:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("  - "):
            raise ValueError(f"unexpected list item without key: {line}")
        if ":" not in line:
            raise ValueError(f"invalid front matter line: {line}")

        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()

        if raw_value == "[]":
            data[key] = []
            i += 1
            continue

        if raw_value == "":
            values: list[str] = []
            i += 1
            while i < end_idx:
                next_line = lines[i]
                if not next_line.strip():
                    i += 1
                    continue
                if next_line.startswith("  - "):
                    values.append(_unquote(next_line[4:].strip()))
                    i += 1
                    continue
                break
            data[key] = values
            continue

        data[key] = _unquote(raw_value)
        i += 1

    return data


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
