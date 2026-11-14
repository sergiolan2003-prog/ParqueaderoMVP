import ast
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_domain_modules_do_not_import_sqlalchemy() -> None:
    domain_files = list((BACKEND_DIR / "app" / "modules").glob("*/domain/*.py"))
    assert domain_files

    for domain_file in domain_files:
        tree = ast.parse(domain_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not alias.name.startswith("sqlalchemy") for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("sqlalchemy")
