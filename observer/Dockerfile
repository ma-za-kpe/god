FROM python:3.11-slim
WORKDIR /app
COPY index.html /app/index.html
EXPOSE 3000
CMD ["python", "-m", "http.server", "3000", "--directory", "/app"]
