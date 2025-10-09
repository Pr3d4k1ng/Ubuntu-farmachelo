#!/bin/bash

# Salir si hay un error
set -e

# --- Construir Frontend ---
echo "Construyendo el frontend..."
cd frontend
npm install
npm run build
cd ..

# --- Instalar dependencias del Backend ---
echo "Instalando dependencias del backend..."
cd backend
echo "Activando entorno virtual..."
source farmachelo_env/bin/activate
pip install -r requirements.txt
deactivate
cd ..

echo "
Despliegue completado.

Próximos pasos:
1. Mueve este proyecto a /var/www/farmachelo-ubuntu en tu VM.
2. Mueve farmachelo.conf a /etc/apache2/sites-available/.
3. Habilita el sitio y los módulos de Apache:
   sudo a2ensite farmachelo.conf
   sudo a2enmod proxy
   sudo a2enmod proxy_http
   sudo a2enmod rewrite
   sudo systemctl restart apache2
4. Inicia el backend en segundo plano con uvicorn:
   cd /var/www/farmachelo-ubuntu/backend
   uvicorn server:app --host 0.0.0.0 --port 8000 &
   (Para producción real, considera usar un servicio systemd para uvicorn)
"
