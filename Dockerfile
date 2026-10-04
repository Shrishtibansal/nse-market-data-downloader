FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV NSE_OUTPUT_DIR=/data
VOLUME ["/data", "/app/logs"]
ENTRYPOINT ["python", "main.py"]
