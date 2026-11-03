# servidor_web.py
# Chat de clase v3: el chat se usa desde el navegador (PC o móvil).
#
# Este programa es a la vez:
#   - un servidor web que entrega la página del chat (web/index.html)
#   - una pequeña "API" que guarda los mensajes y recibe los archivos por trozos
#
# Solo usa librerías que vienen con Python, así que no hay que instalar nada.

import json
import os
import socket
import threading
import time
import uuid
import mimetypes
import shutil
from urllib.parse import urlparse, parse_qs, quote
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PUERTO = 8080
CARPETA_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
CARPETA_ARCHIVOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archivos")
TAMANO_MAXIMO = 2 * 1024 * 1024 * 1024   # archivos de hasta 2 GB
TROZO_MAXIMO = 4 * 1024 * 1024           # cada trozo como mucho 4 MB
SEGUNDOS_DESCONECTADO = 10               # si alguien no pregunta en 10 s, lo damos por ido

# ----- Datos del chat (se guardan en memoria) -----
mensajes = []        # lista de mensajes del chat
ultimo_id = 0        # cada mensaje lleva un número para saber cuáles son nuevos
conectados = {}      # nombre -> última vez que preguntó (segundos)
subidas = {}         # id del archivo -> datos de la subida (nombre, tamaño, recibido...)
candado = threading.Lock()   # evita que dos peticiones a la vez estropeen las listas


def obtener_mi_ip():
    """Devuelve la IP local del equipo para que los compañeros sepan a dónde conectarse."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def anadir_mensaje(mensaje):
    """Añade un mensaje a la lista con su número y su hora. Hay que llamarla con el candado puesto."""
    global ultimo_id
    ultimo_id += 1
    mensaje["id"] = ultimo_id
    mensaje["hora"] = time.strftime("%H:%M")
    mensajes.append(mensaje)


def revisar_conectados(nombre):
    """Apunta que "nombre" sigue conectado y avisa de quién entra o sale."""
    ahora = time.time()
    if nombre:
        if nombre not in conectados:
            anadir_mensaje({"tipo": "aviso", "texto": f"{nombre} se ha unido al chat"})
        conectados[nombre] = ahora

    # Los que llevan un rato sin preguntar se han ido (han cerrado la pestaña)
    for persona in list(conectados):
        if ahora - conectados[persona] > SEGUNDOS_DESCONECTADO:
            del conectados[persona]
            anadir_mensaje({"tipo": "aviso", "texto": f"{persona} ha salido del chat"})


def limpiar_nombre(texto, maximo):
    return str(texto or "").strip()[:maximo]


class Manejador(BaseHTTPRequestHandler):
    """Atiende cada petición del navegador. Cada petición va en su propio hilo."""

    # ----- Funciones de ayuda para responder -----

    def responder_json(self, datos, codigo=200):
        cuerpo = json.dumps(datos).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def error(self, texto, codigo=400):
        self.responder_json({"error": texto}, codigo)

    def leer_json(self):
        largo = int(self.headers.get("Content-Length", 0))
        if largo > 100000:
            return None
        try:
            return json.loads(self.rfile.read(largo).decode("utf-8"))
        except:
            return None

    def log_message(self, formato, *args):
        pass   # no llenamos la terminal con cada petición

    # ----- Peticiones GET (pedir cosas) -----

    def do_GET(self):
        url = urlparse(self.path)
        parametros = parse_qs(url.query)

        if url.path == "/":
            self.enviar_pagina()

        elif url.path == "/mensajes":
            # El navegador pregunta cada segundo: "¿hay mensajes nuevos desde el número X?"
            desde = int(parametros.get("desde", ["0"])[0])
            nombre = limpiar_nombre(parametros.get("nombre", [""])[0], 20)
            with candado:
                revisar_conectados(nombre)
                nuevos = [m for m in mensajes if m["id"] > desde]
                personas = sorted(conectados)
            self.responder_json({"mensajes": nuevos, "conectados": personas})

        elif url.path.startswith("/descargar/") or url.path.startswith("/ver/"):
            self.enviar_archivo(url.path)

        else:
            self.error("No existe", 404)

    def enviar_pagina(self):
        with open(os.path.join(CARPETA_WEB, "index.html"), "rb") as f:
            cuerpo = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def enviar_archivo(self, ruta_url):
        """Envía un archivo al navegador poco a poco (sirve aunque pese mucho)."""
        partes = ruta_url.split("/")          # ["", "descargar", "<id>"]
        id_archivo = partes[2] if len(partes) > 2 else ""
        with candado:
            datos = subidas.get(id_archivo)
        if not datos or not datos["terminado"]:
            self.error("Archivo no encontrado", 404)
            return

        tipo = mimetypes.guess_type(datos["nombre"])[0] or "application/octet-stream"
        ver_en_pagina = partes[1] == "ver" and tipo.startswith("image/") and tipo != "image/svg+xml"

        self.send_response(200)
        self.send_header("Content-Type", tipo if ver_en_pagina else "application/octet-stream")
        self.send_header("Content-Length", str(datos["tamano"]))
        self.send_header("X-Content-Type-Options", "nosniff")
        if not ver_en_pagina:
            # Esto hace que el navegador lo descargue con su nombre original
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(datos["nombre"]))
        self.end_headers()

        with open(datos["ruta"], "rb") as f:
            shutil.copyfileobj(f, self.wfile, 64 * 1024)   # lo mandamos de 64 KB en 64 KB

    # ----- Peticiones POST (mandar cosas) -----

    def do_POST(self):
        url = urlparse(self.path)
        parametros = parse_qs(url.query)

        if url.path == "/enviar":
            self.recibir_texto()
        elif url.path == "/subir/inicio":
            self.empezar_subida()
        elif url.path == "/subir/trozo":
            self.recibir_trozo(parametros.get("id", [""])[0])
        elif url.path == "/subir/fin":
            self.terminar_subida(parametros.get("id", [""])[0])
        else:
            self.error("No existe", 404)

    def recibir_texto(self):
        datos = self.leer_json()
        if not datos:
            return self.error("Datos incorrectos")
        nombre = limpiar_nombre(datos.get("nombre"), 20)
        texto = limpiar_nombre(datos.get("texto"), 2000)
        if not nombre or not texto:
            return self.error("Falta el nombre o el texto")

        with candado:
            anadir_mensaje({"tipo": "texto", "de": nombre, "texto": texto})
        print(f"{nombre}: {texto}")
        self.responder_json({"ok": True})

    def empezar_subida(self):
        """Paso 1: el navegador avisa de que va a mandar un archivo y de cuánto pesa."""
        datos = self.leer_json()
        if not datos:
            return self.error("Datos incorrectos")
        nombre = limpiar_nombre(datos.get("nombre"), 20)
        nombre_archivo = os.path.basename(limpiar_nombre(datos.get("archivo"), 150)) or "archivo"
        tamano = int(datos.get("tamano", 0))
        if not nombre:
            return self.error("Falta el nombre")
        if tamano > TAMANO_MAXIMO:
            return self.error("El archivo es demasiado grande (máximo 2 GB)")

        id_archivo = uuid.uuid4().hex     # un identificador único para no mezclar archivos
        os.makedirs(CARPETA_ARCHIVOS, exist_ok=True)
        ruta = os.path.join(CARPETA_ARCHIVOS, id_archivo)
        open(ruta, "wb").close()          # creamos el archivo vacío

        with candado:
            subidas[id_archivo] = {"de": nombre, "nombre": nombre_archivo, "tamano": tamano,
                                   "recibido": 0, "ruta": ruta, "terminado": False}
        print(f"[archivo] {nombre} empieza a subir {nombre_archivo} ({tamano} bytes)")
        self.responder_json({"id": id_archivo})

    def recibir_trozo(self, id_archivo):
        """Paso 2: llega un trozo del archivo y lo añadimos al final."""
        with candado:
            datos = subidas.get(id_archivo)
        if not datos or datos["terminado"]:
            return self.error("Subida no encontrada", 404)

        largo = int(self.headers.get("Content-Length", 0))
        if largo > TROZO_MAXIMO or datos["recibido"] + largo > datos["tamano"]:
            return self.error("Trozo demasiado grande")

        with open(datos["ruta"], "ab") as f:   # "ab" = añadir al final, en binario
            pendiente = largo
            while pendiente > 0:
                bloque = self.rfile.read(min(65536, pendiente))
                if not bloque:
                    break
                f.write(bloque)
                pendiente -= len(bloque)

        with candado:
            datos["recibido"] += largo - pendiente
        self.responder_json({"recibido": datos["recibido"]})

    def terminar_subida(self, id_archivo):
        """Paso 3: el navegador avisa de que ha terminado. Lo anunciamos en el chat."""
        with candado:
            datos = subidas.get(id_archivo)
            if not datos or datos["recibido"] != datos["tamano"]:
                return self.error("La subida no está completa")
            datos["terminado"] = True
            anadir_mensaje({"tipo": "archivo", "de": datos["de"], "archivo": {
                "id": id_archivo, "nombre": datos["nombre"], "tamano": datos["tamano"]}})
        print(f"[archivo] {datos['de']} ha subido {datos['nombre']}")
        self.responder_json({"ok": True})


# ----- Programa principal -----
servidor = ThreadingHTTPServer(("0.0.0.0", PUERTO), Manejador)

print("===== CHAT DE CLASE (v3 web) =====")
print(f"Abre en el navegador:  http://localhost:{PUERTO}")
print(f"Tus compañeros:        http://{obtener_mi_ip()}:{PUERTO}")
print("(Con Tailscale, usad la IP 100.x.x.x que sale con: tailscale ip -4)")
print("Pulsa Ctrl+C para apagarlo.\n")

try:
    servidor.serve_forever()
except KeyboardInterrupt:
    print("\nApagando el servidor...")
    servidor.server_close()
