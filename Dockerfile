FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY install-ngrok.sh /tmp/install-ngrok.sh
RUN chmod +x /tmp/install-ngrok.sh && /tmp/install-ngrok.sh && rm /tmp/install-ngrok.sh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY entrypoint.sh .
COPY . .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
