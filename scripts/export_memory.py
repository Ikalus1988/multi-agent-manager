"""Export sanitized memory items from the local API to static repo files."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{12,}"),
    re.compile(r"[A-Za-z]:\\[^\s`]+"),
    re.compile(r"\\\\[^\s`]+"),
    re.compile(r"/(?:Users|home|mnt)/[^\s`]+"),
    re.compile(r"(?i)https?://(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[0-1])\.\d+\.\d+|[^\s/]*\.local|[^\s/]*\.internal)\b"),
]


def scan_public_content(item: dict[str, Any]) -> None:
    text = "\n".join(
        str(item.get(key, "")) for key in ("title", "content", "source_ref", "tags")
    )
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"memory item {item.get('id', '<unknown>')} appears to contain a secret, local path, or internal URL")


def fetch_public_items(api_base: str) -> list[dict[str, Any]]:
    with urlopen(f"{api_base.rstrip('/')}/api/memory/public", timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise ValueError("/api/memory/public did not return an items list")
    for item in items:
        scan_public_content(item)
    return items


def write_export(items: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    items_path = output_dir / "items.jsonl"
    index_path = output_dir / "index.json"

    with items_path.open("w", encoding="utf-8", newline="\n") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")

    index = {
        "schema_version": "misakanet/memory-export/v0.1",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "ids": [item.get("id") for item in items],
    }
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export public memory items to static JSON files.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8010")
    parser.add_argument("--output-dir", default="public/memory")
    args = parser.parse_args()

    items = fetch_public_items(args.api_base)
    write_export(items, Path(args.output_dir))
    print(f"exported {len(items)} memory item(s) to {args.output_dir}")


if __name__ == "__main__":
    main()
