from fakes import FConstraint, FObj

from fbschema import categories
from fbschema.model import Context


def _arts(key, obj, **ctx_kw):
    cat = categories.CATEGORY_BY_KEY[key]
    ctx = Context(schema=None, dialect=3, **ctx_kw)
    return list(cat.artifacts_for(ctx, obj))


def test_generator_value_off_by_default():
    arts = _arts("generator", FObj("GEN_X", value=42))
    assert [a.sql for a in arts] == ["CREATE OBJ GEN_X"]


def test_generator_value_when_enabled():
    arts = _arts("generator", FObj("GEN_X", value=42), with_generator_values=True)
    assert any("RESTART WITH 42" in a.sql for a in arts)


def test_table_emits_create_then_ordered_constraints():
    t = FObj("ACC", constraints=[
        FConstraint("FK1", "fkey"),
        FConstraint("NN", "not_null"),   # должен быть пропущен
        FConstraint("PK1", "pkey"),
        FConstraint("CK1", "check"),
    ])
    arts = _arts("table", t)
    sqls = [a.sql for a in arts]
    assert sqls[0].startswith("CREATE OBJ ACC")
    kinds = [s for s in sqls if "CONSTRAINT" in s]
    # порядок: pkey, unique, check, fkey; not_null отсутствует
    assert "PK1" in kinds[0] and "CK1" in kinds[1] and "FK1" in kinds[2]
    assert not any("NN" in s for s in sqls)
    assert all(a.path == "04_TABLES/ACC.sql" for a in arts)


def test_function_declaration_and_body_are_separate_adjacent_files():
    arts = _arts("function", FObj("CALC"))
    paths = [a.path for a in arts]
    assert "07_FUNCTIONS/CALC.declaration.sql" in paths   # объявление — свой файл
    assert "07_FUNCTIONS/CALC.sql" in paths               # тело — обычный файл
    assert all(a.psql for a in arts)
    body = next(a.sql for a in arts if a.path == "07_FUNCTIONS/CALC.sql")
    assert body.startswith("ALTER")
    # соседство при сортировке: declaration идёт вплотную перед телом
    files = sorted(p.rsplit("/", 1)[1] for p in paths)
    assert files == ["CALC.declaration.sql", "CALC.sql"]


def test_procedure_declaration_and_body_separate():
    paths = {a.path for a in _arts("procedure", FObj("DOIT"))}
    assert paths == {"08_PROCEDURES/DOIT.declaration.sql", "08_PROCEDURES/DOIT.sql"}


def test_objects_filters_system_and_kind():
    from fakes import FSchema
    schema = FSchema(
        functions=[FObj("UDF", external=True), FObj("PSQL"), FObj("PKGFN", packaged=True)],
        generators=[FObj("G"), FObj("RDB$G", sys=True)],
        indices=[FObj("IDX"), FObj("ENF", enforcer=True)],
    )
    ext = [o.name for o in categories.CATEGORY_BY_KEY["external_function"].objects(schema)]
    psql = [o.name for o in categories.CATEGORY_BY_KEY["function"].objects(schema)]
    gens = [o.name for o in categories.CATEGORY_BY_KEY["generator"].objects(schema)]
    idx = [o.name for o in categories.CATEGORY_BY_KEY["index"].objects(schema)]
    assert ext == ["UDF"]
    assert psql == ["PSQL"]            # external и packaged исключены
    assert gens == ["G"]               # системный исключён
    assert idx == ["IDX"]              # enforcer исключён
