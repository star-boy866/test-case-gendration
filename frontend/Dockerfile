# Stage 1: Build
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies deterministically
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .
# Setting environment variables during build for safe static embedding
# (In production, the backend API URL might be dynamic via relative paths or injected config, 
# but we assume the standard Vite VITE_API_URL usage here)
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from builder stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx configuration (if needed to handle SPA routing and security headers)
# For this phase, we dynamically inject security headers into the default conf.
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
        add_header X-Content-Type-Options "nosniff" always; \
        add_header X-Frame-Options "DENY" always; \
        add_header Content-Security-Policy "default-src '\''self'\''; script-src '\''self'\''; style-src '\''self'\'' '\''unsafe-inline'\''; connect-src '\''self'\'' http://localhost:8000; img-src '\''self'\'' data:;" always; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
