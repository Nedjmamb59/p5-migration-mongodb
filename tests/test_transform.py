"""Tests unitaires : intégrité du CSV et nettoyage (sans base de données)."""
from datetime import datetime

import pandas as pd
import pytest
from bson.decimal128 import Decimal128

from app.transform import (ALLOWED_VALUES, EXPECTED_COLUMNS, audit_dataframe,
                           clean_dataframe, row_to_document, to_documents, to_money)


def test_all_expected_columns_present(raw_df):
    assert list(raw_df.columns) == EXPECTED_COLUMNS


def test_audit_report(raw_df):
    report = audit_dataframe(raw_df)
    assert report["rows"] == 55_500
    assert report["missing_values"] == {}
    assert report["non_numeric"] == {}
    assert report["invalid_dates"] == {}
    assert report["unexpected_categories"] == {}
    assert report["exact_duplicates"] == 534


def test_audit_rejects_missing_column(raw_df):
    with pytest.raises(ValueError, match="Colonnes manquantes"):
        audit_dataframe(raw_df.drop(columns=["Age"]))


def test_clean_types(clean_df):
    assert clean_df["Age"].dtype == "int64"
    assert clean_df["Room Number"].dtype == "int64"
    assert clean_df["Billing Amount"].dtype == "float64"
    assert pd.api.types.is_datetime64_any_dtype(clean_df["Date of Admission"])
    assert pd.api.types.is_datetime64_any_dtype(clean_df["Discharge Date"])


def test_clean_removes_duplicates_only(raw_df, clean_df):
    assert clean_df.duplicated().sum() == 0
    assert len(clean_df) == len(raw_df) - 534


def test_clean_normalizes_text(clean_df):
    assert (clean_df["Name"] == clean_df["Name"].str.title()).all()
    assert not clean_df["Hospital"].str.endswith(",").any()


def test_no_missing_values_after_clean(clean_df):
    assert clean_df.isna().sum().sum() == 0


def test_discharge_after_admission(clean_df):
    assert (clean_df["Discharge Date"] >= clean_df["Date of Admission"]).all()


def test_categories_within_allowed(clean_df):
    for col, allowed in ALLOWED_VALUES.items():
        assert set(clean_df[col].unique()) <= allowed


def test_to_money_rounding():
    assert to_money(18856.281306) == Decimal128("18856.28")
    assert to_money(-2008.4951) == Decimal128("-2008.50")


def test_row_to_document_structure(clean_df):
    doc = row_to_document(clean_df.iloc[0].to_dict())
    assert set(doc) == {"patient", "admission", "medical", "hospital", "billing"}
    assert doc["patient"]["name"] == "Bobby Jackson"
    assert isinstance(doc["admission"]["admission_date"], datetime)
    assert isinstance(doc["billing"]["amount"], Decimal128)


def test_one_document_per_row(clean_df):
    assert len(to_documents(clean_df.head(100))) == 100