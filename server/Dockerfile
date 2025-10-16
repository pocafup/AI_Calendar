
FROM python:3.11-slim

WORKDIR /app

RUN pip install --upgrade pip && pip install "poetry==2.1.2"

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-interaction --no-root --no-ansi

COPY server/src/ ./src

EXPOSE 5003
CMD ["poetry","run","python","src/server.py"]
