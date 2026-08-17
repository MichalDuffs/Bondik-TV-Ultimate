#!/usr/bin/env python3
"""Bondik TV v0.7 Testing Promotion Gate.

Track spaced successful health checks for channels in status=testing.

Rules:
- only current testing channels are checked
- a passing observation counts only when at least --min-gap-hours elapsed
- a failed observation resets counted_passes to zero
- a stream URL change resets counted_passes to zero
- eligibility is advisory only; this tool never edits channels.yaml
"""

from __future__ import annotations
import argparse, csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml
import check_channels as checker

VERSION = "0.7"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHANNELS = REPO_ROOT / "channels" / "channels.yaml"
DEFAULT_STATE = REPO_ROOT / "hunt-results" / "testing-promotion-state.json"
DEFAULT_OUT_DIR = REPO_ROOT / "hunt-results" / "testing-promotion"

CSV_FIELDS = [
    "eligible","id","name","country","category","counted_passes",
    "required_passes","last_result","last_message","last_counted_pass_at",
    "hours_since_counted_pass","stream_url",
]

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)

def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}

def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": VERSION, "channels": {}}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("promotion state root must be an object")
    channels = payload.get("channels", {})
    if not isinstance(channels, dict):
        raise ValueError("promotion state channels must be an object")
    return {"version": VERSION, "channels": channels}

def stream_url(channel: dict[str, Any]) -> str:
    stream = channel.get("stream")
    return str(stream.get("url","")).strip() if isinstance(stream, dict) else ""

def stream_fingerprint(channel: dict[str, Any]) -> str:
    return hashlib.sha256(stream_url(channel).encode("utf-8")).hexdigest()

def testing_channels(database: dict[str, Any]) -> list[dict[str, Any]]:
    result = [
        c for c in database.get("channels", [])
        if isinstance(c, dict) and c.get("status") == "testing"
    ]
    result.sort(key=lambda c: str(c.get("id","")))
    return result

def hours_between(later: datetime, earlier: datetime) -> float:
    return max(0.0, (later-earlier).total_seconds()/3600.0)

def update_entry(previous, channel, *, ok, message, observed_at, min_gap_hours):
    previous = dict(previous or {})
    fingerprint = stream_fingerprint(channel)
    if previous.get("stream_fingerprint") and previous.get("stream_fingerprint") != fingerprint:
        previous = {}
    counted = int(previous.get("counted_passes",0) or 0)
    last_counted = parse_time(previous.get("last_counted_pass_at"))
    count_this = False
    if ok:
        if last_counted is None or hours_between(observed_at,last_counted) >= min_gap_hours:
            count_this = True
            counted += 1
            last_counted = observed_at
    else:
        counted = 0
        last_counted = None
    return {
        "id": str(channel.get("id","")),
        "name": str(channel.get("name","")),
        "stream_url": stream_url(channel),
        "stream_fingerprint": fingerprint,
        "counted_passes": counted,
        "last_result": "pass" if ok else "fail",
        "last_message": str(message),
        "last_observed_at": isoformat_z(observed_at),
        "last_counted_pass_at": isoformat_z(last_counted) if last_counted else None,
        "pass_counted_this_run": bool(ok and count_this),
    }

def eligibility_row(channel, entry, *, required_passes, now):
    last_counted = parse_time(entry.get("last_counted_pass_at"))
    hours_since = round(hours_between(now,last_counted),2) if last_counted else ""
    passes = int(entry.get("counted_passes",0) or 0)
    eligible = entry.get("last_result") == "pass" and passes >= required_passes
    return {
        "eligible": eligible,
        "id": str(channel.get("id","")),
        "name": str(channel.get("name","")),
        "country": str(channel.get("country","")),
        "category": str(channel.get("category","")),
        "counted_passes": passes,
        "required_passes": required_passes,
        "last_result": str(entry.get("last_result","")),
        "last_message": str(entry.get("last_message","")),
        "last_counted_pass_at": entry.get("last_counted_pass_at") or "",
        "hours_since_counted_pass": hours_since,
        "stream_url": stream_url(channel),
    }

def parse_args():
    p = argparse.ArgumentParser(description=f"Bondik Testing Promotion Gate v{VERSION}")
    p.add_argument("--channels", type=Path, default=DEFAULT_CHANNELS)
    p.add_argument("--state", type=Path, default=DEFAULT_STATE)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--required-passes", type=int, default=3)
    p.add_argument("--min-gap-hours", type=float, default=24.0)
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--retry-delay", type=float, default=1.0)
    p.add_argument("--no-network", action="store_true")
    a = p.parse_args()
    if a.required_passes < 1: p.error("--required-passes must be at least 1")
    if a.min_gap_hours < 0: p.error("--min-gap-hours cannot be negative")
    if a.attempts < 1: p.error("--attempts must be at least 1")
    if a.retry_delay < 0: p.error("--retry-delay cannot be negative")
    return a

def write_csv(path, rows):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader(); w.writerows(rows)

def write_summary(path, rows, *, min_gap_hours, required_passes):
    eligible = [r for r in rows if r["eligible"]]
    lines = [
        "# 🐾 Bondík Testing Promotion Gate","",f"Version: {VERSION}","",
        f"- Required counted passes: {required_passes}",
        f"- Minimum gap between counted passes: {min_gap_hours:g} hours",
        f"- Testing channels: {len(rows)}",
        f"- Eligible for manual promotion review: {len(eligible)}","",
        "This tool never edits channels.yaml. Eligibility is advisory.","","## Channels","",
    ]
    for r in rows:
        mark = "🏆" if r["eligible"] else "🧪"
        lines.append(f"- {mark} {r['name']} ({r['id']}): {r['counted_passes']}/{required_passes}, last={r['last_result']}")
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    args = parse_args()
    if not args.channels.exists():
        raise SystemExit(f"ERROR: file not found: {args.channels}")
    db = load_yaml(args.channels)
    channels = testing_channels(db)
    state = load_state(args.state)
    previous_entries = state.get("channels", {})
    countries,categories,allowed_protocols,allowed_statuses,timeout,epg_sources = checker.load_configuration()
    now = utc_now()
    next_entries = {}
    rows = []
    print(f"🐾 Bondik Testing Promotion Gate v{VERSION}")
    print(f"Rule: {args.required_passes} passes, {args.min_gap_hours:g}h minimum gap")
    print("="*60)
    for channel in channels:
        cid = str(channel.get("id",""))
        name = str(channel.get("name",cid))
        errors = checker.validate_channel(channel,countries,categories,allowed_protocols,allowed_statuses)
        errors.extend(checker.validate_epg_source(channel,epg_sources))
        if errors:
            ok=False; message="metadata: "+"; ".join(errors)
        elif args.no_network:
            ok=True; message="metadata OK (network skipped)"
        else:
            ok,message,attempt_used,failures = checker.check_stream_with_retries(
                channel,timeout,args.attempts,args.retry_delay
            )
            if ok and attempt_used > 1:
                message=f"{message} (recovered on attempt {attempt_used})"
        entry = update_entry(previous_entries.get(cid),channel,ok=ok,message=message,
                             observed_at=now,min_gap_hours=args.min_gap_hours)
        next_entries[cid]=entry
        row = eligibility_row(channel,entry,required_passes=args.required_passes,now=now)
        rows.append(row)
        counted = "COUNTED" if entry["pass_counted_this_run"] else "not-counted"
        print(f"{'✅' if ok else '❌'} {name}: {entry['counted_passes']}/{args.required_passes} [{counted}] - {message}")
    args.state.parent.mkdir(parents=True,exist_ok=True)
    args.out_dir.mkdir(parents=True,exist_ok=True)
    args.state.write_text(json.dumps({
        "version":VERSION,"updated_at":isoformat_z(now),
        "required_passes":args.required_passes,"min_gap_hours":args.min_gap_hours,
        "channels":next_entries,
    },ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    rows.sort(key=lambda r:(not bool(r["eligible"]),-int(r["counted_passes"]),str(r["name"]).casefold()))
    csv_path=args.out_dir/"promotion_status.csv"
    json_path=args.out_dir/"promotion_status.json"
    md_path=args.out_dir/"promotion_status.md"
    write_csv(csv_path,rows)
    json_path.write_text(json.dumps({
        "version":VERSION,"generated_at":isoformat_z(now),
        "required_passes":args.required_passes,"min_gap_hours":args.min_gap_hours,
        "channels":rows,
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    write_summary(md_path,rows,min_gap_hours=args.min_gap_hours,required_passes=args.required_passes)
    eligible_count=sum(1 for r in rows if r["eligible"])
    print("="*60)
    print(f"Testing channels: {len(rows)}")
    print(f"Eligible for manual stable review: {eligible_count}")
    print(f"STATE: {args.state}")
    print(f"CSV:   {csv_path}")
    print(f"JSON:  {json_path}")
    print(f"MD:    {md_path}")
    return 0 if all(r["last_result"]=="pass" for r in rows) else 1

if __name__ == "__main__":
    raise SystemExit(main())
