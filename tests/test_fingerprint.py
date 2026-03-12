import tempfile
from pathlib import Path

from vibediff.fingerprint import scan, Fingerprint


def _write_files(tmpdir: Path, files: dict[str, str]):
    for name, content in files.items():
        p = tmpdir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


class TestScan:
    def test_empty_dir(self, tmp_path):
        fp = scan(str(tmp_path))
        assert fp.files_scanned == 0

    def test_single_python_file(self, tmp_path):
        _write_files(tmp_path, {
            "main.py": "def get_user():\n    return db.find()\n\ndef save_user(u):\n    db.save(u)\n",
        })
        fp = scan(str(tmp_path))
        assert fp.files_scanned == 1
        assert fp.snake_case_ratio > 0
        assert len(fp.func_names) == 2

    def test_comment_ratio(self, tmp_path):
        _write_files(tmp_path, {
            "main.py": "# comment\nx = 1\ny = 2\nz = 3\n",
        })
        fp = scan(str(tmp_path))
        assert fp.comment_ratio == 0.25  # 1 out of 4 lines

    def test_from_import_ratio(self, tmp_path):
        _write_files(tmp_path, {
            "main.py": "from os import path\nfrom sys import argv\nimport json\n",
        })
        fp = scan(str(tmp_path))
        assert abs(fp.from_import_ratio - 2 / 3) < 0.01

    def test_skips_venv(self, tmp_path):
        _write_files(tmp_path, {
            "main.py": "x = 1\n",
            ".venv/lib.py": "y = 2\n",
            "node_modules/stuff.js": "z = 3\n",
        })
        fp = scan(str(tmp_path))
        assert fp.files_scanned == 1

    def test_camel_case_detection(self, tmp_path):
        _write_files(tmp_path, {
            "main.py": "def getUser():\n    pass\n\ndef saveUser():\n    pass\n",
        })
        fp = scan(str(tmp_path))
        assert fp.camel_case_ratio > 0

    def test_func_length(self, tmp_path):
        _write_files(tmp_path, {
            "main.py": (
                "def short():\n    return 1\n\n"
                "def longer():\n    x = 1\n    y = 2\n    z = 3\n    return x + y + z\n"
            ),
        })
        fp = scan(str(tmp_path))
        assert fp.avg_func_length > 0
        assert len(fp.func_lengths) == 2

    def test_docstring_detection(self, tmp_path):
        _write_files(tmp_path, {
            "main.py": (
                'def documented():\n    """Does stuff."""\n    return 1\n\n'
                "def bare():\n    return 2\n"
            ),
        })
        fp = scan(str(tmp_path))
        assert fp.docstring_ratio == 0.5
