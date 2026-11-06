from app.engine.cache import generation_key


def test_generation_cache_is_scoped_to_database_policy_and_schema():
    args = ["db-a","total","model",{"orders":{"id":"int"}},{"mode":"QUERY_ONLY"},[]]
    key = generation_key(*args)
    for index, value in [(0,"db-b"),(1,"other question"),(2,"other model"),
                         (3,{"orders":{"id":"text"}}),(4,{"mode":"NONE"}),
                         (5,[("a","id","b","id")])]:
        changed = args.copy()
        changed[index] = value
        assert generation_key(*changed) != key
