import io
from contextlib import redirect_stdout

import pytest
from fakes import FObj, FSchema

from fbschema import cli
from fbschema.model import Context


# ---- argparse / валидация (до подключения к БД) → exit 2 ----

@pytest.mark.parametrize("argv", [
    ["fb-dump-schema", "--list", "FOO"],          # --list + имя
    ["fb-dump-schema", "--stdout"],               # --stdout без имён
    ["fb-dump-schema", "--with-deps"],            # --with-deps без имён
    ["fb-dump-schema", "--type", "zzz"],          # неизвестный тип
    ["fb-dump-schema", "--type", "table"],        # --type в полном режиме
])
def test_argparse_validation_exits_2(argv):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 2


# ---- диспетчеры с фейковым Context (без БД) ----

def _ctx():
    return Context(
        schema=FSchema(
            tables=[FObj("ACCOUNT", columns=[])],
            procedures=[FObj("CALC")],
            generators=[FObj("GEN")],
            roles=[FObj("R")],
        ),
        dialect=3,
    )


def test_run_list_prints_categories():
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.run_list(_ctx(), None)
    out = buf.getvalue()
    assert code == 0
    assert "# table (1)" in out and "ACCOUNT" in out


def test_run_list_type_filter():
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.run_list(_ctx(), "procedure")
    out = buf.getvalue()
    assert "# procedure" in out and "# table" not in out


def test_run_targeted_writes_tree(tmp_path):
    dd = tmp_path / "out"
    code = cli.run_targeted(_ctx(), dd, ["ACCOUNT"], None, False, False)
    assert code == 0
    assert (dd / "04_TABLES/ACCOUNT.sql").exists()


def test_run_targeted_missing_returns_3(tmp_path):
    code = cli.run_targeted(_ctx(), tmp_path / "out", ["NOPE"], None, False, False)
    assert code == 3


def test_run_full_writes_preamble_and_objects(tmp_path):
    dd = tmp_path / "full"
    code = cli.run_full(_ctx(), dd)
    assert code == 0
    assert (dd / "DATABASE.sql").read_text().startswith("SET SQL DIALECT 3")
    assert (dd / "04_TABLES/ACCOUNT.sql").exists()
    assert (dd / "11_ROLES/ROLES.sql").exists()
