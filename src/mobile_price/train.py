import hashlib
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import mlflow
import pandas as pd
import sklearn
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import ConfusionMatrixDisplay, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DATA_PATH = Path(os.getenv("DATA_PATH", "data/train.csv"))
MODEL_NAME = os.getenv("MODEL_NAME", "mobile_price")
EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "mobile_price")
C = float(os.getenv("C", "1.0"))
MIN_GAIN = float(os.getenv("GATE_MIN_GAIN", "0.001"))
SEED = 42
SKOPS_TRUSTED = ["numpy.dtype", "sklearn.compose._column_transformer._RemainderColsList"]

COLUMNS = [
    'battery_power',
    'blue',
    'dual_sim',
    'fc',
    'four_g',
    'clock_speed',
    'm_dep',
    'int_memory',
    'mobile_wt',
    'n_cores',
    'pc',
    'px_height',
    'px_width',
    'ram',
    'sc_h',
    'sc_w',
    'talk_time',
    'three_g',
    'touch_screen',
    'wifi'
]


def load_and_validate(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = set(COLUMNS + ["price_range"]) - set(df.columns)
    if missing:
        raise ValueError(f"в данных нет колонок: {sorted(missing)}")
    if len(df) < 1000:
        raise ValueError(f"слишком мало строк: {len(df)}")
    if not set(df["price_range"].unique()) <= {1, 2, 3, 0}:
        raise ValueError(f"неожиданные значения таргета: {df['price_range'].unique()[:5]}")
    return df


def build_pipeline(c: float) -> Pipeline:
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', LogisticRegression(max_iter=1000, C=c))
    ])
    return pipeline

def champion_f1_score(client: MlflowClient) -> tuple[str | None, float | None]:
    try:
        mv = client.get_model_version_by_alias(MODEL_NAME, "champion")
    except MlflowException:
        return None, None
    return mv.version, client.get_run(mv.run_id).data.metrics.get("f1_score_macro")

def main() -> dict:
    df = load_and_validate(DATA_PATH)
    data_md5 = hashlib.md5(DATA_PATH.read_bytes()).hexdigest()
    features = COLUMNS
    x_train, x_test, y_train, y_test = train_test_split(
        df[features], df["price_range"], test_size=0.2, stratify=df["price_range"], random_state=SEED)

    pipeline = build_pipeline(C).fit(x_train, y_train)
    y_pred = pipeline.predict(x_test)
    f1 = float(f1_score(y_test, y_pred, average="macro"))
    recall = recall_score(y_test, y_pred, average="macro")
    precision = precision_score(y_test, y_pred, average="macro")


    mlflow.set_experiment(EXPERIMENT)
    client = MlflowClient()
    with mlflow.start_run() as run:
        metadata = {"features": features, "n_train": len(x_train),
                    "data_rows": len(df), "sklearn": sklearn.__version__}
        mlflow.log_params({"C": C, "model": "LogisticRegression", "seed": SEED, "data": str(DATA_PATH),"data_md5": data_md5})
        mlflow.log_metrics({"f1_score_macro": round(f1, 4), "recall_macro":round(recall, 4), "precision_macro": round(precision, 4)})
        mlflow.log_dict(metadata, "metadata.json")
        info = mlflow.sklearn.log_model(pipeline, name="model", registered_model_name=MODEL_NAME,
                                        skops_trusted_types=SKOPS_TRUSTED)
        version = info.registered_model_version

        display = ConfusionMatrixDisplay.from_predictions(
            y_test, y_pred, labels=[0, 1, 2, 3], cmap="Blues"
        )
        display.figure_.tight_layout()
        mlflow.log_figure(display.figure_, "confusion_matrix.png")
        plt.close(display.figure_)

    old_version, old_f1 = champion_f1_score(client)
    promoted = old_f1 is None or f1 > old_f1 + MIN_GAIN
    client.set_registered_model_alias(MODEL_NAME, "challenger", version)
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, "champion", version)

    result = {"run_id": run.info.run_id, "version": version, "f1_score_macro": f1,
              "champion_before": old_version, "champion_f1_before": old_f1, "promoted": promoted}
    print(json.dumps(result, ensure_ascii=False))
    xcom = Path("/airflow/xcom")
    if xcom.is_dir():
        (xcom / "return.json").write_text(json.dumps(result))
    return result


if __name__ == "__main__":
    main()