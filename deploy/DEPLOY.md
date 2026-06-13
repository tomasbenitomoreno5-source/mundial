# Despliegue en servidor Oracle Cloud (Ubuntu)

Guía para servir la web + auto-update en una VM de Oracle Cloud.
Asume **Ubuntu 22.04**. Para Oracle Linux, cambia `apt` por `dnf` y revisa las
dependencias de Playwright a mano.

> Modelo: **todo-en-uno**. Web (`next start`) + SQLite + scrapers + cron, en la
> misma máquina. Los cambios de **código** se despliegan con `git pull` +
> `deploy.sh`; los **resultados** del Mundial se actualizan solos por cron.

---

## 0. Abrir puertos (¡el paso que todos olvidan en Oracle!)
Hay que abrir 80 y 443 en **DOS sitios**:

**a) Consola de Oracle** — VCN → Security List (o NSG) → Ingress Rules:
añade `0.0.0.0/0` TCP 80 y 443.

**b) Firewall del SO** (en la VM):
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save     # ubuntu
```

## 1. Dependencias del sistema
```bash
sudo apt update
# Node 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs python3-venv python3-pip git
```

## 2. Clonar el repo
```bash
cd ~
git clone <URL_DEL_REPO> mundial
cd mundial
```

## 3. Python + Playwright (scrapers)
```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/playwright install --with-deps chromium
# prueba rápida de que el scraping funciona desde el server (anti-bot):
.venv/bin/python extraer_resultados.py     # debe correr sin error
```

## 4. Build + seed de la web
```bash
cd web
npm ci
npx prisma generate
npx prisma db push --skip-generate
npm run db:seed        # carga los CSV de data/ en SQLite
npm run build
```

## 5. Servicio (systemd) para `next start`
```bash
# edita User/rutas si tu usuario no es 'ubuntu' o el repo no está en ~/mundial
sudo cp deploy/mundial-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mundial-web
sudo systemctl status mundial-web      # debe estar 'active (running)'
```
La web ya responde en `localhost:3000`.

## 6. Reverse proxy + HTTPS (Caddy)
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
# edita deploy/Caddyfile con tu dominio (o el bloque :80 si vas por IP)
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```
Con dominio: apunta un registro A a la IP pública de la VM → Caddy saca el TLS solo.

## 7. Auto-update (cron)
**Opción simple — cada 2h:**
```bash
crontab -e
# añade (ajusta la ruta):
0 */2 * * * /home/ubuntu/mundial/actualizar.sh >> /tmp/mundial_update.log 2>&1
```
**Opción exacta — post-partido (kickoff + 2.5h):**
```bash
chmod +x actualizar.sh
.venv/bin/python deploy/generar_crontab.py | crontab -
```
(El sitio es ISR: tras el re-seed, las páginas recogen los datos solas, sin rebuild.)

---

## Día a día
- **Cambio de código:** en local `git push` → en el server `bash deploy/deploy.sh`.
- **Resultados del Mundial:** automático por el cron. No tocas nada.
- Logs del auto-update: `tail -f /tmp/mundial_update.log`.
- Logs de la web: `journalctl -u mundial-web -f`.

---

## Notificaciones por Telegram (resumen de cada cron)

`run_actualizacion.py` manda **una notificación por ejecución del cron** con el
resumen (qué pasos corrieron, OK/fallo, vía API/HTML, resultados nuevos).

**1. Crear el bot:** en Telegram, habla con **@BotFather** → `/newbot` → te da un
**token** (`123456:ABC...`).

**2. Tu chat_id:** escribe cualquier mensaje a tu bot, luego abre en el navegador
`https://api.telegram.org/bot<TOKEN>/getUpdates` y copia el `chat.id` (o usa
**@userinfobot**).

**3. Configurar las credenciales.** `notificar.py` las lee de variables de
entorno o, si no, del fichero **`telegram.env`** (en la raíz de `mundial/`). Ese
fichero está en `.gitignore` → **NO viaja con `git pull`**, así que hay que
crearlo **una vez en cada máquina** (local y servidor). En el servidor:
```bash
cd /ruta/al/repo/mundial
cat > telegram.env <<'EOF'
MUNDIAL_TG_TOKEN=123456:ABC...
MUNDIAL_TG_CHAT=<tu chat_id>
EOF
```
Al estar gitignorado, los `git pull` posteriores **no lo pisan** (se crea solo
una vez). Sin él (ni env vars), el resumen se imprime en el log y el cron sigue
igual.

> ⚠️ **IP de datacenter (Oracle Cloud):** SofaScore bloquea más agresivamente las
> IPs de datacenter. Si el scraping (resultados) empieza a fallar con 403 en el
> servidor, la notificación te avisará — y la solución es correr el cron desde
> una **IP residencial** (p.ej. tu Mac) en vez del VPS. Verifícalo tras desplegar.
