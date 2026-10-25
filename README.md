# Mobile Price

Сервис предсказывает класс цены телефона от 0 до 3 по его характеристикам.
Модель — StandardScaler и LogisticRegression. При запуске в кластере сервис
загружает модель `mobile_price` по алиасу `champion` из MLflow Registry.

## Quickstart
### 1. Подготовка

Нужны Git, uv, Docker с Linux-контейнерами, kind, kubectl, Helm и curl
Все команды ниже выполняются в **Git Bash** на Windows либо Bash на Linux/macOS.

```bash
git clone https://github.com/Stolide-anseed/Homework.git
cd Homework
uv sync --frozen
```

### 2. Платформа одной командой

```bash
bash platform/up.sh
```

Скрипт создаёт кластер `hw` с пробросом порта 80, устанавливает Traefik,
MLflow, Airflow, RustFS, Prometheus и Grafana, затем создаёт бакет `dvc`.
Имя `hw` согласовано с `KIND_CLUSTER` в CI.

```bash
bash platform/up.sh
```

Проверка из Git Bash:

```bash
kubectl --context kind-hw get pods -A
kubectl --context kind-hw get ingress -A
curl --fail --show-error http://mlflow.localhost/health
curl --fail --show-error --aws-sigv4 "aws:amz:us-east-1:s3" \
  --user 'dvcadmin:dvc-secret-123' 'http://s3.localhost/dvc?list-type=2'
```
### 3. DNS на Windows

Браузер и curl могут открывать `*.localhost`, даже если Python не разрешает эти имена.
Проверьте:

```bash
uv run python -c "import socket; print(socket.gethostbyname('mlflow.localhost')); print(socket.gethostbyname('s3.localhost'))"
```

Оба адреса должны быть `127.0.0.1`. Если это не так, откройте от администратора
`C:\Windows\System32\drivers\etc\hosts` и добавьте строку:

```text
127.0.0.1 mlflow.localhost s3.localhost s3-console.localhost airflow.localhost grafana.localhost mobile.localhost
```

Повторите проверку Python. На Linux/macOS при необходимости используются такие же записи в `/etc/hosts`.

### 4. Данные и первый dvc push в S3

Текущая общая конфигурация DVC ещё указывает на прежнюю локальную папку.
Для этого Quickstart переопределяем remote и ключи в игнорируемом Git файле
`.dvc/config.local`:

```bash
uv run dvc remote add --local -f -d laptop s3://dvc
uv run dvc remote modify --local laptop endpointurl http://s3.localhost
uv run dvc remote modify --local laptop access_key_id dvcadmin
uv run dvc remote modify --local laptop secret_access_key dvc-secret-123
```

В новом кластере бакет пустой. Исходный `train.csv` восстанавливаем из коммита,
где он ещё хранился в Git, и проверяем совпадение с DVC-указателем:

```bash
git show f0318cff058d6c56bf65afcabb6cf9e5aec5444c:data/train.csv > data/train.csv
uv run python -c "import hashlib; from pathlib import Path; actual=hashlib.md5(Path('data/train.csv').read_bytes()).hexdigest(); assert actual == 'e8c4560161dc3c8571b5b2db25be3294', actual; print('MD5 OK:', actual)"
uv run dvc push data/train.csv.dvc -r laptop
```

Это первоначальная загрузка исходного обучающего датасета, а не восстановление
всех версий данных. Если S3 уже наполнен, вместо извлечения файла из истории
можно выполнить `uv run dvc pull data/train.csv.dvc -r laptop`.

### 5. Обучение первого champion

```bash
MLFLOW_TRACKING_URI=http://mlflow.localhost \
DATA_PATH=data/train.csv MODEL_NAME=mobile_price C=1 \
uv run python -u -m mobile_price.train
```

В новом реестре первая модель должна получить `promoted: true`.
В MLflow → Model registry → `mobile_price` проверьте наличие алиаса `champion`.
В уже используемом реестре гейт может не продвинуть новую модель — это нормально,
если действующий `champion` существует. Удалённый эксперимент перед повторным
обучением нужно восстановить.

### 6. GitHub Secret и self-hosted runner

В своём репозитории откройте Settings → Secrets and variables → Actions и
создайте repository secret `DB_PASSWORD`: непустой случайный пароль из латинских
букв и цифр. Он будет использоваться и базой, и приложением. Не меняйте его
при повторных деплоях без согласованной смены пароля внутри PostgreSQL.

В Settings → Actions → General включите
`Require approval for all external contributors`.

Затем Settings → Actions → Runners → New self-hosted runner → Linux.
Скопируйте регистрационный токен после `--token` из предложенной команды.
Он должен относиться к тому же репозиторию, откуда будет запущен workflow.

В отдельном Git Bash из каталога клона:

```bash
REPO_URL=$(git remote get-url origin)
REPO_URL=${REPO_URL%.git}
read -rsp 'RUNNER_TOKEN: ' RUNNER_TOKEN
echo

MSYS_NO_PATHCONV=1 docker run -d \
  --name gh-runner --network kind --group-add 0 \
  --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e REPO_URL="$REPO_URL" -e RUNNER_TOKEN="$RUNNER_TOKEN" \
  ghcr.io/actions/actions-runner:2.337.0 \
  bash -c 'if [ ! -f .runner ]; then ./config.sh --unattended --url "$REPO_URL" --token "$RUNNER_TOKEN" --name hw-kind --labels kind || exit 1; fi; exec ./run.sh'

unset RUNNER_TOKEN
docker logs --tail 30 -f gh-runner
```

Эта команда рассчитана на свежую установку без контейнера `gh-runner` и
одноимённой регистрации `hw-kind`. Если они уже есть, используйте работающий
runner, не создавайте второй. URL выше рассчитан на HTTPS-клонирование.

Дождитесь `Listening for Jobs` и статуса `Idle` в GitHub. Ctrl+C завершает
только просмотр логов. Runner получает доступ к Docker хоста: не допускайте
выполнения на нём непроверенных заданий из чужих PR.

### 7. Первый деплой по кнопке

В GitHub откройте Actions → ci → Run workflow → ветка `main` → Run workflow.
В fork предварительно включите Actions. Настройки и изменения проекта должны
быть закоммичены в этой ветке: CI не использует незакоммиченные локальные файлы.

Дождитесь успеха `tests`, `build`, `deploy`. Образ публикуется в GHCR с тегом
`sha-<коммит>`, затем runner загружает его в кластер, создаёт Secret, базу и сервис.
До деплоя первого сервиса обязательно должен существовать `champion` из шага 5.

### 8. Ответ через Ingress и доказательства

```bash
kubectl --context kind-hw rollout status deployment/mobile-service --timeout=180s
curl --fail --show-error http://mobile.localhost/health
curl --fail --show-error -X POST http://mobile.localhost/v1/predict \
  -H 'Content-Type: application/json' -d @test.json
kubectl --context kind-hw get pods -A
```

В `/health` ожидается версия вида `mobile_price-vN`, в ответе `/v1/predict` —
`mobile_price` от 0 до 3 и `request_id`. Запросы идут через Ingress, без port-forward.
Для пункта 1 сохраните вывод с готовыми Pod и в отчёте укажите реальное время
от начала подготовки до успешного ответа. Сквозной запуск по этой инструкции
в чистом кластере ещё требуется проверить; замер времени не подменяется оценкой.

### Адреса интерфейсов

| Компонент | Адрес |
|---|---|
| Сервис | http://mobile.localhost/docs |
| MLflow | http://mlflow.localhost |
| Airflow | http://airflow.localhost |
| Grafana | http://grafana.localhost — учебные `admin` / `admin` |
| S3 API | http://s3.localhost |
| S3 Console | http://s3-console.localhost/rustfs/console/index.html |

Ключи S3 `dvcadmin` / `dvc-secret-123` — только для локальной учебной установки.
Не публикуйте эту платформу в интернет с настройками по умолчанию.

### Повторная проверка с нуля

Сначала сохраните нужные модели MLflow и данные S3 вне кластера: удаление kind
может уничтожить эти данные. Только после резервного копирования для отдельного
контрольного прогона удалите кластер `hw`, создайте свежий клон и повторите шаги
Quickstart. Рабочий кластер автоматически эта инструкция не удаляет.

После сдачи остановите и удалите контейнер runner командой
`docker rm -f gh-runner`, а его регистрацию — через Remove в Settings → Actions → Runners.
