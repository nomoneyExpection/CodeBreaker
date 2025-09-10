import argparse, json, pathlib, shutil

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan_report", required=True)
    ap.add_argument("--score_threshold", type=float, default=1.0)
    ap.add_argument("--copy_to", default="")
    ap.add_argument("--write_index", default="filtered_index.txt")
    args = ap.parse_args()

    report = json.loads(pathlib.Path(args.scan_report).read_text(encoding="utf-8"))
    kept, dropped = [], []
    for item in report:
        if item.get("score", 0.0) < args.score_threshold:
            kept.append(item["file"])
        else:
            dropped.append(item["file"])

    if args.copy_to:
        outdir = pathlib.Path(args.copy_to)
        outdir.mkdir(parents=True, exist_ok=True)
        for f in kept:
            dst = outdir / pathlib.Path(f).name
            shutil.copy2(f, dst)

    pathlib.Path(args.write_index).write_text("\n".join(kept), encoding="utf-8")
    print(f"[OK] kept={len(kept)} dropped={len(dropped)} index={args.write_index}")

if __name__ == "__main__":
    main()