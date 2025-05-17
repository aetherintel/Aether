FROM node:20-alpine AS prod

WORKDIR /app

COPY package.json .

RUN npm install

RUN npm i -g serve

COPY . .

RUN npm run build


FROM nginx:stable-alpine

WORKDIR /usr/share/nginx/html

RUN rm -rf ./*

RUN mkdir -p /etc/nginx/ssl

COPY --from=prod /app/dist .

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]