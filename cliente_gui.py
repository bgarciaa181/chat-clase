# cliente_gui.py
# Cliente del chat de clase con ventana (Tkinter).
# Se conecta al mismo servidor.py que el cliente de terminal.

import socket
import threading
import queue
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext

PUERTO = 5555   # tiene que ser el mismo que en el servidor

# Aquí el hilo que recibe deja los mensajes, y la ventana los va recogiendo
mensajes_recibidos = queue.Queue()


# ----- Funciones -----

def mostrar(texto):
    """Escribe un mensaje en la caja del chat."""
    chat.config(state="normal")       # desbloqueamos la caja para poder escribir
    chat.insert("end", texto + "\n")
    chat.config(state="disabled")     # la volvemos a bloquear para que el usuario no la edite
    chat.see("end")                   # bajamos hasta el último mensaje


def enviar(event=None):
    """Envía lo que hay escrito en la caja de texto."""
    texto = entrada.get().strip()
    if texto == "":
        return

    if texto == "/salir":
        cerrar()
        return

    try:
        cliente.send(texto.encode("utf-8"))
    except:
        mostrar("*** Se ha perdido la conexión con el servidor ***")
        return

    # El servidor no nos devuelve nuestros propios mensajes, así que los mostramos nosotros
    if texto != "/usuarios":
        mostrar(f"Tú: {texto}")

    entrada.delete(0, "end")   # vaciamos la caja de texto


def recibir_mensajes():
    """Hilo que escucha al servidor y guarda los mensajes en la cola."""
    while True:
        try:
            mensaje = cliente.recv(1024).decode("utf-8")
            if not mensaje:
                mensajes_recibidos.put("*** Se ha cerrado el servidor ***")
                break
            mensajes_recibidos.put(mensaje)
        except:
            break


def revisar_mensajes():
    """Cada 100 ms mira si han llegado mensajes nuevos y los muestra."""
    while not mensajes_recibidos.empty():
        mostrar(mensajes_recibidos.get())
    ventana.after(100, revisar_mensajes)


def cerrar():
    """Cierra la conexión y la ventana."""
    try:
        cliente.close()
    except:
        pass
    ventana.destroy()


# ----- Pedir IP y nombre -----

ventana = tk.Tk()
ventana.withdraw()   # ocultamos la ventana principal mientras pedimos los datos

ip_servidor = simpledialog.askstring("Chat de clase", "IP del servidor:", initialvalue="127.0.0.1")
nombre = simpledialog.askstring("Chat de clase", "Tu nombre:")

if not ip_servidor or not nombre:
    exit()

# ----- Conectar con el servidor -----

cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    cliente.connect((ip_servidor, PUERTO))
except:
    messagebox.showerror("Error", "No se ha podido conectar.\nRevisa la IP y que el servidor esté encendido.")
    exit()

cliente.send(nombre.encode("utf-8"))   # lo primero que mandamos es el nombre

# ----- Crear la ventana del chat -----

ventana.title(f"Chat de clase - {nombre}")
ventana.geometry("500x450")
ventana.deiconify()   # ahora sí mostramos la ventana

# Caja donde se ven los mensajes (con barra de desplazamiento)
chat = scrolledtext.ScrolledText(ventana, state="disabled", wrap="word", font=("Arial", 11))
chat.pack(padx=10, pady=10, fill="both", expand=True)

# Parte de abajo: caja para escribir + botones
abajo = tk.Frame(ventana)
abajo.pack(padx=10, pady=(0, 10), fill="x")

entrada = tk.Entry(abajo, font=("Arial", 11))
entrada.pack(side="left", fill="x", expand=True, ipady=4)
entrada.bind("<Return>", enviar)   # pulsar Enter también envía
entrada.focus()

boton_enviar = tk.Button(abajo, text="Enviar", command=enviar, bg="#4a90d9", fg="white")
boton_enviar.pack(side="left", padx=(5, 0))

boton_usuarios = tk.Button(abajo, text="👥 Usuarios", command=lambda: cliente.send("/usuarios".encode("utf-8")))
boton_usuarios.pack(side="left", padx=(5, 0))

# Si se cierra la ventana con la X, cerramos también la conexión
ventana.protocol("WM_DELETE_WINDOW", cerrar)

# ----- Arrancar -----

hilo = threading.Thread(target=recibir_mensajes, daemon=True)
hilo.start()

revisar_mensajes()   # empieza a revisar la cola de mensajes
ventana.mainloop()   # mantiene la ventana abierta