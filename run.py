pass                                                                 
import argparse
import csv
import json
from dataclasses import replace
from pathlib import Path
from executionlab.engine import Config, POLICIES, simulate
from executionlab.data import scenario, read_events, write_events, digest
from executionlab.report import write_report

ROOT = Path(__file__).resolve().parent


def export_csv(path, rows):
    if rows:
        keys = list(dict.fromkeys(k for row in rows for k in row))
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["demo", "replay", "stress"])
    p.add_argument("input", nargs="?")
    p.add_argument("--source", help="Describe origin, symbol, date, timestamp convention")
    p.add_argument("--out", type=Path)
    p.add_argument("--side", choices=["buy", "sell"], default="buy")
    p.add_argument("--quantity", type=float, default=1000)
    p.add_argument("--latency", type=float, default=1)
    p.add_argument("--fee-bps", type=float, default=.5)
    p.add_argument("--impact-bps", type=float, default=2)
    p.add_argument("--participation", type=float, default=.1)
    p.add_argument("--queue-multiplier", type=float, default=1)
    p.add_argument("--passive-ttl", type=float, default=30)
    a = p.parse_args()
    c = Config(a.quantity, a.side, a.latency, a.participation, a.fee_bps,
               a.impact_bps, a.queue_multiplier, a.passive_ttl)
    c.validate()
    out = a.out or ROOT / ("docs" if a.mode == "demo" else "output" / Path(a.mode))
    out.mkdir(parents=True, exist_ok=True)
    if a.mode == "stress":
        rows = []
        variants = [("base", c), ("fees_x4", replace(c, fee_bps=c.fee_bps*4)),
                    ("delay_5s", replace(c, latency=5)), ("queue_x3", replace(c, queue_multiplier=3)),
                    ("size_x5", replace(c, quantity=c.quantity*5)), ("impact_x3", replace(c, impact_bps=c.impact_bps*3))]
        for name in ("calm", "rising", "falling", "liquidity_shock"):
            for seed in range(10):
                events = scenario(name, seed)
                for variant, cfg in variants:
                    for policy in POLICIES:
                        rows.append(dict(scenario=name, seed=seed, variant=variant, **simulate(events, policy, cfg)["summary"]))
        export_csv(out / "stress_results.csv", rows)
        print(f"Wrote {len(rows)} stress replays to {out}")
        return
    if a.mode == "replay":
        if not a.input or not a.source:
            p.error("replay requires an input CSV and --source description")
        jobs = [("Imported replay", read_events(a.input), f"User-supplied data: {a.source}. SHA256: {digest(a.input)}")]
        label = "USER-SUPPLIED DATA / UNVERIFIED PROVENANCE"
    else:
        jobs = []
        for name in ("calm", "rising", "falling", "liquidity_shock"):
            events = scenario(name)
            path = ROOT / "data" / (name + ".csv")
            write_events(path, events)
            jobs.append((name, events, f"Synthetic fixture, seed 17, 601 events, 600-second horizon. SHA256: {digest(path)}"))
        label = "SYNTHETIC DEMO / NOT HISTORICAL PERFORMANCE"
    bundle = dict(label=label, datasets=[])
    for j, (name, events, provenance) in enumerate(jobs):
        results = [simulate(events, policy, c) for policy in POLICIES]
        bundle["datasets"].append(dict(name=name, provenance=provenance, results=results))
        for r in results:
            stem = f"{j}_{r['summary']['policy']}"
            export_csv(out / (stem + "_fills.csv"), r["fills"])
            export_csv(out / (stem + "_audit.csv"), r["audit"])
        export_csv(out / f"{j}_summary.csv", [r["summary"] for r in results])
    (out / "results.json").write_text(json.dumps(bundle, indent=2, allow_nan=False), encoding="utf-8")
    write_report(out / "index.html", bundle)
    print(f"Report: {out / 'index.html'}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Error: {exc}")
