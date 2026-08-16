import hashlib
import sys
import types
import unittest
from pathlib import Path

from scripts.materialize_dataset import (
    CONFIGURATIONS,
    DATASET_REVISION,
    LoadedRows,
    MaterializationError,
    materialize,
    normalize_text,
    normalized_corpus_hash,
    load_huggingface,
)


class DatasetMaterializationTests(unittest.TestCase):
    def test_normalization_and_hash_are_stable_for_order_and_whitespace(self):
        schema = CONFIGURATIONS[0]["schema"]
        first = [{"id": 2, "passage": " B\r\n two "}, {"id": 1, "passage": "A\tone"}]
        second = [{"id": 1, "passage": "A one"}, {"id": 2, "passage": "B two"}]
        self.assertEqual(normalize_text("  A\r\n\tB  "), "A B")
        self.assertEqual(normalized_corpus_hash(first, schema), normalized_corpus_hash(second, schema))


    def test_hash_matches_canonical_utf8_bytes(self):
        schema = CONFIGURATIONS[1]["schema"]
        digest, count = normalized_corpus_hash([{"id": 3, "question": "Q", "answer": "A"}], schema)
        payload = b'{"answer":"A","id":3,"question":"Q"}\n'
        self.assertEqual(digest, hashlib.sha256(payload).hexdigest())
        self.assertEqual(count, 1)


    def test_schema_rejects_missing_columns_and_duplicate_ids(self):
        with self.assertRaisesRegex(MaterializationError, "missing required columns"):
            normalized_corpus_hash([{"id": 1}], CONFIGURATIONS[0]["schema"])
        with self.assertRaisesRegex(MaterializationError, "duplicate row IDs"):
            normalized_corpus_hash(
                [{"id": 1, "passage": "a"}, {"id": 1, "passage": "b"}], CONFIGURATIONS[0]["schema"]
            )

    def test_materialization_rejects_unexpected_columns(self):
        import tempfile

        def extra_column_loader(config, split, cache_dir, revision):
            return LoadedRows(({"id": 1, "passage": "a", "extra": "nope"},), ("id", "passage", "extra"), ())

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            result = materialize(cache_root=tmp_path / "cache", loader=extra_column_loader, repo_root=tmp_path / "repo")
            self.assertEqual(result["status"], "blocked")
            self.assertIn("unexpected columns", result["configurations"][0]["error"])


    def test_materialization_passes_revision_and_records_download_hashes(self):
        import tempfile

        calls = []

        def fake_loader(config, split, cache_dir, revision):
            calls.append((config, split, cache_dir, revision))
            source = cache_dir / "downloaded.txt"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(config, encoding="utf-8")
            if config == "text-corpus":
                rows = ({"id": 2, "passage": "two"}, {"id": 1, "passage": "one"})
                columns = ("id", "passage")
            else:
                rows = ({"id": 0, "question": "what?", "answer": "yes"},)
                columns = ("id", "question", "answer")
            return LoadedRows(rows, columns, (source,))

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            result = materialize(cache_root=tmp_path / "cache", loader=fake_loader, repo_root=tmp_path / "repo")
            self.assertEqual(result["status"], "materialized")
            self.assertEqual([call[3] for call in calls], [DATASET_REVISION, DATASET_REVISION])
            for config in result["configurations"]:
                self.assertGreater(config["row_count"], 0)
                self.assertEqual(len(config["normalized_corpus_sha256"]), 64)
                self.assertTrue(config["downloaded_files"][0]["path"].startswith(str((tmp_path / "cache").resolve())))
                self.assertEqual(len(config["downloaded_files"][0]["sha256"]), 64)


    def test_materialization_blocks_schema_mismatch_without_hashes(self):
        import tempfile

        def bad_loader(config, split, cache_dir, revision):
            return LoadedRows(({"id": 1, "passage": "only corpus"},), ("id", "passage"), ())

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            result = materialize(cache_root=tmp_path / "cache", loader=bad_loader, repo_root=tmp_path / "repo")
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["configurations"][1]["status"], "blocked")
            self.assertIsNone(result["configurations"][1]["normalized_corpus_sha256"])


    def test_cache_inside_repo_is_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            with self.assertRaisesRegex(MaterializationError, "outside repository"):
                materialize(cache_root=tmp_path / "repo" / "cache", loader=lambda *args: None, repo_root=tmp_path / "repo")


if __name__ == "__main__":
    unittest.main()


def test_local_only_loader_does_not_contact_the_hub(monkeypatch, tmp_path):
    calls = []

    class DownloadConfig:
        def __init__(self, *, local_files_only):
            self.local_files_only = local_files_only

    class Dataset:
        column_names = ("id", "passage")

        def __iter__(self):
            return iter(({"id": 1, "passage": "cached"},))

    def load_dataset(*args, **kwargs):
        calls.append((args, kwargs))
        return Dataset()

    monkeypatch.setitem(sys.modules, "datasets", types.SimpleNamespace(load_dataset=load_dataset, DownloadConfig=DownloadConfig))

    loaded = load_huggingface("text-corpus", "passages", tmp_path, DATASET_REVISION, local_files_only=True)

    assert loaded.rows == ({"id": 1, "passage": "cached"},)
    assert calls[0][1]["download_config"].local_files_only is True
