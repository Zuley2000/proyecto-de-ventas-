# -*- coding: utf-8 -*-
"""
db.py
=====
Capa de datos (SQLite) — el único módulo con efectos secundarios (E/S).

Reemplaza a uDMConexion.pas (FireDAC + PostgreSQL). Aquí SOLO se guarda y
se lee; toda transformación de datos vive en core.py. Esto separa lo
imperativo (base de datos) de lo funcional (core.py), que es justo la idea
central de la Unidad 2: aislar las funciones puras del resto del programa.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import core

DB_PATH = Path(__file__).with_name("ventas.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'cajero',
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'General',
    selling_price REAL NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sales (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    sale_date TEXT NOT NULL,
    total REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed'
);

CREATE TABLE IF NOT EXISTS sale_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(sale_id),
    barcode TEXT NOT NULL,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    movement_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    movement_date TEXT NOT NULL
);
"""

SEED_USERS = [("dia", "1234", "Dia", "admin")]

SEED_PRODUCTS = [
    ("7501000000010", "Coca-Cola 600ml", "Bebidas", 18.0, 24),
    ("7501000000027", "Agua Ciel 1L", "Bebidas", 15.0, 30),
    ("7501000000034", "Sabritas 45g", "Botanas", 22.5, 4),
    ("7501000000041", "Doritos 62g", "Botanas", 24.0, 12),
    ("7501000000058", "Galletas Marías", "Panadería", 19.0, 2),
    ("7501000000065", "Pan Blanco", "Panadería", 32.0, 15),
    ("7501000000072", "Jabón Neutro", "Higiene", 14.5, 20),
    ("7501000000089", "Shampoo 400ml", "Higiene", 55.0, 8),
]


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def inicializar():
    """Crea el esquema y siembra datos de ejemplo si la base está vacía."""
    con = conectar()
    try:
        con.executescript(SCHEMA)
        if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO users (username, password, full_name, role) VALUES (?,?,?,?)",
                SEED_USERS,
            )
        if con.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            con.executemany(
                "INSERT INTO products (barcode, name, category, selling_price, stock_quantity) "
                "VALUES (?,?,?,?,?)",
                SEED_PRODUCTS,
            )
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Lecturas: siempre regresan datos "crudos" -> se convierten a los tipos
# inmutables de core.py justo al salir de aquí.
# ---------------------------------------------------------------------------

def obtener_productos() -> tuple[core.Producto, ...]:
    con = conectar()
    try:
        filas = con.execute(
            "SELECT product_id, barcode, name, selling_price, stock_quantity, category, is_active "
            "FROM products ORDER BY name"
        ).fetchall()
    finally:
        con.close()
    return tuple(
        core.Producto(f["product_id"], f["barcode"], f["name"], f["selling_price"],
                      f["stock_quantity"], f["category"], bool(f["is_active"]))
        for f in filas
    )


def validar_login(username: str, password: str):
    con = conectar()
    try:
        fila = con.execute(
            "SELECT username, full_name, role FROM users "
            "WHERE username = ? AND password = ? AND is_active = 1",
            (username, password),
        ).fetchone()
    finally:
        con.close()
    return dict(fila) if fila else None


def contar_ventas() -> int:
    """Cuántas ventas hay ya guardadas — se usa para arrancar el folio
    correlativo (FAC-000001, FAC-000002, ...) después de la última que
    exista, y no siempre desde 1 al reabrir el programa."""
    con = conectar()
    try:
        return con.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    finally:
        con.close()


def obtener_ventas() -> tuple[core.Venta, ...]:
    con = conectar()
    try:
        cabeceras = con.execute(
            "SELECT sale_id, invoice_number, username, sale_date, total FROM sales ORDER BY sale_date"
        ).fetchall()
        detalles = con.execute(
            "SELECT sale_id, barcode, name, quantity, unit_price FROM sale_details"
        ).fetchall()
    finally:
        con.close()

    por_venta = {}
    for d in detalles:
        por_venta.setdefault(d["sale_id"], []).append(
            core.ItemCarrito(d["barcode"], d["name"], d["unit_price"], d["quantity"])
        )

    return tuple(
        core.Venta(c["invoice_number"], c["sale_date"], c["username"],
                   tuple(por_venta.get(c["sale_id"], ())), c["total"])
        for c in cabeceras
    )


# ---------------------------------------------------------------------------
# Escrituras
# ---------------------------------------------------------------------------

def registrar_venta(folio: str, username: str, fecha: str, carrito: tuple[core.ItemCarrito, ...]):
    """Guarda la venta y descuenta stock, dentro de una sola transacción
    (igual que el StartTransaction / Commit / Rollback del Delphi original).
    """
    total = core.total_carrito(carrito)
    con = conectar()
    try:
        cur = con.execute(
            "INSERT INTO sales (invoice_number, username, sale_date, total) VALUES (?,?,?,?)",
            (folio, username, fecha, total),
        )
        sale_id = cur.lastrowid
        for item in carrito:
            con.execute(
                "INSERT INTO sale_details (sale_id, barcode, name, quantity, unit_price) "
                "VALUES (?,?,?,?,?)",
                (sale_id, item.barcode, item.name, item.qty, item.price),
            )
            con.execute(
                "UPDATE products SET stock_quantity = stock_quantity - ? WHERE barcode = ?",
                (item.qty, item.barcode),
            )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def registrar_movimiento(barcode: str, tipo: str, cantidad: int, fecha: str):
    """Equivalente a CALL sp_registrar_movimiento_inventario(...)."""
    signo = 1 if tipo in ("compra", "devolucion") else -1
    con = conectar()
    try:
        fila = con.execute("SELECT product_id FROM products WHERE barcode = ?", (barcode,)).fetchone()
        if fila is None:
            raise ValueError("El código de barras no existe en el catálogo.")
        con.execute(
            "INSERT INTO inventory_movements (product_id, movement_type, quantity, movement_date) "
            "VALUES (?,?,?,?)",
            (fila["product_id"], tipo, cantidad, fecha),
        )
        con.execute(
            "UPDATE products SET stock_quantity = stock_quantity + ? WHERE product_id = ?",
            (signo * cantidad, fila["product_id"]),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def agregar_producto(barcode: str, name: str, category: str, price: float, stock: int):
    con = conectar()
    try:
        con.execute(
            "INSERT INTO products (barcode, name, category, selling_price, stock_quantity) "
            "VALUES (?,?,?,?,?)",
            (barcode, name, category, price, stock),
        )
        con.commit()
    finally:
        con.close()


def eliminar_producto(barcode: str):
    con = conectar()
    try:
        fila = con.execute("SELECT product_id FROM products WHERE barcode = ?", (barcode,)).fetchone()
        if fila:
            con.execute("DELETE FROM inventory_movements WHERE product_id = ?", (fila["product_id"],))
            con.execute("DELETE FROM sale_details WHERE barcode = ?", (barcode,))
            con.execute("DELETE FROM products WHERE product_id = ?", (fila["product_id"],))
        con.commit()
    finally:
        con.close()
