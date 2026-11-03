# cliente.py
# Cliente del chat de clase: se conecta al servidor y permite enviar y recibir mensajes.

import socket
import threading

PUERTO = 5555   # tiene que ser el mismo que en el servidor

print("===== CHAT DE CLASE =====")
ip_servidor = input("IP del servidor: ")
nombre = input("Tu nombre: ")

cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    cliente.connect((ip_servidor, PUERTO))
except:
    print("No se ha podido conectar. Revisa la IP y que el servidor esté encendido.")
    exit()

# Lo primero que mandamos es nuestro nombre
cliente.send(nombre.encode("utf-8"))


def recibir_mensajes():
    """Se queda escuchando y muestra todo lo que manda el servidor."""
    while True:
        try:
            mensaje = cliente.recv(1024).decode("utf-8")
            if not mensaje:
                print("*** Se ha cerrado el servidor ***")
                break
            print(mensaje)
        except:
            break


# Escuchamos en un hilo aparte para poder escribir y recibir a la vez
hilo = threading.Thread(target=recibir_mensajes, daemon=True)
hilo.start()

# Bucle para escribir mensajes
while True:
    texto = input()

    if texto == "/salir":
        print("Saliendo del chat...")
        break

    if texto.strip() != "":   # no mandamos mensajes vacíos
        try:
            cliente.send(texto.encode("utf-8"))
        except:
            print("Se ha perdido la conexión con el servidor.")
            break

cliente.close()