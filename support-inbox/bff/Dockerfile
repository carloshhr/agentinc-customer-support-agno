FROM python:3.14-slim
WORKDIR /service
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app app
COPY migrations migrations
COPY alembic.ini retention.py .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
