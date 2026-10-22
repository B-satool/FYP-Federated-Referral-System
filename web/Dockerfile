FROM node:22-alpine AS build
WORKDIR /app
ARG VITE_OIDC_AUTHORITY=http://localhost:8080/realms/referral
ENV VITE_OIDC_AUTHORITY=$VITE_OIDC_AUTHORITY
# Shown on the privacy notice, terms and accessibility pages. Optional: set the name and contact of the institution that operates this deployment.
ARG VITE_OPERATOR_NAME=""
ARG VITE_CONTACT_EMAIL=""
ENV VITE_OPERATOR_NAME=$VITE_OPERATOR_NAME
ENV VITE_CONTACT_EMAIL=$VITE_CONTACT_EMAIL
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
