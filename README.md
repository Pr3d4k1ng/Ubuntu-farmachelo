# Farmachelo Ubuntu Deployment

Este proyecto está preparado para correr en un servidor Apache en Ubuntu, utilizando XAMPP dentro de una máquina virtual. A continuación, se describen los pasos y la estructura organizada para su correcto funcionamiento.

## Estructura del Proyecto

- **backend/**: Contiene todo el código Python del backend (FastAPI, por ejemplo) y la configuración del entorno virtual.
  - Se utiliza un entorno virtual ubicado en `backend/farmachelo_env`. Este entorno está configurado con Linux, por lo que se debe activar usando `source farmachelo_env/bin/activate`.
  - El archivo `server.py` debería exponer la aplicación (por ejemplo, con la variable `app`), para ser ejecutada con `uvicorn`.
  
- **frontend/**: Contiene el código fuente de la aplicación (React u otro framework). Se asume que se usa un proceso de *build* que genera la carpeta `build` (o similar), la cual será utilizada como *DocumentRoot* en Apache.
  - Se ha detectado una estructura duplicada de carpetas `src`. Se recomienda conservar la carpeta `frontend/src` y eliminar la carpeta `frontend/public/src` para evitar confusiones.

- **farmachelo.conf**: Archivo de configuración para Apache (virtual host). Asegúrate de que apunta a la ruta correcta del directorio construido del frontend (por ejemplo, `DocumentRoot /path/to/farmachelo-ubuntu/frontend/build`) y que se configuran apropiadamente los proxy reversos para el backend.

- **deploy.sh**: Script de despliegue que realiza las siguientes acciones:
  1. Construir el frontend (instala dependencias y ejecuta el build).
  2. Instalar las dependencias del backend utilizando el entorno virtual adecuado (en Linux se usa `farmachelo_env/bin/activate`).
  3. Imprime instrucciones para completar el despliegue, tales como mover el proyecto a `/var/www/farmachelo-ubuntu` y configurar Apache.

## Pasos para Desplegar en Ubuntu con XAMPP

1. **Copiar el Proyecto a htdocs**
   - Coloca el proyecto en el directorio `htdocs` de XAMPP, o asegúrate de que Apache esté configurado para apuntar al directorio del proyecto.

2. **Construir el Frontend**
   - Navega a la carpeta `frontend` y ejecuta:
     ```bash
     npm install
     npm run build
     ```
   - Esto generará la carpeta `build` con los archivos estáticos a servir.

3. **Instalar Dependencias del Backend**
   - Navega a la carpeta `backend` y activa el entorno virtual:
     ```bash
     cd backend
     source farmachelo_env/bin/activate
     pip install -r requirements.txt
     deactivate
     ```

4. **Configuración de Apache**
   - Copia `farmachelo.conf` a `/etc/apache2/sites-available/`.
   - Asegúrate de que el archivo de configuración tenga los siguientes elementos:
     - `DocumentRoot` apuntando a la carpeta generada del frontend (por ejemplo, `/path/to/farmachelo-ubuntu/frontend/build`).
     - Configuración para proxy de las rutas que manejen el backend, en caso de requerirlo.
   - Habilita el sitio y los módulos necesarios:
     ```bash
     sudo a2ensite farmachelo.conf
     sudo a2enmod proxy
     sudo a2enmod proxy_http
     sudo a2enmod rewrite
     sudo systemctl restart apache2
     ```

5. **Iniciar el Backend**
   - Desde la carpeta `backend`, inicia el backend con uvicorn:
     ```bash
     cd backend
     uvicorn server:app --host 0.0.0.0 --port 8000 &
     ```
   - Para producción, se recomienda configurar un servicio systemd para gestionar uvicorn.

6. **Revisión de Carpetas Duplicadas en el Frontend**
   - Se recomienda eliminar la carpeta `frontend/public/src` y mantener únicamente `frontend/src` para evitar duplicidades.

## Notas Adicionales

- Revisa todas las rutas y permisos de archivos al mover o copiar el proyecto en la máquina virtual.
- Asegúrate de tener instalados todos los módulos requeridos en Ubuntu (por ejemplo, Node.js, npm, Python 3.x, etc.).
- Verifica la configuración de variables de entorno en los archivos `.env` tanto para el backend como para el frontend.

Con estos pasos y ajustes, el proyecto debería estar correctamente organizado y listo para funcionar en un entorno Ubuntu con XAMPP como servidor Apache.
