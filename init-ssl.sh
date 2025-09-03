#!/bin/bash
set -e

DOMAIN=${1:-xn--ther-uoa.tech}
EMAIL=${2:-your-email@example.com}

echo "Initializing SSL certificates for domain: $DOMAIN"

# Determine Docker Compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "Neither docker-compose nor docker compose found!"
    exit 1
fi

echo "Using Docker Compose command: $COMPOSE_CMD"

# Step 1: Start with HTTP-only configuration
echo "Step 1: Starting with HTTP-only configuration..."
cp docker/nginx/default-http.conf docker/nginx/default.conf

# Start services
$COMPOSE_CMD -f docker-compose.prod.yml up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 30

# Step 2: Generate SSL certificates
echo "Step 2: Generating SSL certificates..."
$COMPOSE_CMD -f docker-compose.prod.yml exec certbot \
    certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d $DOMAIN

if [ $? -eq 0 ]; then
    echo "SSL certificates generated successfully!"
    
    # Step 3: Switch to HTTPS configuration
    echo "Step 3: Switching to HTTPS configuration..."
    cp docker/nginx/default-https.conf docker/nginx/default.conf
    
    # Restart frontend to load new configuration
    $COMPOSE_CMD -f docker-compose.prod.yml restart frontend
    
    echo "SSL setup completed successfully!"
    echo "Your site should now be available at: https://$DOMAIN"
else
    echo "SSL certificate generation failed!"
    exit 1
fi