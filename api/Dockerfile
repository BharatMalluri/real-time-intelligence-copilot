FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir fastapi==0.111.0 uvicorn==0.30.1 psycopg2-binary==2.9.9 pydantic==2.7.4 requests==2.32.3

COPY . .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]