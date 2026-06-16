import pytest

from fbschema import config


def _write_env(tmp_path, extra=""):
    p = tmp_path / "t.env"
    p.write_text("ISC_USER=U\nISC_PASSWORD=P\nFB_DATABASE=x\nDUMP_DIR=d\n" + extra)
    return p


def test_load_minimal(tmp_path):
    _write_env(tmp_path)
    cfg = config.load("t.env", tmp_path)
    assert cfg.user == "U" and cfg.password == "P" and cfg.database == "x"
    assert cfg.dump_dir == tmp_path / "d"
    assert cfg.charset == "UTF8"          # дефолт
    assert cfg.audit_log is True          # дефолт
    assert cfg.timeout == 0


def test_missing_required_raises(tmp_path):
    p = tmp_path / "bad.env"
    p.write_text("ISC_USER=U\n")
    with pytest.raises(config.ConfigError):
        config.load("bad.env", tmp_path)


def test_missing_file_raises(tmp_path):
    with pytest.raises(config.ConfigError):
        config.load("nope.env", tmp_path)


@pytest.mark.parametrize("val,expected", [
    ("false", False), ("0", False), ("no", False), ("off", False),
    ("true", True), ("1", True), ("yes", True),
])
def test_audit_log_parsing(tmp_path, val, expected):
    _write_env(tmp_path, f"AUDIT_LOG={val}\n")
    cfg = config.load("t.env", tmp_path)
    assert cfg.audit_log is expected


def test_charset_and_timeout(tmp_path):
    _write_env(tmp_path, "DB_CHARSET=WIN1251\nISQL_TIMEOUT=120\n")
    cfg = config.load("t.env", tmp_path)
    assert cfg.charset == "WIN1251"
    assert cfg.timeout == 120


def test_bad_timeout_raises(tmp_path):
    _write_env(tmp_path, "ISQL_TIMEOUT=abc\n")
    with pytest.raises(config.ConfigError):
        config.load("t.env", tmp_path)
