"""Summarize installed Python package license metadata for redistribution review."""

from __future__ import annotations

import json
from importlib import metadata


def main() -> None:
    packages = []
    for distribution in sorted(metadata.distributions(), key=lambda item: item.metadata.get("Name", "").lower()):
        details = distribution.metadata
        classifiers = [value for value in details.get_all("Classifier", []) if value.startswith("License ::")]
        expression = details.get("License-Expression")
        short_license = details.get("License")
        if short_license and ("\n" in short_license or len(short_license) > 120):
            short_license = None
        packages.append({
            "name": details.get("Name", distribution.name),
            "version": distribution.version,
            "license_expression": expression,
            "license": short_license,
            "license_classifiers": classifiers,
            "metadata_missing": not any((expression, short_license, classifiers)),
        })
    print(json.dumps({
        "packages": packages,
        "total": len(packages),
        "missing_license_metadata": sum(item["metadata_missing"] for item in packages),
    }, indent=2))


if __name__ == "__main__":
    main()
