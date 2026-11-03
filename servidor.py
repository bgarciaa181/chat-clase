# servidor.py
# Servidor del chat de clase por red local.
# Recibe los mensajes de cada usuario y los reenvía a todos los demás.

import socket
import threading

HOST = "0.0.0.0"   # 0.0.0.0 = escuchar en todas las tarjetas de red del equipo
PUERTO = 5555      # puerto por el que se conectan los clientes

clientes = []      # sockets de los usuarios conectados
nombres = []       # nombres de los usuarios (en la misma posición que en "clientes")


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


def enviar_a_todos(mensaje, remitente=None):
    """Envía un mensaje a todos los clientes menos al que lo ha escrito."""
    for cliente in clientes:
        if cliente != remitente:
            try:
                cliente.send(mensaje.encode("utf-8"))
            except:
                pass


def quitar_cliente(cliente):
    """Quita a un usuario de las listas cuando se desconecta."""
    if cliente in clientes:
        posicion = clientes.index(cliente)
        nombre = nombres[posicion]
        clientes.pop(posicion)
        nombres.pop(posicion)
        cliente.close()
        print(f"[-] {nombre} se ha desconectado")
        enviar_a_todos(f"*** {nombre} ha salido del chat ***")


def atender_cliente(cliente):
    """Escucha los mensajes de un usuario (cada usuario tiene su propio hilo)."""
    while True:
        try:
            mensaje = cliente.recv(1024).decode("utf-8")
        except:
            mensaje = ""

        # Si no llega nada, el usuario se ha ido
        if not mensaje:
            quitar_cliente(cliente)
            break

        nombre = nombres[clientes.index(cliente)]

        # Comando para ver quién está conectado
        if mensaje == "/usuarios":
            lista = ", ".join(nombres)
            cliente.send(f"*** Conectados ({len(nombres)}): {lista} ***".encode("utf-8"))
        else:
            print(f"{nombre}: {mensaje}")
            enviar_a_todos(f"{nombre}: {mensaje}", cliente)


# ----- Programa principal -----
servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # socket TCP
servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # permite reiniciar rápido el servidor
servidor.bind((HOST, PUERTO))
servidor.listen()

print("===== CHAT DE CLASE =====")
print(f"Servidor encendido. Decid a vuestros compañeros que se conecten a: {obtener_mi_ip()}")
print("Pulsa Ctrl+C para apagarlo.\n")

try:
    while True:
        # Esperamos a que alguien se conecte
        cliente, direccion = servidor.accept()

        # Lo primero que manda el cliente es su nombre
        nombre = cliente.recv(1024).decode("utf-8")
        clientes.append(cliente)
        nombres.append(nombre)

        print(f"[+] {nombre} se ha conectado desde {direccion[0]}")
        cliente.send("*** Bienvenido al chat de clase! Escribe /usuarios para ver quien esta y /salir para irte ***".encode("utf-8"))
        enviar_a_todos(f"*** {nombre} se ha unido al chat ***", cliente)

        # Creamos un hilo para escuchar a este usuario sin bloquear a los demás
        hilo = threading.Thread(target=atender_cliente, args=(cliente,), daemon=True)
        hilo.start()
except KeyboardInterrupt:
    print("\nApagando el servidor...")
    servidor.close()