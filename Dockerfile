FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev --no-install-project

COPY src/ src/
RUN uv sync --no-dev

COPY artifacts/ artifacts/

COPY .dvc/config .dvc/config
COPY data/*.dvc data/
RUN uv run --no-sync dvc config --local core.no_scm true

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "mobile_price.service.app:app", "--host", "0.0.0.0", "--port", "8000"]







## устанавливаем uv
#COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
#
## рабочая директория
#WORKDIR /app
#
## переносим всё в папку директории
#COPY pyproject.toml uv.lock ./
#
## команда инициализации
## --frozen - чтобы версии не менял
## --no-instal-project - чтобы не устанвлял версии, как отдельный пакет
## --no-dev - не смотрел dev зависимости
#RUN uv sync --frozen --no-install-project --no-dev
#
#COPY src/ src/
#
#RUN uv sync --frozen --no-dev
#
#COPY artifacts/ artifacts/
#
#EXPOSE 8000
#CMD ["uv", "run", "--no-sync", "uvicorn", "mobile_price.service.app:app", "--host", "0.0.0.0", "--port", "8000"]
