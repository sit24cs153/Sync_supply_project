import pandas as pd
import pytest

from app.data_loader import _validate, DatasetValidationError


def _valid_frames():
    herbs = pd.DataFrame([{"herb_id": "H01", "latin_name": "Ocimum sanctum", "name_en": "Tulsi"}])
    conditions = pd.DataFrame([{"condition_id": "C01", "category": "Respiratory", "symptoms_en": "cough|cold"}])
    remedies = pd.DataFrame([{"condition_id": "C01", "herb_id": "H01", "preparation_en": "Boil and drink."}])
    return herbs, conditions, remedies


def test_valid_dataset_passes():
    herbs, conditions, remedies = _valid_frames()
    _validate(herbs, conditions, remedies)  # should not raise


def test_rejects_missing_required_column():
    herbs, conditions, remedies = _valid_frames()
    herbs = herbs.drop(columns=["name_en"])
    with pytest.raises(DatasetValidationError):
        _validate(herbs, conditions, remedies)


def test_rejects_duplicate_herb_id():
    herbs, conditions, remedies = _valid_frames()
    herbs = pd.concat([herbs, herbs], ignore_index=True)
    with pytest.raises(DatasetValidationError):
        _validate(herbs, conditions, remedies)


def test_rejects_remedy_with_unknown_condition_id():
    herbs, conditions, remedies = _valid_frames()
    remedies.loc[0, "condition_id"] = "C99"
    with pytest.raises(DatasetValidationError):
        _validate(herbs, conditions, remedies)


def test_rejects_remedy_with_unknown_herb_id():
    herbs, conditions, remedies = _valid_frames()
    remedies.loc[0, "herb_id"] = "H99"
    with pytest.raises(DatasetValidationError):
        _validate(herbs, conditions, remedies)


def test_rejects_empty_preparation_text():
    herbs, conditions, remedies = _valid_frames()
    remedies.loc[0, "preparation_en"] = ""
    with pytest.raises(DatasetValidationError):
        _validate(herbs, conditions, remedies)
