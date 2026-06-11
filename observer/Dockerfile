FROM python:3.11-slim
WORKDIR /app
COPY index.html /app/index.html
COPY brand.css /app/brand.css
COPY assets /app/assets
EXPOSE 3000
CMD ["python", "-m", "http.server", "3000", "--directory", "/app"]
