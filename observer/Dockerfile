FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY --from=build /app/dist /app/dist
COPY index.html /app/index.html
COPY maku.html /app/maku.html
COPY stage.html /app/stage.html
COPY brand.css /app/brand.css
COPY assets /app/assets
COPY rigged-avatar.js /app/rigged-avatar.js
COPY serve.py /app/serve.py
EXPOSE 3000
CMD ["python", "/app/serve.py"]
