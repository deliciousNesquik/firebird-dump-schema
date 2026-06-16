from fbschema.render import fname, render


def test_fname_sanitizes_separators():
    assert fname("ACCOUNT") == "ACCOUNT.sql"
    assert fname("A/B\\C") == "A_B_C.sql"
    assert fname("  X  ") == "X.sql"


def test_render_non_psql_terminates_with_semicolon():
    out = render(["CREATE TABLE T (A INT)", "ALTER TABLE T ADD X INT"], psql=False)
    lines = out.splitlines()
    assert lines[0].endswith(";")
    assert all(not l or l.endswith(";") for l in lines)
    assert "SET TERM" not in out


def test_render_psql_wraps_set_term():
    out = render(["CREATE PROCEDURE P AS BEGIN END"], psql=True)
    assert out.startswith("SET TERM ^ ;")
    assert out.rstrip().endswith("SET TERM ; ^")
    assert "\n^\n" in out


def test_render_psql_strips_existing_terminator():
    out = render(["CREATE TRIGGER T ... END^"], psql=True)
    # тело не должно содержать двойной ^^
    assert "^^" not in out
