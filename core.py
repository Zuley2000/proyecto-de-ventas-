# -*- coding: utf-8 -*-
"""
core.py
========
Núcleo FUNCIONAL del sistema de ventas (conversión del proyecto original en
Delphi/FireDAC + PostgreSQL a Python).

Este módulo NO toca la base de datos ni la interfaz gráfica: solo recibe
datos, los transforma y regresa datos nuevos. Es la parte que aplica los
conceptos de la Unidad 2 (Programación Funcional):

    - Funciones puras (misma entrada -> misma salida, sin efectos secundarios)
    - Inmutabilidad (namedtuples y tuplas; nunca se muta una colección)
    - Funciones como valores / de orden superior (aplicar, pipeline)
    - lambda
    - range()
    - Operadores como funciones (módulo operator)
    - Predicados + filter()
    - map / filter / reduce combinados en pipelines
    - Comprensiones de listas
    - Recursividad y árboles (árbol de categorías)
    - Evaluación perezosa: generadores con yield

La capa de base de datos (db.py) solo entrega "filas crudas" y esta capa las
convierte en resultados, exactamente como el pipeline visto en clase:

    datos -> filtrar -> transformar -> agregar -> resultado
"""

from __future__ import annotations

import operator
from collections import namedtuple
from functools import reduce
from itertools import count

# ---------------------------------------------------------------------------
# 2.1 Tipos de datos (inmutables)
# ---------------------------------------------------------------------------
# En el proyecto original cada producto era una fila de PostgreSQL
# (product_id, barcode, name, selling_price, stock_quantity, category).
# Aquí un Producto es una tupla con nombre: no se puede mutar por accidente,
# igual que se vio con las tuplas en la presentación (2.1 y 2.6).

Producto = namedtuple(
    "Producto", ["id", "barcode", "name", "price", "stock", "category", "active"]
)

# Un ítem del carrito. "total" siempre se recalcula con una función pura,
# nunca se guarda "a mano" para no arriesgarnos a que quede desincronizado.
ItemCarrito = namedtuple("ItemCarrito", ["barcode", "name", "price", "qty"])

# Una venta ya cerrada (cabecera), tal como "sales" en el proyecto Delphi.
Venta = namedtuple("Venta", ["folio", "fecha", "usuario", "items", "total"])

# Tipos de movimiento de inventario (equivalente a la tabla movement_types
# y al mapeo case..of de uMovimiento.pas)
TIPOS_MOVIMIENTO = {
    "compra": 2,
    "devolucion": 3,
    "merma": 5,
    "salida": 6,
}


# ---------------------------------------------------------------------------
# 2.2 Funciones de orden superior / funciones puras básicas
# ---------------------------------------------------------------------------

def aplicar(funcion, valor):
    """Función de orden superior: recibe otra función y la aplica.

    Idéntica en espíritu al ejemplo 'aplicar(funcion, valor)' de la
    presentación (2.2 Funciones de orden superior).
    """
    return funcion(valor)


def pipeline(*funciones):
    """Compone funciones de izquierda a derecha: pipeline(f, g, h)(x) == h(g(f(x))).

    Esto es lo que en la presentación se llama "pipeline funcional":
    datos -> filtrar -> transformar -> agregar -> resultado.
    """
    return reduce(lambda f, g: (lambda x: g(f(x))), funciones, lambda x: x)


# ---------------------------------------------------------------------------
# 2.3 / 2.4 range() y operadores como funciones (operator)
# ---------------------------------------------------------------------------

def generar_folios(prefijo="FAC", inicio=1):
    """Generador (evaluación perezosa) de folios consecutivos: FAC-000001, ...

    Usa itertools.count, la versión "infinita" de range() vista en la
    sección 2.7 (secuencia infinita con yield). No calcula todos los folios
    de antemano: entrega uno solo cada vez que se le pide next().
    """
    for numero in count(inicio):
        yield f"{prefijo}-{numero:06d}"


def es_precio_valido(p: Producto) -> bool:
    """Predicado puro: True/False, sin efectos secundarios (2.4)."""
    return operator.gt(p.price, 0) and operator.ge(p.stock, 0)


# ---------------------------------------------------------------------------
# 2.2 Parseo de texto del buscador ("3x7501234" o "7501234")
# ---------------------------------------------------------------------------

def parsear_busqueda(texto: str) -> tuple[int, str]:
    """Función pura que reemplaza el bloque imperativo de
    AgregarProductoAlCarrito en uVenta.pas / uInventario.pas.

    Misma entrada -> misma salida siempre. Regresa (cantidad, codigo_o_nombre).
    """
    texto = texto.strip()
    if not texto:
        return (1, "")

    minus = texto.lower()
    pos = minus.find("x")
    if pos <= 0:
        pos = texto.find("*")

    if 0 < pos < len(texto) - 1:
        izquierda, derecha = texto[:pos].strip(), texto[pos + 1:].strip()
        if izquierda.isdigit():
            return (int(izquierda), derecha)

    return (1, texto)


# ---------------------------------------------------------------------------
# 2.5 map / filter / reduce sobre productos
# ---------------------------------------------------------------------------

def buscar_productos(productos: tuple[Producto, ...], texto: str) -> tuple[Producto, ...]:
    """FILTER: selecciona productos activos que hagan match por código o nombre.

    Equivale al WHERE barcode = ... OR name ILIKE ... AND is_active = TRUE
    de las consultas SQL originales, pero como un predicado de Python.
    """
    texto = texto.strip().lower()
    coincide = lambda p: p.active and (p.barcode == texto or texto in p.name.lower())
    return tuple(filter(coincide, productos))


def productos_con_stock_bajo(productos: tuple[Producto, ...], umbral: int = 5):
    """Generador perezoso (yield): productos con 0 < stock <= umbral.

    Reemplaza el ShowMessage de "ALERTA DE STOCK MÍNIMO" del Delphi, pero de
    forma funcional: no imprime nada, solo entrega los productos que
    cumplen el predicado, uno a la vez.
    """
    predicado = lambda p: 0 < p.stock <= umbral
    return (p for p in filter(predicado, productos))


def total_item(item: ItemCarrito) -> float:
    """Función pura: total de una fila del carrito (cantidad x precio)."""
    return round(item.qty * item.price, 2)


def total_carrito(carrito: tuple[ItemCarrito, ...]) -> float:
    """MAP + REDUCE: transforma cada ítem a su total y los acumula.

    Es exactamente el pipeline "1..N -> map(total) -> reduce(suma)" de la
    sección "Combinar operaciones: pipeline funcional" del PDF.
    """
    totales = map(total_item, carrito)
    return round(reduce(operator.add, totales, 0.0), 2)


def agregar_al_carrito(
    carrito: tuple[ItemCarrito, ...], producto: Producto, cantidad: int
) -> tuple[ItemCarrito, ...]:
    """Devuelve un carrito NUEVO (inmutabilidad, 2.1 / 2.2): nunca se muta
    la tupla recibida, tal como 'numeros + (4,)' en el ejemplo de tuplas.
    """
    existente = next((i for i in carrito if i.barcode == producto.barcode), None)

    if existente is None:
        nuevo_item = ItemCarrito(producto.barcode, producto.name, producto.price, cantidad)
        return (nuevo_item,) + carrito  # el más nuevo queda primero, como en el Delphi

    resto = tuple(filter(lambda i: i.barcode != producto.barcode, carrito))
    actualizado = existente._replace(qty=existente.qty + cantidad)
    return (actualizado,) + resto


def quitar_del_carrito(carrito: tuple[ItemCarrito, ...], barcode: str) -> tuple[ItemCarrito, ...]:
    """FILTER: nuevo carrito sin el ítem indicado."""
    return tuple(filter(lambda i: i.barcode != barcode, carrito))


def actualizar_cantidad(
    carrito: tuple[ItemCarrito, ...], barcode: str, nueva_cantidad: int
) -> tuple[ItemCarrito, ...]:
    """MAP: reconstruye el carrito cambiando solo la cantidad de una fila."""
    transformar = lambda i: i._replace(qty=nueva_cantidad) if i.barcode == barcode else i
    return tuple(map(transformar, carrito))


# ---------------------------------------------------------------------------
# 2.6 Recursividad y árboles: catálogo agrupado por categoría
# ---------------------------------------------------------------------------

def construir_arbol_categorias(productos: tuple[Producto, ...]) -> dict:
    """Construye un árbol { categoria: { "productos": [...], "subtotal": x } }
    usando comprensiones en vez de ciclos con acumuladores manuales.
    """
    categorias = sorted({p.category for p in productos})
    return {
        cat: {
            "productos": tuple(p for p in productos if p.category == cat),
            "subtotal": reduce(
                operator.add, (p.price * p.stock for p in productos if p.category == cat), 0.0
            ),
        }
        for cat in categorias
    }


def valor_total_inventario(arbol: dict) -> float:
    """Recursividad (2.6): recorre el árbol de categorías y suma subtotales.

    Un árbol se procesa muy bien con recursividad: caso base = árbol vacío.
    """
    claves = list(arbol.keys())
    if not claves:
        return 0.0
    primera, *resto = claves
    subtotal_actual = arbol[primera]["subtotal"]
    resto_arbol = {k: arbol[k] for k in resto}
    return subtotal_actual + valor_total_inventario(resto_arbol)


def factorial(n: int) -> int:
    """Recursividad clásica (2.6), usada para calcular combinaciones de
    promociones "lleva N, paga N-1" en el reporte de sugerencias.
    """
    if n <= 1:
        return 1
    return n * factorial(n - 1)


# ---------------------------------------------------------------------------
# 2.7 Evaluación perezosa: generadores sobre el historial de ventas
# ---------------------------------------------------------------------------

def flujo_detalles(ventas: tuple[Venta, ...]):
    """Generador: aplana (venta, item) sin construir una lista intermedia.

    Equivalente perezoso de un doble for tradicional.
    """
    for venta in ventas:
        for item in venta.items:
            yield venta, item


def resumen_por_producto(ventas: tuple[Venta, ...]) -> dict:
    """REDUCE clásico: recorre el flujo de (venta, item) y acumula un
    diccionario {producto: {"cantidad": x, "importe": y}} sin usar
    variables mutables sueltas -> todo pasa por un solo 'reduce'.
    """

    def acumular(acc: dict, par):
        _venta, item = par
        actual = acc.get(item.name, {"cantidad": 0, "importe": 0.0})
        nuevo = {
            "cantidad": actual["cantidad"] + item.qty,
            "importe": round(actual["importe"] + total_item(item), 2),
        }
        return {**acc, item.name: nuevo}

    return reduce(acumular, flujo_detalles(ventas), {})


def reporte_ventas(
    ventas: tuple[Venta, ...],
    desde: str | None = None,
    hasta: str | None = None,
) -> dict:
    """Pipeline completo: FILTER por fecha -> MAP a totales -> REDUCE a un
    resumen. Es el "Analizador funcional de datos de ventas" que propone
    el PDF del profe, aplicado al historial real de la caja.
    """
    en_rango = lambda v: (desde is None or v.fecha >= desde) and (hasta is None or v.fecha <= hasta)
    ventas_filtradas = tuple(filter(en_rango, ventas))

    totales = tuple(map(lambda v: v.total, ventas_filtradas))
    total_periodo = reduce(operator.add, totales, 0.0)
    ticket_promedio = round(total_periodo / len(ventas_filtradas), 2) if ventas_filtradas else 0.0

    return {
        "num_ventas": len(ventas_filtradas),
        "total_periodo": round(total_periodo, 2),
        "ticket_promedio": ticket_promedio,
        "por_producto": resumen_por_producto(ventas_filtradas),
        "top_producto": (
            max(resumen_por_producto(ventas_filtradas).items(), key=lambda kv: kv[1]["importe"])[0]
            if ventas_filtradas
            else "—"
        ),
    }
