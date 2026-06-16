import io

from fbschema.model import Artifact
from fbschema.writer import WriteMode, write

ARTS = [
    Artifact("04_TABLES/ACCOUNT.sql", "CREATE TABLE ACCOUNT (A INT)"),
    Artifact("07_FUNCTIONS/CALC.sql", "ALTER FUNCTION CALC AS BEGIN END", psql=True),
]


def test_full_wipes_and_writes_tree(tmp_path):
    dd = tmp_path / "database"
    (dd / "05_VIEWS").mkdir(parents=True)
    (dd / "05_VIEWS" / "STALE.sql").write_text("old")  # должен быть удалён очисткой

    n = write(ARTS, dd, WriteMode.FULL)
    assert n == 2
    assert (dd / "01_EXTERNAL_FUNCTIONS").is_dir()           # SUBDIRS пересозданы
    assert (dd / "04_TABLES/ACCOUNT.sql").read_text().endswith(";\n")
    assert "SET TERM ^ ;" in (dd / "07_FUNCTIONS/CALC.sql").read_text()
    assert not (dd / "05_VIEWS/STALE.sql").exists()          # дерево очищено


def test_tree_mode_does_not_wipe(tmp_path):
    dd = tmp_path / "database"
    (dd / "05_VIEWS").mkdir(parents=True)
    keep = dd / "05_VIEWS" / "KEEP.sql"
    keep.write_text("keep")

    write([Artifact("04_TABLES/ACCOUNT.sql", "CREATE TABLE ACCOUNT (B INT)")], dd, WriteMode.TREE)
    assert keep.read_text() == "keep"                        # чужой файл не тронут
    assert "B INT" in (dd / "04_TABLES/ACCOUNT.sql").read_text()


def test_stdout_mode_prints_and_skips_fs(tmp_path):
    dd = tmp_path / "nope"
    buf = io.StringIO()
    n = write(ARTS, dd, WriteMode.STDOUT, out=buf)
    text = buf.getvalue()
    assert n == 2
    assert "-- ===== 04_TABLES/ACCOUNT.sql =====" in text
    assert not dd.exists()                                   # ФС не трогаем


def test_empty_sql_skipped(tmp_path):
    dd = tmp_path / "database"
    n = write([Artifact("x/empty.sql", "   ")], dd, WriteMode.FULL)
    assert n == 0
