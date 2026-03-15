ARG NODE_IMAGE=docker.m.daocloud.io/library/node:20-alpine
FROM ${NODE_IMAGE} AS build

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend ./
ARG VITE_PUBLIC_UPLOAD_URL=/api/upload
ENV VITE_PUBLIC_UPLOAD_URL=$VITE_PUBLIC_UPLOAD_URL
RUN npm run build

ARG NGINX_IMAGE=docker.m.daocloud.io/library/nginx:1.25-alpine
FROM ${NGINX_IMAGE}

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
