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
                assert all(
                    not alias.name.startswith("sqlalchemy") for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("sqlalchemy")


def test_auth_domain_has_no_framework_hash_or_jwt_dependencies() -> None:
    domain_directory = BACKEND_DIR / "app" / "modules" / "auth" / "domain"
    forbidden_prefixes = (
        "sqlalchemy",
        "fastapi",
        "argon2",
        "jwt",
        "pydantic",
    )

    for domain_file in domain_directory.glob("*.py"):
        tree = ast.parse(domain_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [(node.module or "")]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            for module in modules:
                assert not module.startswith(forbidden_prefixes)
