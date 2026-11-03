# servidor.py
# Servidor del chat de clase.
# Recibe los mensajes y archivos de cada usuario y los reenvía a todos los demás.
#
# Cada mensaje viaja como una línea de texto en formato JSON, por ejemplo:
#   {"tipo": "texto", "texto": "hola"}
#   {"tipo": "archivo", "nombre": "foto.png", "datos": "...base64..."}

import socket
import threading
import json
import os

HOST = "0.0.0.0"   # 0.0.0.0 = escuchar en todas las tarjetas de red del equipo
PUERTO = 5555      # puerto por el que se conectan los clientes
LIMITE = 10 * 1024 * 1024   # tamaño máximo de un mensaje (10 MB, por los archivos)

clientes = {}                 # socket -> nombre del usuario
candado = threading.Lock()    # evita que dos hilos escriban a la vez en el mismo socket


def obtener_mi_ip():
    """Devuelve la IP local del equipo para que los compañeros sepan a dónde conectarse."""
    try:
        # Truco: "conectamos" un socket UDP hacia fuera (no se envía nada)
        # y así sabemos qué IP local usaría el equipo
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def enviar(cliente, mensaje):
    """Convierte el mensaje (un diccionario) a JSON y lo envía a un cliente."""
    linea = json.dumps(mensaje) + "\n"   # el \n marca dónde acaba cada mensaje
    cliente.sendall(linea.encode("utf-8"))


def enviar_a_uno(cliente, mensaje):
    with candado:
        try:
            enviar(cliente, mensaje)
        except:
            pass


def enviar_a_todos(mensaje, remitente=None):
    """Envía un mensaje a todos los clientes menos al que lo ha mandado."""
    with candado:
        for cliente in list(clientes):
            if cliente != remitente:
                try:
                    enviar(cliente, mensaje)
                except:
                    pass


def aviso(texto):
    """Crea un mensaje de aviso del servidor (entradas, salidas...)."""
    return {"tipo": "aviso", "texto": texto}


def atender_cliente(cliente, ip):
    """Escucha los mensajes de un usuario (cada usuario tiene su propio hilo)."""
    nombre = None
    buffer = b""   # aquí vamos juntando los trozos que llegan hasta tener una línea completa

    while True:
        try:
            trozo = cliente.recv(65536)
        except:
            break
        if not trozo:          # si no llega nada, el usuario se ha ido
            break

        buffer += trozo
        if len(buffer) > LIMITE:
            print(f"[!] {nombre or ip} ha enviado algo demasiado grande, lo desconectamos")
            break

        # Puede que hayan llegado varios mensajes juntos: los separamos por el \n
        while b"\n" in buffer:
            linea, buffer = buffer.split(b"\n", 1)
            try:
                mensaje = json.loads(linea.decode("utf-8"))
            except:
                continue   # si llega algo que no es JSON, lo ignoramos

            tipo = mensaje.get("tipo")

            # El primer mensaje de cada usuario tiene que ser su nombre
            if nombre is None:
                if tipo == "nombre":
                    nombre = str(mensaje.get("nombre", "Anónimo"))[:20]
                    with candado:
                        clientes[cliente] = nombre
                    print(f"[+] {nombre} se ha conectado desde {ip}")
                    enviar_a_uno(cliente, aviso("Bienvenido al chat de clase! Puedes mandar mensajes y archivos"))
                    enviar_a_todos(aviso(f"{nombre} se ha unido al chat"), cliente)
                continue

            if tipo == "texto":
                texto = mensaje.get("texto", "")
                print(f"{nombre}: {texto}")
                enviar_a_todos({"tipo": "texto", "de": nombre, "texto": texto}, cliente)

            elif tipo == "archivo":
                # basename quita rutas raras del nombre (por si alguien manda "../../algo")
                nombre_archivo = os.path.basename(str(mensaje.get("nombre", ""))) or "archivo"
                print(f"[archivo] {nombre} ha enviado {nombre_archivo}")
                enviar_a_todos({"tipo": "archivo", "de": nombre,
                                "nombre": nombre_archivo, "datos": mensaje.get("datos", "")}, cliente)

            elif tipo == "usuarios":
                lista = ", ".join(clientes.values())
                enviar_a_uno(cliente, aviso(f"Conectados ({len(clientes)}): {lista}"))

    # Si salimos del bucle es que el usuario se ha desconectado
    with candado:
        clientes.pop(cliente, None)
    cliente.close()
    if nombre:
        print(f"[-] {nombre} se ha desconectado")
        enviar_a_todos(aviso(f"{nombre} ha salido del chat"))


# ----- Programa principal -----
servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # socket TCP
servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # permite reiniciar rápido el servidor
servidor.bind((HOST, PUERTO))
servidor.listen()

print("===== CHAT DE CLASE (v2) =====")
print(f"Servidor encendido. Decid a vuestros compañeros que se conecten a: {obtener_mi_ip()}")
print("(Si usáis Tailscale, dadles la IP 100.x.x.x que sale con: tailscale ip -4)")
print("Pulsa Ctrl+C para apagarlo.\n")

try:
    while True:
        # Esperamos a que alguien se conecte y le creamos su propio hilo
        cliente, direccion = servidor.accept()
        hilo = threading.Thread(target=atender_cliente, args=(cliente, direccion[0]), daemon=True)
        hilo.start()
except KeyboardInterrupt:
    print("\nApagando el servidor...")
    servidor.close()