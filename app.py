# -*- coding: utf-8 -*-
"""
app.py
======
Interfaz gráfica (Tkinter) del sistema de ventas — conversión a Python del
proyecto original en Delphi/FMX (uLogin, uVenta, uInventario, uMovimiento,
uNuevoProducto).

Esta capa SOLO dibuja pantallas y reacciona a clics: toda la lógica de
negocio (carrito, totales, filtros, reportes) viene de core.py, y todo el
acceso a datos viene de db.py. Así se respeta la separación que pide la
Unidad 2: funciones puras aisladas del resto del programa.

La navegación es un ttk.Notebook real (pestañas de verdad: Venta,
Inventario, Movimientos, Reporte) y el tamaño de la ventana se ajusta a la
pantalla real del dispositivo, para que se vea bien tanto en una laptop
como en un teléfono.

Ejecutar con:  python3 app.py
"""

from __future__ import annotations

import datetime as dt
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

import core
import db


def hoy() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Ventas — versión Python (funcional)")
        self._ajustar_tamano_ventana()
        self._configurar_estilos()

        self.usuario: dict | None = None
        self.carrito: tuple[core.ItemCarrito, ...] = ()

        # Arranca el folio DESPUÉS de las ventas que ya existan en la base
        # (evita choques de "UNIQUE constraint failed" al reabrir la app
        # con datos guardados de sesiones anteriores). Si esta consulta
        # puntual fallara por algo, no debe tumbar el arranque de toda la
        # interfaz — en el peor caso el folio arranca desde 1.
        try:
            siguiente_folio = db.contar_ventas() + 1
        except Exception:
            siguiente_folio = 1
        self.folios = core.generar_folios(inicio=siguiente_folio)

        self.contenedor = tk.Frame(self)
        self.contenedor.pack(fill="both", expand=True)

        self.mostrar_login()

    # ------------------------------------------------------------------
    def _ajustar_tamano_ventana(self):
        """Usa el tamaño real de la pantalla en vez de un tamaño fijo pensado
        para escritorio. En un teléfono, si la ventana pide más ancho del
        que hay pantalla, todo lo que quede a la derecha (botones, texto)
        se corta — por eso "COBRAR" se veía como "OBRA"."""
        ancho_pantalla = self.winfo_screenwidth()
        alto_pantalla = self.winfo_screenheight()
        ancho = min(980, ancho_pantalla)
        alto = min(580, alto_pantalla)
        self.geometry(f"{ancho}x{alto}+0+0")
        self.minsize(min(320, ancho), min(480, alto))

    def _configurar_estilos(self):
        """Fija una altura de fila para las tablas, calculada a partir de la
        MÉTRICA REAL de la fuente en este dispositivo (no un número fijo
        adivinado). En Android el texto suele dibujarse más alto de lo
        normal; si el rowheight es fijo y pequeño, las filas se encimaban.
        Aquí se mide el alto real de línea de la fuente y se le da margen,
        así se ajusta solo sin importar el tamaño de fuente del sistema."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        fuente_celdas = tkfont.Font(font="TkDefaultFont").actual()
        familia = fuente_celdas["family"]
        tamano = max(fuente_celdas["size"], 10)
        medidor = tkfont.Font(family=familia, size=tamano)
        alto_linea = medidor.metrics("linespace")
        rowheight = alto_linea + 16  # margen generoso arriba/abajo de cada fila

        # IMPORTANTE: se le pasa a ttk una tupla (familia, tamaño), nunca el
        # objeto Font directamente — pasarlo como objeto hacía que el texto
        # de las celdas se dibujara casi invisible en Android.
        style.configure("Treeview", rowheight=rowheight, font=(familia, tamano))
        style.configure("Treeview.Heading", font=(familia, tamano, "bold"))
        style.configure("TNotebook.Tab", padding=(16, 8), font=(familia, tamano, "bold"))

    # ------------------------------------------------------------------
    def limpiar_contenedor(self):
        for widget in self.contenedor.winfo_children():
            widget.destroy()

    def boton_ancho(self, padre, **kwargs):
        """Botón que siempre puede crecer para ocupar su columna del grid,
        en vez de quedar pegado a un ancho fijo que se corta en pantallas
        angostas."""
        return tk.Button(padre, **kwargs)

    def _tabla_con_scroll(self, padre, columnas, anchos, height):
        """Treeview con scrollbar vertical, reutilizado por todas las
        tablas de la app (catálogo, carrito, inventario, reporte)."""
        marco = tk.Frame(padre)
        tabla = ttk.Treeview(marco, columns=columnas, show="headings", height=height)
        for col, ancho in zip(columnas, anchos):
            tabla.heading(col, text=col.capitalize())
            tabla.column(col, width=ancho, minwidth=ancho, anchor="center", stretch=True)
        scroll = ttk.Scrollbar(marco, orient="vertical", command=tabla.yview)
        tabla.configure(yscrollcommand=scroll.set)
        tabla.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return marco, tabla

    # ------------------------------------------------------------------
    # LOGIN  (equivalente a uLogin.pas)
    # ------------------------------------------------------------------
    def mostrar_login(self):
        self.limpiar_contenedor()
        self.usuario = None
        marco = tk.Frame(self.contenedor)
        marco.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(marco, text="Iniciar sesión", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, columnspan=2, pady=(0, 16)
        )
        tk.Label(marco, text="Usuario:").grid(row=1, column=0, sticky="e", pady=4)
        entry_user = tk.Entry(marco, width=20)
        entry_user.grid(row=1, column=1, pady=4)
        entry_user.insert(0, "dia")

        tk.Label(marco, text="Contraseña:").grid(row=2, column=0, sticky="e", pady=4)
        entry_pass = tk.Entry(marco, width=20, show="•")
        entry_pass.grid(row=2, column=1, pady=4)
        entry_pass.insert(0, "1234")

        def intentar_login(event=None):
            u = db.validar_login(entry_user.get().strip(), entry_pass.get().strip())
            if u is None:
                messagebox.showerror("Acceso denegado", "Usuario o contraseña incorrecto.")
                return
            self.usuario = u
            self.carrito = ()
            self.mostrar_principal()

        entry_pass.bind("<Return>", intentar_login)
        tk.Button(marco, text="Ingresar", width=18, command=intentar_login).grid(
            row=3, column=0, columnspan=2, pady=(14, 0)
        )
        tk.Label(marco, text="(usuario de prueba: dia / 1234)", fg="gray").grid(
            row=4, column=0, columnspan=2, pady=(8, 0)
        )

    # ------------------------------------------------------------------
    # PANTALLA PRINCIPAL: barra delgada + pestañas reales (Notebook)
    # ------------------------------------------------------------------
    def mostrar_principal(self):
        self.limpiar_contenedor()

        barra = tk.Frame(self.contenedor, bg="#1f2937")
        barra.pack(fill="x")
        tk.Label(
            barra, text=f"Usuario: {self.usuario['full_name']}",
            bg="#1f2937", fg="white", font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=10, pady=6)
        tk.Button(barra, text="Cerrar sesión", command=self.mostrar_login).pack(
            side="right", padx=8, pady=4
        )

        self.notebook = ttk.Notebook(self.contenedor)
        self.notebook.pack(fill="both", expand=True)

        tab_venta = tk.Frame(self.notebook)
        tab_inventario = tk.Frame(self.notebook)
        tab_movimientos = tk.Frame(self.notebook)
        self.tab_reporte = tk.Frame(self.notebook)

        self.notebook.add(tab_venta, text="Venta")
        self.notebook.add(tab_inventario, text="Inventario")
        self.notebook.add(tab_movimientos, text="Movimientos")
        self.notebook.add(self.tab_reporte, text="Reporte")

        self.refrescar_catalogo_venta = self.construir_punto_de_venta(tab_venta)
        self.refrescar_inventario = self.construir_inventario(tab_inventario)
        self.construir_movimientos(tab_movimientos)

        self.notebook.bind("<<NotebookTabChanged>>", self._al_cambiar_pestana)

    def _al_cambiar_pestana(self, event=None):
        """Cada pestaña siempre muestra datos frescos de la base de datos,
        sin importar en qué otra pestaña se hicieron los cambios."""
        titulo = self.notebook.tab(self.notebook.select(), "text")
        if titulo == "Venta":
            self.refrescar_catalogo_venta()
        elif titulo == "Inventario":
            self.refrescar_inventario()
        elif titulo == "Reporte":
            self.construir_reporte(self.tab_reporte)

    # ------------------------------------------------------------------
    # PUNTO DE VENTA (equivalente a uVenta.pas)
    # ------------------------------------------------------------------
    def construir_punto_de_venta(self, cuerpo):
        cuerpo.columnconfigure(0, weight=1)

        buscador = tk.Frame(cuerpo)
        buscador.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(buscador, text="Buscar / cantidad (ej. '3xagua'):").pack(anchor="w")
        entry_busqueda = tk.Entry(buscador)
        entry_busqueda.pack(fill="x", pady=4)
        entry_busqueda.focus_set()

        # --- Catálogo: se ve QUÉ se está vendiendo, igual que en Inventario.
        # Tocar (doble clic / doble toque) un producto lo agrega al carrito.
        tk.Label(cuerpo, text="Catálogo — toca un producto para agregarlo:",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10)
        # Sin columna de código: el nombre completo importa más que el
        # código de barras aquí, y el buscador ya filtra por ambos.
        marco_catalogo, tabla_catalogo = self._tabla_con_scroll(
            cuerpo, ("producto", "precio", "stock"), (220, 80, 70), height=4
        )
        marco_catalogo.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        tabla_catalogo.column("producto", anchor="w")

        # --- Carrito de la venta en curso.
        tk.Label(cuerpo, text="Carrito:", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10)
        marco_carrito, tabla = self._tabla_con_scroll(
            cuerpo, ("cant", "producto", "precio", "total"), (50, 190, 80, 90), height=4
        )
        marco_carrito.pack(fill="both", expand=True, padx=10, pady=(2, 6))
        tabla.column("producto", anchor="w")

        lbl_total = tk.Label(cuerpo, text="Total: $0.00", font=("Segoe UI", 16, "bold"))
        lbl_total.pack(anchor="e", padx=10)

        def refrescar_tabla():
            tabla.delete(*tabla.get_children())
            for item in self.carrito:
                tabla.insert("", "end", iid=item.barcode,
                             values=(item.qty, item.name,
                                     f"{item.price:.2f}", f"{core.total_item(item):.2f}"))
            lbl_total.config(text=f"Total: ${core.total_carrito(self.carrito):.2f}")

        def refrescar_catalogo(*_):
            """FILTER (core.buscar_productos) sobre lo que se escribe en el
            buscador; con el campo vacío muestra todo el catálogo activo."""
            texto = entry_busqueda.get()
            _cantidad, patron = core.parsear_busqueda(texto)
            productos = db.obtener_productos()
            visibles = core.buscar_productos(productos, patron)
            tabla_catalogo.delete(*tabla_catalogo.get_children())
            for p in visibles:
                tabla_catalogo.insert("", "end", iid=p.barcode,
                                      values=(p.name, f"{p.price:.2f}", p.stock))

        def agregar_al_carrito(producto: core.Producto, cantidad: int) -> bool:
            if producto.stock <= 0:
                messagebox.showerror("Sin existencias", f'"{producto.name}" está agotado.')
                return False
            ya_en_carrito = next((i.qty for i in self.carrito if i.barcode == producto.barcode), 0)
            if ya_en_carrito + cantidad > producto.stock:
                messagebox.showerror(
                    "Stock insuficiente",
                    f"Disponible: {producto.stock} pzas. Solicitado: {ya_en_carrito + cantidad} pzas.",
                )
                return False
            self.carrito = core.agregar_al_carrito(self.carrito, producto, cantidad)
            if producto.stock <= 5:
                messagebox.showwarning(
                    "Alerta de stock mínimo", f'Solo quedan {producto.stock} unidades de "{producto.name}".'
                )
            refrescar_tabla()
            return True

        def agregar_por_busqueda(event=None):
            texto = entry_busqueda.get()
            cantidad, patron = core.parsear_busqueda(texto)
            if not patron:
                return
            productos = db.obtener_productos()
            coincidencias = core.buscar_productos(productos, patron)
            if not coincidencias:
                messagebox.showwarning("Sin resultados", f'No se encontró ningún producto para "{patron}".')
                entry_busqueda.delete(0, tk.END)
                return
            agregar_al_carrito(coincidencias[0], cantidad)
            entry_busqueda.delete(0, tk.END)
            refrescar_catalogo()

        def agregar_desde_catalogo(event=None):
            seleccion = tabla_catalogo.selection()
            if not seleccion:
                return
            barcode = seleccion[0]
            productos = db.obtener_productos()
            producto = next((p for p in productos if p.barcode == barcode), None)
            if producto is not None:
                agregar_al_carrito(producto, 1)

        entry_busqueda.bind("<Return>", agregar_por_busqueda)
        entry_busqueda.bind("<KeyRelease>", refrescar_catalogo)
        tabla_catalogo.bind("<Double-1>", agregar_desde_catalogo)

        def quitar_seleccionado():
            seleccion = tabla.selection()
            if not seleccion:
                messagebox.showinfo("Carrito", "Selecciona primero un renglón para quitarlo.")
                return
            self.carrito = core.quitar_del_carrito(self.carrito, seleccion[0])
            refrescar_tabla()

        def limpiar_carrito():
            if self.carrito and messagebox.askyesno("Confirmar", "¿Cancelar la venta y limpiar el carrito?"):
                self.carrito = ()
                refrescar_tabla()

        def cobrar():
            if not self.carrito:
                messagebox.showinfo("Carrito vacío", "Agrega productos antes de cobrar.")
                return
            folio = next(self.folios)
            try:
                db.registrar_venta(folio, self.usuario["username"], hoy(), self.carrito)
            except Exception as exc:  # pragma: no cover - solo UI
                messagebox.showerror("Error al cobrar", str(exc))
                return
            messagebox.showinfo(
                "Venta cobrada",
                f"¡Venta cobrada!\nFolio: {folio}\nTotal: ${core.total_carrito(self.carrito):.2f}",
            )
            self.carrito = ()
            refrescar_tabla()
            refrescar_catalogo()

        # Botones en grid con columnas de igual peso: así ninguno se corta
        # aunque la pantalla sea angosta, y "Cobrar" siempre queda visible.
        botones = tk.Frame(cuerpo)
        botones.pack(fill="x", padx=10, pady=(0, 10))
        botones.columnconfigure((0, 1, 2), weight=1)
        tk.Button(botones, text="Quitar", command=quitar_seleccionado).grid(row=0, column=0, sticky="ew", padx=2)
        tk.Button(botones, text="Limpiar", command=limpiar_carrito).grid(row=0, column=1, sticky="ew", padx=2)
        tk.Button(
            botones, text="Cobrar", bg="#16a34a", fg="white", font=("Segoe UI", 10, "bold"), command=cobrar
        ).grid(row=0, column=2, sticky="ew", padx=2)

        refrescar_tabla()
        refrescar_catalogo()
        return refrescar_catalogo

    # ------------------------------------------------------------------
    # INVENTARIO (equivalente a uInventario.pas + uNuevoProducto.pas)
    # ------------------------------------------------------------------
    def construir_inventario(self, cuerpo):
        buscador = tk.Frame(cuerpo)
        buscador.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(buscador, text="Filtrar por nombre o código:").pack(anchor="w")
        entry_filtro = tk.Entry(buscador)
        entry_filtro.pack(fill="x", pady=4)

        marco_tabla, tabla = self._tabla_con_scroll(
            cuerpo, ("codigo", "producto", "categoria", "precio", "stock"), (110, 160, 120, 70, 60), height=9
        )
        marco_tabla.pack(fill="both", expand=True, padx=10, pady=6)

        lbl_valor = tk.Label(cuerpo, text="Valor total del inventario: $0.00",
                              font=("Segoe UI", 10, "bold"), wraplength=900, justify="left")
        lbl_valor.pack(anchor="w", padx=10)

        lbl_alertas = tk.Label(cuerpo, text="", fg="#b45309", justify="left",
                                wraplength=900, anchor="w")
        lbl_alertas.pack(fill="x", padx=10, pady=(4, 0))

        def refrescar(*_):
            productos = db.obtener_productos()
            texto = entry_filtro.get().strip().lower()
            visibles = tuple(
                p for p in productos
                if texto == "" or texto in p.name.lower() or texto in p.barcode
            )
            tabla.delete(*tabla.get_children())
            for p in visibles:
                tabla.insert("", "end", iid=p.barcode,
                             values=(p.barcode, p.name, p.category, f"{p.price:.2f}", p.stock))

            arbol = core.construir_arbol_categorias(productos)
            lbl_valor.config(text=f"Valor total del inventario: ${core.valor_total_inventario(arbol):.2f}")

            bajos = list(core.productos_con_stock_bajo(productos))
            if bajos:
                nombres = ", ".join(p.name for p in bajos)
                lbl_alertas.config(text=f"Aviso — stock mínimo (≤5 pzas): {nombres}")
            else:
                lbl_alertas.config(text="")

        entry_filtro.bind("<KeyRelease>", refrescar)

        def eliminar_seleccionado():
            seleccion = tabla.selection()
            if not seleccion:
                messagebox.showinfo("Inventario", "Selecciona primero el producto a eliminar.")
                return
            barcode = seleccion[0]
            nombre = tabla.item(barcode, "values")[1]
            if messagebox.askyesno(
                "Confirmar eliminación",
                f'¿Eliminar permanentemente "{nombre}"?\nSe borrará su historial de movimientos y ventas.',
            ):
                db.eliminar_producto(barcode)
                refrescar()

        def abrir_alta():
            self.dialogo_nuevo_producto(on_guardado=refrescar)

        botones = tk.Frame(cuerpo)
        botones.pack(fill="x", padx=10, pady=(0, 10))
        botones.columnconfigure((0, 1), weight=1)
        tk.Button(botones, text="Nuevo producto", command=abrir_alta).grid(row=0, column=0, sticky="ew", padx=2)
        tk.Button(botones, text="Eliminar seleccionado", command=eliminar_seleccionado).grid(
            row=0, column=1, sticky="ew", padx=2
        )

        refrescar()
        return refrescar

    def dialogo_nuevo_producto(self, on_guardado):
        """Equivalente a uNuevoProducto.pas, como ventana modal."""
        ventana = tk.Toplevel(self)
        ventana.title("Nuevo producto")
        ventana.grab_set()
        ventana.columnconfigure(1, weight=1)
        # El tamaño se calcula AL FINAL, a partir de lo que los widgets
        # realmente ocupan (ver más abajo) — un tamaño fijo en píxeles no
        # coincidía con cómo Android termina dibujando la ventana y dejaba
        # un hueco vacío enorme.

        campos = {}
        for i, (etiqueta, clave) in enumerate(
            [("Código de barras:", "barcode"), ("Nombre:", "name"),
             ("Categoría:", "category"), ("Precio:", "price"), ("Existencias:", "stock")]
        ):
            tk.Label(ventana, text=etiqueta).grid(row=i, column=0, sticky="e", padx=8, pady=6)
            entry = tk.Entry(ventana)
            entry.grid(row=i, column=1, pady=6, padx=(0, 4), sticky="ew")
            campos[clave] = entry
        campos["category"].insert(0, "General")

        def escanear():
            """Abre la cámara y decodifica un código de barras (EAN/UPC)
            usando el módulo scanner.py. Requiere opencv-contrib-python o
            pyzbar instalado — si falta, avisa cómo instalarlo en vez de
            truena la app."""
            try:
                import scanner
            except ImportError:
                messagebox.showerror(
                    "Escáner no disponible",
                    "Falta el archivo scanner.py junto a app.py.",
                )
                return
            try:
                codigo = scanner.escanear_codigo_barras()
            except Exception as exc:
                messagebox.showerror("No se pudo escanear", str(exc))
                return
            if codigo:
                campos["barcode"].delete(0, tk.END)
                campos["barcode"].insert(0, codigo)
            else:
                messagebox.showinfo("Escaneo cancelado", "No se detectó ningún código de barras.")

        tk.Button(ventana, text="Escanear código", command=escanear).grid(
            row=0, column=2, padx=(0, 8), pady=6, sticky="ew"
        )

        def guardar():
            try:
                barcode = campos["barcode"].get().strip()
                name = campos["name"].get().strip()
                category = campos["category"].get().strip() or "General"
                price = float(campos["price"].get().strip())
                stock = int(campos["stock"].get().strip())
                if not barcode or not name:
                    raise ValueError("Código y nombre son obligatorios.")
                db.agregar_producto(barcode, name, category, price, stock)
            except Exception as exc:
                messagebox.showerror("Datos inválidos", str(exc))
                return
            ventana.destroy()
            on_guardado()

        tk.Button(ventana, text="Guardar", bg="#16a34a", fg="white", command=guardar).grid(
            row=6, column=0, columnspan=2, pady=14
        )

        # Tamaño real: se mide lo que los widgets ya colocados necesitan
        # (reqwidth/reqheight) en vez de adivinar un "420x300" que no
        # coincidía con el dispositivo, y se centra en la pantalla.
        ventana.update_idletasks()
        # max(...) evita que la ventana quede diminuta si el dispositivo
        # todavía no calculó bien el tamaño de los widgets en este momento.
        ancho = min(max(ventana.winfo_reqwidth() + 20, 300), self.winfo_screenwidth() - 20)
        alto = min(max(ventana.winfo_reqheight() + 20, 260), self.winfo_screenheight() - 40)
        x = max(0, (self.winfo_screenwidth() - ancho) // 2)
        y = max(0, (self.winfo_screenheight() - alto) // 3)
        ventana.geometry(f"{ancho}x{alto}+{x}+{y}")

    # ------------------------------------------------------------------
    # MOVIMIENTOS (equivalente a uMovimiento.pas)
    # ------------------------------------------------------------------
    def construir_movimientos(self, cuerpo):
        marco = tk.Frame(cuerpo)
        marco.pack(fill="x", padx=20, pady=20)
        marco.columnconfigure(1, weight=1)

        tk.Label(marco, text="Código de barras:").grid(row=0, column=0, sticky="e", pady=6)
        entry_codigo = tk.Entry(marco)
        entry_codigo.grid(row=0, column=1, pady=6, sticky="ew")

        tk.Label(marco, text="Tipo de movimiento:").grid(row=1, column=0, sticky="e", pady=6)
        combo_tipo = ttk.Combobox(
            marco, state="readonly",
            values=["Compra (reabasto)", "Devolución de cliente", "Merma", "Salida"],
        )
        combo_tipo.grid(row=1, column=1, pady=6, sticky="ew")

        tk.Label(marco, text="Cantidad:").grid(row=2, column=0, sticky="e", pady=6)
        entry_cantidad = tk.Entry(marco)
        entry_cantidad.grid(row=2, column=1, pady=6, sticky="ew")

        mapa_tipo = {
            "Compra (reabasto)": "compra",
            "Devolución de cliente": "devolucion",
            "Merma": "merma",
            "Salida": "salida",
        }

        def registrar():
            codigo = entry_codigo.get().strip()
            tipo_ui = combo_tipo.get()
            cantidad_txt = entry_cantidad.get().strip()
            if not codigo or not tipo_ui or not cantidad_txt:
                messagebox.showwarning("Faltan datos", "Completa todos los campos antes de registrar.")
                return
            try:
                cantidad = int(cantidad_txt)
                if cantidad <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Cantidad inválida", "La cantidad debe ser un entero mayor a cero.")
                return
            try:
                db.registrar_movimiento(codigo, mapa_tipo[tipo_ui], cantidad, hoy())
            except Exception as exc:
                messagebox.showerror("Error", str(exc))
                return
            messagebox.showinfo("Listo", "¡Movimiento registrado con éxito en el inventario!")
            entry_codigo.delete(0, tk.END)
            entry_cantidad.delete(0, tk.END)
            combo_tipo.set("")

        tk.Button(marco, text="Registrar movimiento", bg="#2563eb", fg="white", command=registrar).grid(
            row=3, column=0, columnspan=2, pady=16, sticky="ew"
        )

    # ------------------------------------------------------------------
    # REPORTE FUNCIONAL (pipeline filter -> map -> reduce sobre ventas)
    # ------------------------------------------------------------------
    def construir_reporte(self, cuerpo):
        for widget in cuerpo.winfo_children():
            widget.destroy()

        resumen = tk.Label(cuerpo, font=("Segoe UI", 10), justify="left", anchor="w",
                            wraplength=900)
        resumen.pack(fill="x", padx=10, pady=(10, 8))

        columnas = ("producto", "cantidad", "importe")
        tabla = ttk.Treeview(cuerpo, columns=columnas, show="headings", height=10)
        for col, ancho in zip(columnas, (220, 80, 100)):
            tabla.heading(col, text=col.capitalize())
            tabla.column(col, width=ancho, anchor="center", stretch=True)
        tabla.pack(fill="both", expand=True, padx=10)

        ventas = db.obtener_ventas()
        datos = core.reporte_ventas(ventas)  # filter -> map -> reduce, ver core.py

        resumen.config(
            text=(
                f"Ventas: {datos['num_ventas']}   "
                f"Total: ${datos['total_periodo']:.2f}   "
                f"Ticket promedio: ${datos['ticket_promedio']:.2f}   "
                f"Producto estrella: {datos['top_producto']}"
            )
        )

        for nombre, info in sorted(datos["por_producto"].items(), key=lambda kv: -kv[1]["importe"]):
            tabla.insert("", "end", values=(nombre, info["cantidad"], f"{info['importe']:.2f}"))

        if not ventas:
            tk.Label(cuerpo, text="Aún no hay ventas registradas. Cobra algo en la pestaña Venta primero.",
                     fg="gray").pack(pady=10)


def _mostrar_error_de_arranque(mensaje: str):
    """Si algo falla ANTES de que exista una ventana normal, esto muestra
    un cuadro de error de todos modos, en vez de que la app 'no abra nada'
    sin ninguna pista de qué pasó."""
    try:
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror("No se pudo iniciar la aplicación", mensaje)
        raiz.destroy()
    except Exception:
        print(mensaje)  # último recurso: al menos que quede en la consola


if __name__ == "__main__":
    try:
        db.inicializar()
    except Exception as exc:
        _mostrar_error_de_arranque(
            "No se pudo preparar la base de datos (ventas.db).\n\n"
            f"Detalle: {exc}\n\n"
            "Si el problema sigue, cierra la app, BORRA el archivo "
            "ventas.db (está junto a app.py) y ábrela de nuevo — así se "
            "vuelve a crear limpio, sin perder el código."
        )
    else:
        try:
            App().mainloop()
        except Exception as exc:
            _mostrar_error_de_arranque(
                f"La aplicación se cerró por un error inesperado:\n\n{exc}"
            )
