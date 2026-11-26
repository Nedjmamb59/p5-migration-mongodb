"""Tests d'intégration : à lancer APRÈS la migration, contre la vraie base."""
from datetime import datetime

import pytest
from pymongo.errors import OperationFailure, WriteError

from app.database import INDEXES
from app.integrity import compare_with_source


def test_post_migration_checks(collection, clean_df):
    checks = compare_with_source(collection, clean_df)
    assert all(checks.values()), checks


def test_indexes_exist(collection):
    assert {name for _, name in INDEXES} <= set(collection.index_information())


def test_sample_document_matches_csv(collection, clean_df):
    row = clean_df.iloc[0]
    doc = collection.find_one({"patient.name": row["Name"],
                               "admission.admission_date": row["Date of Admission"].to_pydatetime()})
    assert doc["medical"]["condition"] == row["Medical Condition"]


def test_validator_rejects_bad_document(collection):
    """MongoDB doit refuser un âge écrit en lettres."""
    with pytest.raises(WriteError):
        collection.insert_one({"patient": {"name": "X", "age": "trente"}})


def test_index_is_used_for_condition_query(collection):
    plan = collection.find({"medical.condition": "Cancer",
                            "admission.admission_date": {"$gte": datetime(2023, 1, 1)}}).explain()
    assert "idx_condition_admission_date" in str(plan["queryPlanner"]["winningPlan"])


def test_analyst_can_read_but_not_write(role_client):
    col = role_client("ANALYST_USER", "ANALYST_PASSWORD")
    assert col.count_documents({}) > 0
    with pytest.raises(OperationFailure):
        col.insert_one({"hack": True})


def test_app_user_cannot_delete(role_client):
    col = role_client("APP_USER", "APP_PASSWORD")
    with pytest.raises(OperationFailure):
        col.delete_one({})


def test_app_user_cannot_drop_collection(role_client):
    col = role_client("APP_USER", "APP_PASSWORD")
    with pytest.raises(OperationFailure):
        col.drop()