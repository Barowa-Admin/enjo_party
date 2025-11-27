#!/bin/bash

# Konfiguration - Anpassbar
NODE_VERSION="v18.18.2"
YARN_VERSION="1.22.19"

echo "🚀 Starte Dev-Environment..."
echo ""

# 1. Starte Container
echo "📦 Starte Docker Container..."
docker-compose up -d

# Warte bis Container läuft
sleep 3

# Finde Container-Namen
CONTAINER_NAME=$(docker-compose ps -q frappe)

if [ -z "$CONTAINER_NAME" ]; then
    echo "❌ Container nicht gefunden!"
    exit 1
fi

echo "✅ Container gestartet: $CONTAINER_NAME"
echo ""

# 2. Setup Node.js Version
echo "📦 Installiere Node.js $NODE_VERSION..."
docker exec $CONTAINER_NAME bash -c "source ~/.nvm/nvm.sh && nvm install $NODE_VERSION 2>/dev/null || nvm use $NODE_VERSION"
docker exec $CONTAINER_NAME bash -c "source ~/.nvm/nvm.sh && nvm use $NODE_VERSION && nvm alias default $NODE_VERSION"

# 3. Setup Yarn Version
echo "📦 Installiere Yarn $YARN_VERSION..."
docker exec $CONTAINER_NAME bash -c "source ~/.nvm/nvm.sh && nvm use $NODE_VERSION && npm install -g yarn@$YARN_VERSION"

# 4. Aktualisiere Procfile mit korrekter Node-Version
echo "📝 Aktualisiere Procfile..."
docker exec $CONTAINER_NAME bash -c "cd /workspace/frappe-bench && \
    if grep -q 'v18.18.2' Procfile 2>/dev/null || grep -q 'v20' Procfile 2>/dev/null; then \
        sed -i 's|/home/frappe/.nvm/versions/node/v[0-9.]*/bin/node|/home/frappe/.nvm/versions/node/$NODE_VERSION/bin/node|g' Procfile; \
        echo '✅ Procfile aktualisiert'; \
    else \
        echo '⚠️  Procfile nicht gefunden oder bereits korrekt'; \
    fi"

# 5. Prüfe ob alles korrekt ist
echo ""
echo "🔍 Prüfe Installation..."
NODE_PATH=$(docker exec $CONTAINER_NAME bash -c "source ~/.nvm/nvm.sh && nvm use $NODE_VERSION >/dev/null 2>&1 && which node")
NODE_VER=$(docker exec $CONTAINER_NAME bash -c "source ~/.nvm/nvm.sh && nvm use $NODE_VERSION >/dev/null 2>&1 && node --version")
YARN_VER=$(docker exec $CONTAINER_NAME bash -c "source ~/.nvm/nvm.sh && nvm use $NODE_VERSION >/dev/null 2>&1 && yarn --version")

echo "✅ Node: $NODE_VER ($NODE_PATH)"
echo "✅ Yarn: $YARN_VER"
echo ""

# 6. Öffne Terminal im Container
echo "🎉 Setup abgeschlossen!"
echo ""
echo "📋 Nächste Schritte:"
echo "   1. cd /workspace/frappe-bench"
echo "   2. bench start"
echo ""
echo "🌐 Nach dem Start erreichbar unter: http://development.localhost:8000"
echo ""

# Öffne interaktives Terminal
docker exec -it $CONTAINER_NAME bash -c "cd /workspace/frappe-bench && source ~/.nvm/nvm.sh && nvm use $NODE_VERSION && exec bash"
