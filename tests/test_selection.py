from fakes import FObj, FSchema

from fbschema import categories, selection


def _schema():
    return FSchema(
        functions=[FObj("UDF1", external=True), FObj("CALC")],   # PSQL CALC
        procedures=[FObj("CALC")],                                # коллизия имени CALC
        tables=[FObj("ACCOUNT")],
        generators=[FObj("GEN"), FObj("RDB$X", sys=True)],
        indices=[FObj("IDX"), FObj("ENF", enforcer=True)],
    )


def test_resolve_exact_and_case_insensitive():
    s = _schema()
    assert [c.key for c, _ in selection.resolve(s, ["ACCOUNT"]).matches] == ["table"]
    assert [c.key for c, _ in selection.resolve(s, ["account"]).matches] == ["table"]


def test_resolve_collision_across_categories():
    keys = sorted(c.key for c, _ in selection.resolve(_schema(), ["CALC"]).matches)
    assert keys == ["function", "procedure"]


def test_resolve_type_disambiguates():
    r = selection.resolve(_schema(), ["CALC"], type_alias="procedure")
    assert [c.key for c, _ in r.matches] == ["procedure"]


def test_resolve_missing_and_filters():
    assert selection.resolve(_schema(), ["NOPE"]).missing == ["NOPE"]
    assert selection.resolve(_schema(), ["RDB$X"]).missing == ["RDB$X"]          # системный
    assert selection.resolve(_schema(), ["ENF"], type_alias="index").missing == ["ENF"]  # enforcer


def test_expand_deps_transitive_and_cycle_safe(monkeypatch):
    # A -> B -> C -> A (цикл); D системный (не добавляется)
    a, b, c = FObj("A"), FObj("B"), FObj("C")
    d = FObj("D", sys=True)
    a._deps = [b, d]
    b._deps = [c]
    c._deps = [a]
    cat = categories.CATEGORY_BY_KEY["table"]

    def fake_category_of(obj):
        if getattr(obj, "_sys", False):
            return None
        return (cat, obj)

    monkeypatch.setattr(selection, "_category_of", fake_category_of)

    extra = selection.expand_deps(None, [(cat, a)])
    names = sorted(cat.name_of(o) for _, o in extra)
    assert names == ["B", "C"]   # A (seed) и D (sys) исключены, цикл не зациклил


def test_expand_deps_empty_when_no_deps(monkeypatch):
    cat = categories.CATEGORY_BY_KEY["table"]
    monkeypatch.setattr(selection, "_category_of", lambda o: (cat, o))
    assert selection.expand_deps(None, [(cat, FObj("LONE"))]) == []
