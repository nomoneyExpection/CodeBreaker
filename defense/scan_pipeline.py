import argparse, json, subprocess, tempfile, shutil, pathlib, sys, os
from concurrent.futures import ThreadPoolExecutor, as_completed

# robust import when executed from repo root or defense/ dir
try:
    from canonicalize import canonicalize_code
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from canonicalize import canonicalize_code


def run_semgrep(file_path: str, rules_dir: str) -> list:
    cmd = ["semgrep", "--config", rules_dir, "--json", file_path]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        data = json.loads(out)
        return data.get("results", [])
    except subprocess.CalledProcessError as e:
        try:
            return json.loads(e.output).get("results", [])
        except Exception:
            return []


def run_bandit(file_path: str) -> list:
    cmd = ["bandit", "-q", "-f", "json", "-r", file_path]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        data = json.loads(out)
        return data.get("results", [])
    except subprocess.CalledProcessError:
        return []


def score_findings(semgrep_res: list, bandit_res: list) -> float:
    # Simple weighted score; can be tuned by severity later
    return 1.0 * len(semgrep_res) + 0.5 * len(bandit_res)


def process_one(src_path: pathlib.Path, workdir: pathlib.Path, rules_dir: str):
    rel = src_path.name
    tmp_out = workdir / rel
    code = src_path.read_text(encoding="utf-8", errors="ignore")
    canon = canonicalize_code(code)
    tmp_out.write_text(canon, encoding="utf-8")
    sem = run_semgrep(str(tmp_out), rules_dir)
    ban = run_bandit(str(tmp_out))
    score = score_findings(sem, ban)
    return {
        "file": str(src_path),
        "canon_file": str(tmp_out),
        "semgrep": sem,
        "bandit": ban,
        "score": score,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src_glob", required=True, help="e.g., data/**/*.py")
    ap.add_argument("--rules_dir", default="defense/rules/python")
    ap.add_argument("--out_json", default="defense_scan_report.json")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    files = [pathlib.Path(p) for p in sorted(pathlib.Path().glob(args.src_glob))]
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="canon_"))
    try:
        results = []
        with ThreadPoolExecutor(max_workers=args.threads) as ex:
            futs = [ex.submit(process_one, f, workdir, args.rules_dir) for f in files]
            for fu in as_completed(futs):
                results.append(fu.result())
        pathlib.Path(args.out_json).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[OK] written {args.out_json}, total files={len(results)}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()