# Build stage
FROM oven/bun:latest as builder

WORKDIR /app

COPY package.json ./
RUN bun install

COPY . .
RUN bun run build

# Serve stage
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
