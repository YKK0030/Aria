FROM python:3.11-slim

WORKDIR /app
COPY runner.py /app/runner.py
COPY server.py /app/server.py
RUN mkdir -p /run/aria-tool-tests && chmod 1777 /run/aria-tool-tests
USER 65534:65534
ENTRYPOINT ["python", "/app/runner.py"]
