import importlib
import pytest

pytest.importorskip("airflow.decorators")


def test_scraping_dag_imports():
    module = importlib.import_module("airflow.dags.scraping_dag")
    assert hasattr(module, "dag")


def test_ml_retraining_dag_imports():
    module = importlib.import_module("airflow.dags.ml_retraining_dag")
    assert hasattr(module, "dag")