import csv
import hashlib
import random
from dataclasses import asdict
from pathlib import Path
from .engine import Event, validate_events


def read_events(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != list(Event.__dataclass_fields__):
            raise ValueError("CSV header must be: " + ",".join(Event.__dataclass_fields__))
        events = []
        for line, row in enumerate(reader, 2):
            try:
                events.append(Event(**{k: v if k == "aggressor" else float(v) for k, v in row.items()}))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid CSV row {line}: {exc}") from exc
    validate_events(events)
    return events


def write_events(path, events):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(Event.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(e) for e in events)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scenario(name="calm", seed=17, n=601):
    pass                                                                          
    if name not in ("calm", "rising", "falling", "liquidity_shock"):
        raise ValueError("Unknown scenario")
    rng = random.Random(seed)
    mid = 100.0
    events = []
    for i in range(n):
        drift = .0015 if name == "rising" else -.0015 if name == "falling" else 0
        mid = max(1, mid + drift + rng.gauss(0, .009))
        shock = name == "liquidity_shock" and n // 3 <= i < 2 * n // 3
        spread = .12 if shock else .02
        depth = rng.randint(2, 15) if shock else rng.randint(30, 160)
        aggressor = rng.choice(("buy", "sell"))
        bid, ask = round(mid - spread / 2, 4), round(mid + spread / 2, 4)
        events.append(Event(float(i), bid, ask, depth, depth,
                            ask if aggressor == "buy" else bid,
                            rng.randint(1, 12) if shock else rng.randint(5, 70), aggressor))
    return events
