FROM python:3.11-slim AS base

WORKDIR /app

RUN pip install --upgrade pip && pip install "poetry==2.1.2" 

COPY pyproject.toml poetry.lock* ./ 

RUN poetry install --no-interaction --no-root --no-ansi 

COPY . .

EXPOSE 5000

CMD ["poetry","run", "python", "client/src/app.py"]
