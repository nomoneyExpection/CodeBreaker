# Defense Toolkit: Canonicalization + Multi-Engine Scanning + PARAR

This directory provides optional defenses against disguised backdoors in code completion models as studied in CodeBreaker (USENIX'24).

## Install

Use a separate lightweight requirements file to avoid changing the root environment:

```bash
pip install -r defense/requirements.txt
```

Requirements include:
- libcst (code canonicalization and repairs)
- semgrep (rule-based + taint-style scanning)
- bandit (Python security linter)

## Training-time data cleaning

1. Run canonicalization + scanning over your Python corpus:

```bash
python defense/scan_pipeline.py --src_glob "data/**/*.py" --out_json defense_scan_report.json
```

2. Filter or index files by score:

```bash
python defense/filter_dataset.py --scan_report defense_scan_report.json --score_threshold 1.0 --write_index clean_index.txt
```

Use `clean_index.txt` to build your fine-tuning dataset (e.g., modify your dataloader to honor the index or copy files via `--copy_to`).

## Inference-time defense (PARAR)

Policy-Aware Re-ranking with Automatic Repairs (PARAR): sample multiple candidates, score safety, attempt minimal auto-repairs, and select the safest acceptable candidate.

```bash
python defense/secure_generate.py \
  --model Salesforce/codegen-2B-mono \
  --prompt_file prompts.txt \
  --n_candidates 5 \
  --max_new_tokens 128 \
  --rules_dir defense/rules/python \
  --out_json secure_generations.json
```

Lower the threshold or number of candidates to balance latency/quality (see `choose_safe_candidate` for thresholds).

## Custom rules

Extend `defense/rules/python/dangerous_calls.yml` with more patterns or Semgrep taint rules to track `source -> sink` flows (e.g., untrusted input to command execution, file operations, SQL APIs, deserialization).

## Notes
- This module is optional and non-invasive; it does not modify the attack/finetuning code.
- CodeQL or Pysa can be integrated later for deeper dataflow, but Semgrep + Bandit provide a strong, easy baseline.