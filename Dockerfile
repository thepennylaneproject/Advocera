FROM python:3.12-slim

WORKDIR /app

COPY apps/ apps/
COPY db/ db/
COPY scripts/ scripts/
COPY seeds/ seeds/

RUN mkdir -p data

ENV DB_PATH=/app/data/advocera.db

EXPOSE 8080

# Apply migrations and start the API server.
CMD python3 scripts/run_migrations.py --db "$DB_PATH" && \
    python3 apps/api/server.py
