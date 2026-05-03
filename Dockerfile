FROM python:3.11-slim

WORKDIR /app

COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary

COPY agent/ .
RUN pip install --no-cache-dir -e .

EXPOSE 8080

CMD ["uvicorn", "flowboard.main:app", "--host", "0.0.0.0", "--port", "8080"]
