FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git libcairo2-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-webhook.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-webhook.txt

COPY . .

ENV PYTHONPATH=/app/src
ENV PORT=8080

CMD ["python", "-m", "peachtree_blog.slack_webhook.app"]
