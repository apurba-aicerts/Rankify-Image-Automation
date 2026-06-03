# Build static assets, then serve with nginx (proxies /api to backend service).
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_USE_PROXY=true
ARG VITE_API_KEY=
ENV VITE_USE_PROXY=$VITE_USE_PROXY
ENV VITE_API_KEY=$VITE_API_KEY

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
