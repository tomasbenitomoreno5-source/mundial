# Imagen única: Node (web) + Python + Playwright/Chromium (scrapers).
FROM node:20-bookworm

WORKDIR /app

# Python para los scrapers (bookworm trae 3.11, sin el problema del 3.8 de Ubuntu 20.04)
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv python3-pip \
 && rm -rf /var/lib/apt/lists/*

# Copia el repo (data/ incluido para el seed). .dockerignore excluye lo pesado.
COPY . .

# Deps Python + Chromium con sus librerías de sistema
RUN python3 -m venv .venv \
 && .venv/bin/pip install --no-cache-dir -e . playwright \
 && .venv/bin/playwright install --with-deps chromium

# Build de la web. La DB vive en /data (volumen). Se siembra en build para que
# next build pueda prerenderizar (generateStaticParams consulta la DB).
ENV DATABASE_URL="file:/data/dev.db"
WORKDIR /app/web
RUN mkdir -p /data \
 && npm ci \
 && npx prisma generate \
 && npx prisma db push --skip-generate \
 && npm run db:seed \
 && npm run build

EXPOSE 3000
COPY deploy/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
