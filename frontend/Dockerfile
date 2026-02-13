FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend ./
ARG VITE_PUBLIC_UPLOAD_URL=/api/upload
ENV VITE_PUBLIC_UPLOAD_URL=$VITE_PUBLIC_UPLOAD_URL
RUN npm run build

FROM nginx:1.25-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
