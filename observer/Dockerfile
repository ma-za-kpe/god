FROM python:3.11-slim
WORKDIR /app
COPY index.html /app/index.html
COPY maku.html /app/maku.html
COPY brand.css /app/brand.css
COPY assets /app/assets
COPY serve.py /app/serve.py
EXPOSE 3000
CMD ["python", "/app/serve.py"]
