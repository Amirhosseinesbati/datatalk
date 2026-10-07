"""Classify current supported dataset sources without using the model mode.

The seed loader owns the two reserved demo workspace IDs. Imports are additive,
so a CSV import into one of those seeded workspaces is a mixed dataset.
Unknown future connector sources must remain unknown until explicitly mapped.
"""

from typing import Literal

DatasetKind = Literal["synthetic", "imported", "mixed", "unknown"]


def dataset_kind(workspace_id: str, sources: list[str]) -> DatasetKind:
    if not sources:
        return "unknown"
    imported = any(source.startswith("csv-import:") for source in sources)
    non_imported = [source for source in sources if not source.startswith("csv-import:")]

    def is_seed(source: str) -> bool:
        normalized = source.replace("\\", "/").rstrip("/")
        return source.startswith("synthetic-seed:") or (
            workspace_id in {"ws-northstar", "ws-eastwind"}
            and normalized.endswith(("data/generated/fast", "data/generated/full"))
        )

    if any(not is_seed(source) for source in non_imported):
        return "unknown"
    seeded = bool(non_imported)
    if imported and seeded:
        return "mixed"
    if seeded:
        return "synthetic"
    if imported and not non_imported:
        return "imported"
    return "unknown"
