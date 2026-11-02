FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app


FROM base AS test

COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY tests ./tests

USER appuser
CMD ["python", "-m", "pytest", "-v", "-p", "no:cacheprovider"]


FROM base AS runtime

USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
