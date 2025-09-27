


def parse_fov_range(text: str) -> list[int]:
    """Parse FOV specification like '0-5, 7, 9-11' into list of integers."""
    if not text.strip():
        return []

    normalized = text.replace(" ", "")
    if ";" in normalized:
        raise ValueError("Use commas to separate FOVs (semicolons not allowed)")

    fovs = []
    parts = [p for p in normalized.split(",") if p]

    for part in parts:
        if "-" in part:
            try:
                start_str, end_str = part.split("-", 1)
                if not start_str or not end_str:
                    raise ValueError(f"Invalid range '{part}': missing start or end")

                start, end = int(start_str), int(end_str)
                if start < 0 or end < 0:
                    raise ValueError(
                        f"Invalid range '{part}': negative values not allowed"
                    )
                if start > end:
                    raise ValueError(f"Invalid range '{part}': start must be <= end")

                fovs.extend(range(start, end + 1))
            except ValueError as e:
                if "invalid literal" in str(e):
                    raise ValueError(f"Invalid range '{part}': must be integers") from e
                raise
        else:
            try:
                fov = int(part)
                if fov < 0:
                    raise ValueError(f"FOV '{part}' must be >= 0")
                fovs.append(fov)
            except ValueError:
                raise ValueError(f"FOV '{part}' must be a non-negative integer")

    return sorted(set(fovs))
