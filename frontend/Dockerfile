FROM node:20-alpine AS prod

WORKDIR /app

COPY package.json .

#ENV VITE_API_URL=https://htit-monitor.marvin-carstensen.com/api

RUN npm install

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