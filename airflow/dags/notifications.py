import logging

logger = logging.getLogger(__name__)


def task_failure_alert(context):
    task_instance = context.get("task_instance")
    dag_run = context.get("dag_run")

    task_id = task_instance.task_id if task_instance else "unknown"
    dag_id = dag_run.dag_id if dag_run else "unknown"
    logical_date = dag_run.logical_date if dag_run else "unknown"
    exception = context.get("exception", "Erreur inconnue")

    logger.error(
        "Échec Airflow | dag_id=%s | task_id=%s | logical_date=%s | exception=%s",
        dag_id,
        task_id,
        logical_date,
        exception,
    )