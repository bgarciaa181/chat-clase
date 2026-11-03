# servidor_web.py
# Chat de clase v3: el chat se usa desde el navegador (PC o móvil).
#
# Este programa es a la vez:
#   - un servidor web que entrega la página del chat (web/index.html)
#   - una pequeña "API" que guarda los mensajes y recibe los archivos por trozos
#
# Todo lo que pasa se apunta en datos/registro.log, y los mensajes se guardan
# en datos/historial.json para no perderlos al apagar el servidor.
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

# ===== AJUSTES (cámbialos a tu gusto) =====
PUERTO = 8080
DIAS_GUARDAR = 7   # mensajes, archivos y logs de más de 7 días se borran solos (0 = guardar siempre)
# ==========================================

CARPETA_BASE = os.path.dirname(os.path.abspath(__file__))
CARPETA_WEB = os.path.join(CARPETA_BASE, "web")
CARPETA_ARCHIVOS = os.path.join(CARPETA_BASE, "archivos")
CARPETA_DATOS = os.path.join(CARPETA_BASE, "datos")
ARCHIVO_HISTORIAL = os.path.join(CARPETA_DATOS, "historial.json")

TAMANO_MAXIMO = 2 * 1024 * 1024 * 1024   # archivos de hasta 2 GB
TROZO_MAXIMO = 4 * 1024 * 1024           # cada trozo como mucho 4 MB
SEGUNDOS_DESCONECTADO = 10               # si alguien no pregunta en 10 s, lo damos por ido

# ----- Datos del chat -----
mensajes = []        # lista de mensajes del chat
ultimo_id = 0        # cada mensaje lleva un número para saber cuáles son nuevos
conectados = {}      # nombre -> última vez que preguntó (segundos)
subidas = {}         # id del archivo -> datos de la subida (nombre, tamaño, recibido...)
candado = threading.Lock()       # evita que dos peticiones a la vez estropeen las listas
candado_log = threading.Lock()   # evita que dos hilos escriban a la vez en el log


# ----- Registro (log) -----

def registrar(texto, ip=""):
    """Apunta una línea en el log del día con la fecha y la IP, y la muestra en la terminal.
    Cada día tiene su propio archivo: datos/registro-2026-11-03.log"""
    linea = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {ip:<15} {texto}"
    print(linea)
    archivo_log = os.path.join(CARPETA_DATOS, f"registro-{time.strftime('%Y-%m-%d')}.log")
    with candado_log:
        with open(archivo_log, "a", encoding="utf-8") as f:
            f.write(linea + "\n")


# ----- Limpieza de lo antiguo -----

def limpiar_antiguos():
    """Borra los mensajes, archivos y logs de más de DIAS_GUARDAR días."""
    if DIAS_GUARDAR <= 0:
        return
    limite = time.time() - DIAS_GUARDAR * 24 * 60 * 60   # la fecha límite, en segundos

    with candado:
        # 1. Mensajes viejos (y los archivos que se mandaron en ellos)
        viejos = [m for m in mensajes if m["momento"] < limite]
        for mensaje in viejos:
            mensajes.remove(mensaje)
            if mensaje["tipo"] == "archivo":
                datos = subidas.pop(mensaje["archivo"]["id"], None)
                if datos and os.path.exists(datos["ruta"]):
                    os.remove(datos["ruta"])

        # 2. Archivos sueltos de subidas que se cortaron a medias (de hace más de un día)
        for id_archivo in os.listdir(CARPETA_ARCHIVOS):
            ruta = os.path.join(CARPETA_ARCHIVOS, id_archivo)
            if id_archivo not in subidas and os.path.getmtime(ruta) < time.time() - 24 * 60 * 60:
                os.remove(ruta)

        if viejos:
            guardar_historial()

    # 3. Logs de días antiguos
    logs_borrados = 0
    for nombre in os.listdir(CARPETA_DATOS):
        ruta = os.path.join(CARPETA_DATOS, nombre)
        if nombre.startswith("registro-") and os.path.getmtime(ruta) < limite:
            os.remove(ruta)
            logs_borrados += 1

    if viejos or logs_borrados:
        registrar(f"LIMPIEZA borrados {len(viejos)} mensajes antiguos y {logs_borrados} logs antiguos")


def limpiar_cada_hora():
    """Hilo que se queda funcionando y hace limpieza una vez por hora."""
    while True:
        try:
            limpiar_antiguos()
        except Exception as error:
            registrar(f"[!] Error al limpiar: {error}")
        time.sleep(60 * 60)


# ----- Historial (para no perder nada al apagar) -----

def guardar_historial():
    """Guarda los mensajes y los archivos subidos en historial.json.
    Hay que llamarla con el candado puesto."""
    archivos_terminados = {}
    for id_archivo, datos in subidas.items():
        if datos["terminado"]:
            archivos_terminados[id_archivo] = {"de": datos["de"], "nombre": datos["nombre"],
                                               "tamano": datos["tamano"]}
    contenido = {"ultimo_id": ultimo_id, "mensajes": mensajes, "archivos": archivos_terminados}

    # Escribimos primero en un archivo temporal y luego lo cambiamos de nombre:
    # así, si se va la luz a mitad, no se queda el historial roto
    temporal = ARCHIVO_HISTORIAL + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(contenido, f, ensure_ascii=False)
    os.replace(temporal, ARCHIVO_HISTORIAL)


def cargar_historial():
    """Al arrancar, recupera los mensajes y archivos que había antes de apagar."""
    global ultimo_id
    if not os.path.exists(ARCHIVO_HISTORIAL):
        return
    try:
        with open(ARCHIVO_HISTORIAL, encoding="utf-8") as f:
            contenido = json.load(f)
    except:
        registrar("[!] No se ha podido leer el historial, empezamos de cero")
        return

    for mensaje in contenido.get("mensajes", []):
        mensaje.setdefault("momento", time.time())   # por si viene de una versión anterior
        mensajes.append(mensaje)
    ultimo_id = contenido.get("ultimo_id", 0)
    for id_archivo, datos in contenido.get("archivos", {}).items():
        ruta = os.path.join(CARPETA_ARCHIVOS, id_archivo)
        if os.path.exists(ruta):   # solo si el archivo sigue en la carpeta
            subidas[id_archivo] = {**datos, "recibido": datos["tamano"], "ruta": ruta, "terminado": True}
    registrar(f"Historial cargado: {len(mensajes)} mensajes y {len(subidas)} archivos")


# ----- Funciones de ayuda -----

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
    """Añade un mensaje con su número y su hora, y guarda el historial.
    Hay que llamarla con el candado puesto."""
    global ultimo_id
    ultimo_id += 1
    mensaje["id"] = ultimo_id
    mensaje["hora"] = time.strftime("%H:%M")
    mensaje["momento"] = time.time()   # fecha exacta en segundos, para saber cuándo borrarlo
    mensajes.append(mensaje)
    guardar_historial()


def revisar_conectados(nombre, ip):
    """Apunta que "nombre" sigue conectado y avisa de quién entra o sale."""
    ahora = time.time()
    if nombre:
        if nombre not in conectados:
            anadir_mensaje({"tipo": "aviso", "texto": f"{nombre} se ha unido al chat"})
            registrar(f"ENTRA    {nombre}", ip)
        conectados[nombre] = ahora

    # Los que llevan un rato sin preguntar se han ido (han cerrado la pestaña)
    for persona in list(conectados):
        if ahora - conectados[persona] > SEGUNDOS_DESCONECTADO:
            del conectados[persona]
            anadir_mensaje({"tipo": "aviso", "texto": f"{persona} ha salido del chat"})
            registrar(f"SALE     {persona}")


def limpiar_nombre(texto, maximo):
    return str(texto or "").strip()[:maximo]


def tamano_bonito(bytes_):
    if bytes_ < 1024 ** 2:
        return f"{bytes_ / 1024:.0f} KB"
    return f"{bytes_ / 1024 ** 2:.1f} MB"


class Manejador(BaseHTTPRequestHandler):
    """Atiende cada petición del navegador. Cada petición va en su propio hilo."""

    def ip(self):
        return self.client_address[0]

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
        pass   # no llenamos la terminal con cada petición (ya tenemos nuestro propio log)

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
                revisar_conectados(nombre, self.ip())
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
        if not ver_en_pagina:
            registrar(f"DESCARGA {datos['nombre']}", self.ip())

        self.send_response(200)
        self.send_header("Content-Type", tipo if ver_en_pagina else "application/octet-stream")
        self.send_header("Content-Length", str(datos["tamano"]))
        self.send_header("X-Content-Type-Options", "nosniff")
        if not ver_en_pagina:
            # Esto hace que el navegador lo descargue con su nombre original
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(datos["nombre"]))
        self.end_headers()

        try:
            with open(datos["ruta"], "rb") as f:
                shutil.copyfileobj(f, self.wfile, 64 * 1024)   # lo mandamos de 64 KB en 64 KB
        except (BrokenPipeError, ConnectionResetError):
            pass   # el navegador ha cancelado la descarga

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
        registrar(f"MENSAJE  {nombre}: {texto}", self.ip())
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
        ruta = os.path.join(CARPETA_ARCHIVOS, id_archivo)
        open(ruta, "wb").close()          # creamos el archivo vacío

        with candado:
            subidas[id_archivo] = {"de": nombre, "nombre": nombre_archivo, "tamano": tamano,
                                   "recibido": 0, "ruta": ruta, "terminado": False}
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
        registrar(f"ARCHIVO  {datos['de']} sube {datos['nombre']} ({tamano_bonito(datos['tamano'])})", self.ip())
        self.responder_json({"ok": True})


# ----- Programa principal -----
os.makedirs(CARPETA_ARCHIVOS, exist_ok=True)
os.makedirs(CARPETA_DATOS, exist_ok=True)

print("===== CHAT DE CLASE (v3 web) =====")
cargar_historial()
servidor = ThreadingHTTPServer(("0.0.0.0", PUERTO), Manejador)
registrar("Servidor encendido")

print(f"Abre en el navegador:  http://localhost:{PUERTO}")
print(f"Tus compañeros:        http://{obtener_mi_ip()}:{PUERTO}")
print("(Con Tailscale, usad la IP 100.x.x.x que sale con: tailscale ip -4)")
print(f"El registro se guarda en: datos/registro-{time.strftime('%Y-%m-%d')}.log")
if DIAS_GUARDAR > 0:
    print(f"Se guardan los últimos {DIAS_GUARDAR} días (lo anterior se borra solo)")
print("Pulsa Ctrl+C para apagarlo.\n")

# Hilo que borra lo antiguo una vez por hora
threading.Thread(target=limpiar_cada_hora, daemon=True).start()

try:
    servidor.serve_forever()
except KeyboardInterrupt:
    registrar("Servidor apagado")
    servidor.server_close()
