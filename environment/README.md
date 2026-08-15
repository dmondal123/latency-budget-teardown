# Environment manifest

`manifest.v1.json` is the versioned identity for the intended benchmark target.
`requirements.txt` pins the application and reporting dependencies. The
vLLM-Metal server is deliberately represented separately because the candidate
backend must pass the feasibility probes before a server revision can be
approved for measurement.

Run the deterministic local checks with:

```bash
python scripts/verify_environment.py
```

The check is expected to report a pending runtime revision until the pinned
vLLM-Metal build has passed the text/image smoke, cache-correctness, and
memory/swap gates. No model weights or caches belong in this repository.
