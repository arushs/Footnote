# =============================================================================
# Stage 1: Base with Node.js
# =============================================================================
FROM node:20-alpine AS base

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# =============================================================================
# Stage 2: Development image
# =============================================================================
FROM base AS development

# Install all dependencies
RUN npm ci

# Copy source
COPY . .

EXPOSE 3000

# Vite dev server with hot reload
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# =============================================================================
# Stage 3: Build stage for production
# =============================================================================
FROM base AS builder

# Install dependencies
RUN npm ci

# Copy source
COPY . .

# Build arguments for environment variables
ARG VITE_API_URL
ARG VITE_GOOGLE_API_KEY
ARG VITE_GOOGLE_CLIENT_ID

ENV VITE_API_URL=$VITE_API_URL \
    VITE_GOOGLE_API_KEY=$VITE_GOOGLE_API_KEY \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID

RUN npm run build

# =============================================================================
# Stage 4: Production with nginx
# =============================================================================
FROM nginx:alpine AS production

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
