def test_spark_uses_utc(spark):
    assert spark.conf.get("spark.sql.session.timeZone") == "UTC"


def test_delta_write_and_read(spark, tmp_path):
    path = str(tmp_path / "table")
    spark.createDataFrame([(1, "a")], "id int, name string").write.format("delta").save(path)

    rows = spark.read.format("delta").load(path).collect()

    assert [tuple(r) for r in rows] == [(1, "a")]
