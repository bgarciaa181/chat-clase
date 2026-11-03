# cliente.py
# Cliente de terminal del chat de clase.
# Comandos: /archivo ruta  ->  envía un archivo
#           /usuarios      ->  muestra quién está conectado
#           /salir         ->  sale del chat

import socket
import threading
import json
import base64
import os

PUERTO = 5555                        # tiene que ser el mismo que en el servidor
TAMANO_MAXIMO = 5 * 1024 * 1024      # archivos de 5 MB como máximo
CARPETA_RECIBIDOS = "recibidos"


def enviar_json(mensaje):
    """Convierte el mensaje (un diccionario) a JSON y lo manda al servidor."""
    linea = json.dumps(mensaje) + "\n"
    cliente.sendall(linea.encode("utf-8"))


def guardar_archivo(nombre_archivo, datos_base64):
    """Guarda un archivo recibido en la carpeta "recibidos" y devuelve la ruta."""
    os.makedirs(CARPETA_RECIBIDOS, exist_ok=True)
    nombre_archivo = os.path.basename(nombre_archivo) or "archivo"
    ruta = os.path.join(CARPETA_RECIBIDOS, nombre_archivo)

    # Si ya existe, le añadimos un número: foto(1).png
    base, extension = os.path.splitext(nombre_archivo)
    numero = 1
    while os.path.exists(ruta):
        ruta = os.path.join(CARPETA_RECIBIDOS, f"{base}({numero}){extension}")
        numero += 1

    with open(ruta, "wb") as f:
        f.write(base64.b64decode(datos_base64))
    return ruta


def recibir_mensajes():
    """Se queda escuchando y muestra todo lo que manda el servidor."""
    buffer = b""
    while True:
        try:
            trozo = cliente.recv(65536)
        except:
            break
        if not trozo:
            print("*** Se ha cerrado el servidor ***")
            break

        buffer += trozo
        while b"\n" in buffer:
            linea, buffer = buffer.split(b"\n", 1)
            try:
                mensaje = json.loads(linea.decode("utf-8"))
            except:
                continue

            tipo = mensaje.get("tipo")
            if tipo == "texto":
                print(f"{mensaje['de']}: {mensaje['texto']}")
            elif tipo == "aviso":
                print(f"*** {mensaje['texto']} ***")
            elif tipo == "archivo":
                try:
                    ruta = guardar_archivo(mensaje["nombre"], mensaje["datos"])
                    print(f"📎 {mensaje['de']} ha enviado {mensaje['nombre']} (guardado en {ruta})")
                except:
                    print(f"*** No se ha podido guardar el archivo de {mensaje['de']} ***")


def enviar_archivo(ruta):
    """Lee un archivo y lo envía al servidor."""
    if not os.path.isfile(ruta):
        print("*** No existe ese archivo ***")
        return
    if os.path.getsize(ruta) > TAMANO_MAXIMO:
        print("*** El archivo no puede pasar de 5 MB ***")
        return

    with open(ruta, "rb") as f:
        datos = base64.b64encode(f.read()).decode("utf-8")   # pasamos el archivo a texto

    enviar_json({"tipo": "archivo", "nombre": os.path.basename(ruta), "datos": datos})
    print(f"📎 Has enviado {os.path.basename(ruta)}")


# ----- Programa principal -----

print("===== CHAT DE CLASE (v2) =====")
ip_servidor = input("IP del servidor: ")
nombre = input("Tu nombre: ")

cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    cliente.connect((ip_servidor, PUERTO))
except:
    print("No se ha podido conectar. Revisa la IP y que el servidor esté encendido.")
    exit()

enviar_json({"tipo": "nombre", "nombre": nombre})   # lo primero que mandamos es el nombre
print("Comandos: /archivo ruta  |  /usuarios  |  /salir")

# Escuchamos en un hilo aparte para poder escribir y recibir a la vez
hilo = threading.Thread(target=recibir_mensajes, daemon=True)
hilo.start()

# Bucle para escribir mensajes
while True:
    try:
        texto = input()
    except EOFError:
        break

    try:
        if texto == "/salir":
            print("Saliendo del chat...")
            break
        elif texto == "/usuarios":
            enviar_json({"tipo": "usuarios"})
        elif texto.startswith("/archivo "):
            enviar_archivo(texto[len("/archivo "):].strip())
        elif texto.strip() != "":   # no mandamos mensajes vacíos
            enviar_json({"tipo": "texto", "texto": texto})
    except:
        print("Se ha perdido la conexión con el servidor.")
        break

cliente.close()