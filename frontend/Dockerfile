# Image de l'interface, construite depuis la racine du dépôt : l'application (frontend/) et sa
# documentation (site/), servie sous /docs/.
FROM node:22-alpine AS interface
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM node:22-alpine AS documentation
WORKDIR /site
COPY site/package.json site/package-lock.json ./
RUN npm ci
COPY site/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=interface /app/dist /usr/share/nginx/html
COPY --from=documentation /site/dist /usr/share/nginx/html/docs
COPY --from=documentation /site/en-tetes-docs.conf /etc/nginx/en-tetes-docs.conf
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
