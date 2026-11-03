# cliente_gui.py
# Cliente del chat de clase con ventana (Tkinter).
# Permite enviar mensajes y archivos. Los archivos recibidos se guardan en la carpeta "recibidos".

import socket
import threading
import queue
import json
import base64
import os
import sys
import subprocess
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext, filedialog

PUERTO = 5555                        # tiene que ser el mismo que en el servidor
TAMANO_MAXIMO = 5 * 1024 * 1024      # archivos de 5 MB como máximo
CARPETA_RECIBIDOS = "recibidos"

# Aquí el hilo que recibe deja los mensajes, y la ventana los va recogiendo
mensajes_recibidos = queue.Queue()


# ----- Funciones de red -----

def enviar_json(mensaje):
    """Convierte el mensaje (un diccionario) a JSON y lo manda al servidor."""
    linea = json.dumps(mensaje) + "\n"
    cliente.sendall(linea.encode("utf-8"))


def recibir_mensajes():
    """Hilo que escucha al servidor y guarda los mensajes en la cola."""
    buffer = b""
    while True:
        try:
            trozo = cliente.recv(65536)
        except:
            break
        if not trozo:
            mensajes_recibidos.put({"tipo": "aviso", "texto": "Se ha cerrado el servidor"})
            break

        buffer += trozo
        # Separamos los mensajes por el \n
        while b"\n" in buffer:
            linea, buffer = buffer.split(b"\n", 1)
            try:
                mensajes_recibidos.put(json.loads(linea.decode("utf-8")))
            except:
                pass


# ----- Funciones de la ventana -----

def mostrar(texto):
    """Escribe un mensaje en la caja del chat."""
    chat.config(state="normal")       # desbloqueamos la caja para poder escribir
    chat.insert("end", texto + "\n")
    chat.config(state="disabled")     # la volvemos a bloquear para que el usuario no la edite
    chat.see("end")                   # bajamos hasta el último mensaje


def guardar_archivo(nombre_archivo, datos_base64):
    """Guarda un archivo recibido en la carpeta "recibidos" y devuelve la ruta."""
    os.makedirs(CARPETA_RECIBIDOS, exist_ok=True)

    # basename quita rutas raras (por si alguien manda "../../algo")
    nombre_archivo = os.path.basename(nombre_archivo) or "archivo"
    ruta = os.path.join(CARPETA_RECIBIDOS, nombre_archivo)

    # Si ya existe un archivo con ese nombre, le añadimos un número: foto(1).png
    base, extension = os.path.splitext(nombre_archivo)
    numero = 1
    while os.path.exists(ruta):
        ruta = os.path.join(CARPETA_RECIBIDOS, f"{base}({numero}){extension}")
        numero += 1

    with open(ruta, "wb") as f:
        f.write(base64.b64decode(datos_base64))
    return ruta


def revisar_mensajes():
    """Cada 100 ms mira si han llegado mensajes nuevos y los muestra."""
    while not mensajes_recibidos.empty():
        mensaje = mensajes_recibidos.get()
        tipo = mensaje.get("tipo")

        if tipo == "texto":
            mostrar(f"{mensaje['de']}: {mensaje['texto']}")
        elif tipo == "aviso":
            mostrar(f"*** {mensaje['texto']} ***")
        elif tipo == "archivo":
            try:
                ruta = guardar_archivo(mensaje["nombre"], mensaje["datos"])
                mostrar(f"📎 {mensaje['de']} ha enviado {mensaje['nombre']} (guardado en {ruta})")
            except:
                mostrar(f"*** No se ha podido guardar el archivo de {mensaje['de']} ***")

    ventana.after(100, revisar_mensajes)


def enviar(event=None):
    """Envía lo que hay escrito en la caja de texto."""
    texto = entrada.get().strip()
    if texto == "":
        return

    try:
        enviar_json({"tipo": "texto", "texto": texto})
    except:
        mostrar("*** Se ha perdido la conexión con el servidor ***")
        return

    # El servidor no nos devuelve nuestros propios mensajes, así que los mostramos nosotros
    mostrar(f"Tú: {texto}")
    entrada.delete(0, "end")   # vaciamos la caja de texto


def enviar_archivo():
    """Abre una ventana para elegir un archivo y lo envía."""
    ruta = filedialog.askopenfilename(title="Elige un archivo para enviar")
    if not ruta:
        return   # el usuario ha cancelado

    if os.path.getsize(ruta) > TAMANO_MAXIMO:
        messagebox.showwarning("Archivo muy grande", "El archivo no puede pasar de 5 MB.")
        return

    # Leemos el archivo y lo pasamos a base64 (texto) para poder meterlo en el JSON
    with open(ruta, "rb") as f:
        datos = base64.b64encode(f.read()).decode("utf-8")

    nombre_archivo = os.path.basename(ruta)
    try:
        enviar_json({"tipo": "archivo", "nombre": nombre_archivo, "datos": datos})
        mostrar(f"📎 Tú has enviado {nombre_archivo}")
    except:
        mostrar("*** Se ha perdido la conexión con el servidor ***")


def pedir_usuarios():
    try:
        enviar_json({"tipo": "usuarios"})
    except:
        mostrar("*** Se ha perdido la conexión con el servidor ***")


def abrir_recibidos():
    """Abre la carpeta de archivos recibidos con el explorador del sistema."""
    os.makedirs(CARPETA_RECIBIDOS, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(CARPETA_RECIBIDOS)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", CARPETA_RECIBIDOS])
    else:
        subprocess.Popen(["xdg-open", CARPETA_RECIBIDOS])


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

enviar_json({"tipo": "nombre", "nombre": nombre})   # lo primero que mandamos es el nombre

# ----- Crear la ventana del chat -----

ventana.title(f"Chat de clase - {nombre}")
ventana.geometry("600x480")
ventana.deiconify()   # ahora sí mostramos la ventana

# Caja donde se ven los mensajes (con barra de desplazamiento)
chat = scrolledtext.ScrolledText(ventana, state="disabled", wrap="word", font=("Arial", 11))
chat.pack(padx=10, pady=10, fill="both", expand=True)

# Fila para escribir: caja de texto + botón enviar
fila_escribir = tk.Frame(ventana)
fila_escribir.pack(padx=10, fill="x")

entrada = tk.Entry(fila_escribir, font=("Arial", 11))
entrada.pack(side="left", fill="x", expand=True, ipady=4)
entrada.bind("<Return>", enviar)   # pulsar Enter también envía
entrada.focus()

tk.Button(fila_escribir, text="Enviar", command=enviar, bg="#4a90d9", fg="white").pack(side="left", padx=(5, 0))

# Fila de botones extra
fila_botones = tk.Frame(ventana)
fila_botones.pack(padx=10, pady=(5, 10), fill="x")

tk.Button(fila_botones, text="📎 Enviar archivo", command=enviar_archivo).pack(side="left")
tk.Button(fila_botones, text="📂 Recibidos", command=abrir_recibidos).pack(side="left", padx=5)
tk.Button(fila_botones, text="👥 Usuarios", command=pedir_usuarios).pack(side="left")

# Si se cierra la ventana con la X, cerramos también la conexión
ventana.protocol("WM_DELETE_WINDOW", cerrar)

# ----- Arrancar -----

hilo = threading.Thread(target=recibir_mensajes, daemon=True)
hilo.start()

revisar_mensajes()   # empieza a revisar la cola de mensajes
ventana.mainloop()   # mantiene la ventana abierta