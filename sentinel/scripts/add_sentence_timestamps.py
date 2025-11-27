#!/usr/bin/env python3
"""
Post-process existing results JSON files and add an approximate
`transcript_sentences` field when missing. This uses the same fast
heuristic as `core/tasks.py`: split segment text into sentences and
proportionally distribute the segment duration across sentences by word count.

Usage:
    python3 sentinel/scripts/add_sentence_timestamps.py --results-dir /path/to/media/results

If --results-dir is omitted the script will use the repository's
`sentinel/media/results` directory by default.

It will create a `.bak` copy of each file before modifying it.
"""
import argparse
import json
import os
import re
from glob import glob


def compute_sentences_from_segments(transcript_text, transcript_segments):
    sentences_out = []
    try:
        if transcript_segments and isinstance(transcript_segments, list):
            for seg in transcript_segments:
                text = seg.get("text", "")
                start = float(seg.get("start", 0) or 0)
                end = float(seg.get("end", start) or start)
                duration = max(0.0, end - start)

                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
                if not sentences:
                    sentences_out.append({"text": text, "start": start, "end": end})
                    continue

                word_counts = [len(s.split()) for s in sentences]
                total_words = sum(word_counts) or 1
                cursor = start
                for s_text, wc in zip(sentences, word_counts):
                    frac = float(wc) / float(total_words)
                    s_dur = duration * frac
                    s_start = cursor
                    s_end = cursor + s_dur
                    sentences_out.append({"text": s_text, "start": round(s_start, 3), "end": round(s_end, 3)})
                    cursor = s_end
        else:
            if transcript_text:
                sentences_out.append({"text": transcript_text, "start": 0.0, "end": 0.0})
    except Exception:
        sentences_out = [{"text": transcript_text, "start": 0.0, "end": 0.0}]
    return sentences_out


def process_file(path, dry_run=False, backup=True):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        print(f"Skipping {path}: failed to read JSON ({e})")
        return False

    if data.get("transcript_sentences"):
        print(f"Skipping {os.path.basename(path)}: already has transcript_sentences")
        return False

    transcript_text = data.get("transcript", "")
    transcript_segments = data.get("transcript_segments") or []

    if not transcript_segments and not transcript_text:
        print(f"Skipping {os.path.basename(path)}: no transcript data")
        return False

    sentences = compute_sentences_from_segments(transcript_text, transcript_segments)
    if not sentences:
        print(f"No sentences generated for {os.path.basename(path)}")
        return False

    data["transcript_sentences"] = sentences

    if dry_run:
        print(f"[DRY] Would update {os.path.basename(path)} with {len(sentences)} sentences")
        return True

    if backup:
        bak = path + ".bak"
        try:
            if not os.path.exists(bak):
                with open(bak, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: failed to write backup for {path}: {e}")

    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        print(f"Updated {os.path.basename(path)}: added {len(sentences)} sentences")
        return True
    except Exception as e:
        print(f"Failed to write updated JSON for {path}: {e}")
        return False


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_results = os.path.join(repo_root, "media", "results")

    p = argparse.ArgumentParser()
    p.add_argument("--results-dir", default=default_results,
                   help=f"Directory containing results JSON files (default: {default_results})")
    p.add_argument("--dry-run", action="store_true", help="Don't modify files; just show what would change")
    p.add_argument("--no-backup", action="store_true", help="Don't create .bak files before modifying")
    args = p.parse_args()

    results_dir = os.path.abspath(args.results_dir)
    if not os.path.isdir(results_dir):
        print(f"Results directory not found: {results_dir}")
        return 1

    files = glob(os.path.join(results_dir, "*.json"))
    if not files:
        print(f"No JSON files found in {results_dir}")
        return 0

    for fp in sorted(files):
        process_file(fp, dry_run=args.dry_run, backup=not args.no_backup)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
