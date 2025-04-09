FROM python:3.12-alpine as builder

# Create app directory
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-alpine
RUN apk update && apk add git
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN mkdir -p /app/results
WORKDIR /app

COPY saist .

# Exports
ENV SAIST_COMMAND "docker run punksecurity/saist" 
ENV SAIST_CSV_PATH "/app/results.csv" 
ENV PYTHONUNBUFFERED 1
ENTRYPOINT [ "python3", "/app/main.py" ]
CMD [ "-h" ]
