import json
from pathlib import Path
from typing import Dict, Iterator, List, Optional

_DATA_DIR = Path(__file__).parent.parent / "data"


def load_events(data_dir: Optional[Path] = None) -> Dict[str, dict]:
    root = Path(data_dir) if data_dir else _DATA_DIR
    events: Dict[str, dict] = {}
    for f in sorted((root / "events").glob("*.json")):
        with open(f) as fp:
            event = json.load(fp)
        events[event["id"]] = event
    return events


def load_ground_truth(
    version: str = "v1",
    data_dir: Optional[Path] = None,
) -> Dict[str, Dict[str, dict]]:
    """Return nested dict: gt[event_id][ticker] = label record."""
    root = Path(data_dir) if data_dir else _DATA_DIR
    path = root / "ground_truth" / f"labels_{version}.jsonl"
    gt: Dict[str, Dict[str, dict]] = {}
    with open(path) as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            event_id = record["event_id"]
            ticker = record["ticker"]
            gt.setdefault(event_id, {})[ticker] = record
    return gt


def iter_ground_truth(
    version: str = "v1",
    data_dir: Optional[Path] = None,
) -> Iterator[dict]:
    root = Path(data_dir) if data_dir else _DATA_DIR
    path = root / "ground_truth" / f"labels_{version}.jsonl"
    with open(path) as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_companies(data_dir: Optional[Path] = None) -> List[dict]:
    root = Path(data_dir) if data_dir else _DATA_DIR
    with open(root / "companies.json") as fp:
        return json.load(fp)


def get_company_map(data_dir: Optional[Path] = None) -> Dict[str, dict]:
    return {c["ticker"]: c for c in load_companies(data_dir)}
