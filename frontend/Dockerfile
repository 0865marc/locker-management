FROM node:24-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG PUBLIC_API_BASE_URL=http://127.0.0.1:8000
ENV ASTRO_TELEMETRY_DISABLED=1
RUN PUBLIC_API_BASE_URL="${PUBLIC_API_BASE_URL}" npm run build

FROM nginx:stable-alpine AS runtime
RUN rm -rf /usr/share/nginx/html/*
COPY --from=build /app/dist/ /usr/share/nginx/html/
EXPOSE 80
