from datetime import UTC, datetime

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.sdk import CronTriggerTimetable, Param, dag, task
from kubernetes.client import models as k8s


@dag(
    schedule=CronTriggerTimetable("0 3 * * *", timezone="Europe/Moscow"),
    catchup=False,
    params= {"C":Param(1.0, type='number', exclusiveMinimum=0, description='regularization Log reg')},
    tags=['mobile_price'],
)

def mobile_price_retrain():
    validate = KubernetesPodOperator(
        task_id="validate",
        name="mobile-price-validate",
        namespace="mlops",
        in_cluster=True,
        image="{{ var.value.mobile_price_image }}",
        image_pull_policy="IfNotPresent",
        cmds=[
            "sh", "-c",
            "uv run --no-sync dvc pull -r cluster data/train.csv && uv run --no-sync python -m mobile_price.data",
        ],
        env_vars={"MLFLOW_TRACKING_URI": "http://mlflow.mlops:5000"},
        env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="s3-credentials"))],
        get_logs=True,
        on_finish_action="delete_pod",
    )

    train = KubernetesPodOperator(
        task_id='train',
        name='mobile_price_train',
        namespace='mlops',
        in_cluster=True,
        image="{{ var.value.mobile_price_image }}",
        image_pull_policy="IfNotPresent",
        cmds = ["sh", "-c",
                "uv run --no-sync dvc pull -r cluster data/train.csv && uv run --no-sync python -m mobile_price.train"],
        env_vars = {"MLFLOW_TRACKING_URI": "http://mlflow.mlops:5000", "C": "{{ params.C }}"},
        env_from = [k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="s3-credentials"))],
        do_xcom_push = True,
        get_logs = True,
        on_finish_action = "delete_pod",
    )

    @task.short_circuit
    def promoted(result: dict) -> bool:
        print(f"версия {result['version']}, F1 {result['f1_score_macro']}, champion до этого {result['champion_before']}")
        return result["promoted"]

    @task
    def rollout():
        from kubernetes import client, config

        config.load_incluster_config()
        now = datetime.now(UTC).isoformat()
        client.AppsV1Api().patch_namespaced_deployment(
            "mobile-service", "default",
            {"spec": {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": now}}}}},
        )
        print("mobile-service перезапущен", now)

    validate >> train
    promoted(train.output) >> rollout()


mobile_price_retrain()
