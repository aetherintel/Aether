FROM node:20-alpine AS prod

WORKDIR /app

COPY package.json .

ARG VITE_API_URL
ARG VITE_ESRI_API_KEY

ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_ESRI_API_KEY=${VITE_ESRI_API_KEY}

RUN npm install --legacy-peer-deps

RUN npm i -g serve

COPY . .

RUN npm run build


FROM nginx:stable-alpine

WORKDIR /usr/share/nginx/html

RUN rm -rf ./*

RUN mkdir -p /etc/nginx/ssl

COPY --from=prod /app/dist .

COPY nginx-prod.conf /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]