import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

DATA_PATH = Path(os.getenv("DATA_PATH", "data/train.csv"))
EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "mobile_price")

# Границы с запасом относительно обучающего датасета: battery_power 501–1998,
# ram 256–3998, clock_speed 0.5–3.0. Отрицательные значения недопустимы.
ROWS = pa.DataFrameSchema(
    {
        "battery_power": pa.Column(int, pa.Check.in_range(1, 2500)),
        "blue": pa.Column(int, pa.Check.isin([0, 1])),
        "clock_speed": pa.Column(float, pa.Check.in_range(0.1, 4.0)),
        "dual_sim": pa.Column(int, pa.Check.isin([0, 1])),
        "fc": pa.Column(int),
        "four_g": pa.Column(int, pa.Check.isin([0, 1])),
        "int_memory": pa.Column(int),
        "m_dep": pa.Column(float),
        "mobile_wt": pa.Column(int),
        "n_cores": pa.Column(int),
        "pc": pa.Column(int),
        "px_height": pa.Column(int),
        "px_width": pa.Column(int),
        "ram": pa.Column(int, pa.Check.in_range(1, 5000)),
        "sc_h": pa.Column(int),
        "sc_w": pa.Column(int),
        "talk_time": pa.Column(int),
        "three_g": pa.Column(int, pa.Check.isin([0, 1])),
        "touch_screen": pa.Column(int, pa.Check.isin([0, 1])),
        "wifi": pa.Column(int, pa.Check.isin([0, 1])),
        "price_range": pa.Column(int, pa.Check.isin([0, 1, 2, 3])),
    },
    strict=True,
)

# В исходной выборке каждый класс составляет 25%; допускаем снижение до 10%.
EXPORT = pa.DataFrameSchema(
    ROWS.columns,
    checks=[
        pa.Check(lambda df: len(df) >= 1000, error="меньше 1000 строк"),
        pa.Check(
            lambda df: df["price_range"].value_counts(normalize=True)
            .reindex([0, 1, 2, 3], fill_value=0).ge(0.1).all(),
            error="доля одного из классов цены меньше 10%",
        ),
    ],
    strict=True,
)


def file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def load_raw(path: Path = DATA_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    # Не удаляем неправильные строки: схема должна обнаружить ошибки.
    return raw.reset_index(drop=True)


def load_clean(path: Path = DATA_PATH) -> pd.DataFrame:
    return EXPORT.validate(clean(load_raw(path)), lazy=True)


def main() -> int:
    import mlflow

    raw = load_raw()
    df = clean(raw)
    md5 = file_md5(DATA_PATH)
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name="validate"):
        mlflow.log_params({"step": "validate", "data": str(DATA_PATH), "data_md5": md5})
        mlflow.log_metrics({"raw_rows": len(raw), "clean_rows": len(df)})
        try:
            EXPORT.validate(df, lazy=True)
        except pa.errors.SchemaErrors as exc:
            failures = exc.failure_cases
            summary = failures.groupby(["column", "check"], dropna=False).size().rename("cases").reset_index()
            with tempfile.TemporaryDirectory() as tmp:
                report = Path(tmp) / "failure_cases.csv"
                failures.to_csv(report, index=False)
                mlflow.log_artifact(str(report))
            mlflow.log_metric("failed_checks", len(summary))
            mlflow.set_tag("valid", "false")
            print("Данные не прошли проверку, отчёт failure_cases.csv в MLflow:")
            print(summary.to_string(index=False))
            return 1
        mlflow.set_tag("valid", "true")

    print(json.dumps({"valid": True, "data_md5": md5, "rows": len(df)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
