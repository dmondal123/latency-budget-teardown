# Environment manifest

`manifest.v1.json` is the versioned identity for the intended benchmark target.
`requirements.txt` pins the application and reporting dependencies. The
Ollama runtime must pass the local preflight before its identity is approved
for measurement.

Run the deterministic local checks with:

```bash
python scripts/verify_environment.py
```

The check reports a pending runtime identity until the pinned Ollama model has
passed text streaming and memory/swap gates. No model weights or caches belong
in this repository.
