FROM python:3.11-slim

WORKDIR /app
COPY runner.py /app/runner.py
USER 65534:65534
ENTRYPOINT ["python", "/app/runner.py"]
