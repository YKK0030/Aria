FROM node:22-alpine

WORKDIR /app

COPY package.json tsconfig.json ./
RUN apk add --no-cache --virtual .npm-build-deps git \
    && npm install \
    && apk del .npm-build-deps

COPY src ./src

EXPOSE 3001

CMD ["npm", "run", "dev"]

