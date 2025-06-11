#!/bin/bash
# coBoarding deployment script

echo "🚀 Deploying coBoarding platform..."

# Build and start services
echo "📦 Building Docker containers..."
docker-compose build --no-cache

echo "🔄 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Check service health
echo "🔍 Checking service health..."
docker-compose ps

# Initialize database
echo "🗄️  Initializing database..."
docker-compose exec postgres psql -U coboarding -d coboarding -f /docker-entrypoint-initdb.d/init.sql

# Download Ollama models
echo "🤖 Downloading AI models..."
docker-compose exec ollama ollama pull llava:7b
docker-compose exec ollama ollama pull mistral:7b-instruct
docker-compose exec ollama ollama pull nomic-embed-text

echo "✅ Deployment completed!"
echo ""
echo "🌐 Services available at:"
echo "  - Main App: http://localhost:8502"
echo "  - API: http://localhost:8000"
echo "  - n8n: http://localhost:5678 (admin/admin123)"
echo "  - Database: localhost:5432"
echo "  - Redis: localhost:6379"
echo ""
echo "📚 Next steps:"
echo "  1. Configure email settings in .env file"
echo "  2. Set up notification webhooks for companies"
echo "  3. Upload your first CV to test the system"
echo "  4. Check logs: docker-compose logs -f"
