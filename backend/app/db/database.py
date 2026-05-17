import sqlite3
from pathlib import Path


def connect(db_path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(str(db_path))

