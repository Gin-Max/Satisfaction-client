from pathlib import Path

import pytest
from airflow.models import DagBag
from airflow.utils.dag_cycle_tester import check_cycle


DAGS_FOLDER = Path(__file__).resolve().parents[1] / "airflow" / "dags"


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(
        dag_folder=str(DAGS_FOLDER),
        include_examples=False,
    )


def test_dags_load_without_errors(dagbag):
    assert dagbag.import_errors == {}, dagbag.import_errors


def test_scraping_dag_is_present(dagbag):
    assert "scraping_reviews_weekly" in dagbag.dags


def test_scraping_dag_has_expected_tasks(dagbag):
    dag = dagbag.get_dag("scraping_reviews_weekly")

    expected_tasks = {
        "backfill_existing_reviews",
        "scrape_trustpilot",
        "scrape_google",
        "enrich_trustpilot",
        "enrich_google",
        "load_trustpilot",
        "load_google",
    }

    actual_tasks = {task.task_id for task in dag.tasks}

    assert expected_tasks.issubset(actual_tasks)


def test_dags_have_no_cycles(dagbag):
    for dag_id, dag in dagbag.dags.items():
        check_cycle(dag)


def test_scraping_tasks_have_failure_callback(dagbag):
    dag = dagbag.get_dag("scraping_reviews_weekly")

    for task in dag.tasks:
        assert task.on_failure_callback is not None, (
            f"La tâche {task.task_id} n'a pas de callback d'échec"
        )
