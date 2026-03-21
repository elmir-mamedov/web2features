FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY uv.lock .

RUN pip install uv
RUN uv sync --no-dev --no-editable

COPY . .

EXPOSE 8080

CMD ["python", "app.py"]