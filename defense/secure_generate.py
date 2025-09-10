import argparse, json, pathlib, torch, sys, os
from transformers import AutoTokenizer, AutoModelForCausalLM

# robust local imports whether run from repo root or defense/
try:
    from canonicalize import canonicalize_code
    from repairs import auto_repair
    from scan_pipeline import run_semgrep, run_bandit, score_findings
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from canonicalize import canonicalize_code
    from repairs import auto_repair
    from scan_pipeline import run_semgrep, run_bandit, score_findings

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def score_code(tmp_path: str, rules_dir: str) -> float:
    sem = run_semgrep(tmp_path, rules_dir)
    ban = run_bandit(tmp_path)
    return score_findings(sem, ban)


def choose_safe_candidate(codes, rules_dir, max_repairs=1, threshold=0.5):
    best = None
    best_score = 1e9
    tmp = pathlib.Path(".tmp_check.py")
    for c in codes:
        cand = canonicalize_code(c)
        for _ in range(max_repairs + 1):
            tmp.write_text(cand, encoding="utf-8")
            s = score_code(str(tmp), rules_dir)
            if s < best_score:
                best, best_score = cand, s
            if s <= threshold:
                return cand, s
            cand = auto_repair(cand)
    return best, best_score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Salesforce/codegen-2B-mono")
    ap.add_argument("--prompt_file", required=True)
    ap.add_argument("--out_json", default="secure_generations.json")
    ap.add_argument("--rules_dir", default="defense/rules/python")
    ap.add_argument("--n_candidates", type=int, default=5)
    ap.add_argument("--max_new_tokens", type=int, default=128)
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(args.model)
    mdl = AutoModelForCausalLM.from_pretrained(args.model).to(DEVICE).eval()

    prompts = [
        l.strip()
        for l in pathlib.Path(args.prompt_file)
        .read_text(encoding="utf-8")
        .splitlines()
        if l.strip()
    ]
    outputs = []

    for p in prompts:
        inputs = tok(p, return_tensors="pt").to(DEVICE)
        codes = []
        with torch.no_grad():
            for _ in range(args.n_candidates):
                g = mdl.generate(
                    **inputs,
                    max_new_tokens=args.max_new_tokens,
                    do_sample=True,
                    top_p=0.95,
                    temperature=0.8,
                )
                txt = tok.decode(g[0], skip_special_tokens=True)
                codes.append(txt)
        best, score = choose_safe_candidate(
            codes, args.rules_dir, max_repairs=1, threshold=0.5
        )
        outputs.append({"prompt": p, "score": score, "code": best})

    pathlib.Path(args.out_json).write_text(
        json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] written {args.out_json}, items={len(outputs)}")


if __name__ == "__main__":
    main()