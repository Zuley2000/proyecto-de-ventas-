# Sistema de Ventas — versión Python (Programación Funcional, Unidad 2)

Conversión a Python de tu proyecto original en Delphi/FMX + PostgreSQL
(`Sistemas_de_ventas`: Login, Venta, Inventario, Movimiento, NuevoProducto).
Aplica los conceptos de la Unidad 2 (funciones puras, inmutabilidad,
lambda, map/filter/reduce, recursividad/árboles, generadores) y tiene
interfaz gráfica (Tkinter).

## Cómo ejecutarlo

Requiere Python 3.10+ con Tkinter (viene incluido en la instalación normal
de Python en Windows/Mac; en Linux a veces hay que instalar `python3-tk`).

```bash
python3 app.py
```

Usuario de prueba ya cargado: **dia / 1234**. La primera vez que corres el
programa se crea automáticamente `ventas.db` (SQLite) con productos de
ejemplo — no necesitas PostgreSQL ni FireDAC.

## Estructura

- **core.py** — todo lo funcional y puro: sin base de datos, sin interfaz,
  sin efectos secundarios. Aquí está el pipeline `filtrar → transformar →
  agregar` con `map`/`filter`/`reduce`, el carrito inmutable, el árbol de
  categorías con recursión y los generadores (`yield`).
- **db.py** — reemplaza a `uDMConexion.pas`: guarda y lee de SQLite.
- **app.py** — reemplaza a `uLogin/uVenta/uInventario/uMovimiento/uNuevoProducto.pas`:
  dibuja las pantallas y llama a `core.py`/`db.py`. En la pestaña **Venta**
  se ve el catálogo completo (igual que en Inventario) — tocar dos veces un
  producto lo agrega al carrito, y el buscador de arriba filtra ese catálogo
  en vivo además de servir para agregar por código/cantidad ("3xagua").
- **scanner.py** — abre la cámara y decodifica un código de barras para
  llenar el campo "Código de barras" al dar de alta un producto nuevo.

## Escanear código de barras

El botón "📷 Escanear" del formulario de "Nuevo producto" necesita una de
estas dos librerías (no vienen incluidas por defecto):

```bash
pip install opencv-contrib-python      # opción recomendada, todo en uno
# o, si esa no funciona en tu dispositivo:
pip install opencv-python pyzbar
```

En Android (Pydroid 3 u otra app similar) además hay que darle permiso de
**Cámara** a la app desde Ajustes → Apps. Si las librerías no están
instaladas o la cámara no está disponible, el botón muestra un mensaje
explicando qué falta — el resto de la app sigue funcionando normal, no se
puede escanear pero sí escribir el código a mano.

## Dónde está cada concepto de la Unidad 2

| Concepto de la Unidad 2 | Dónde está en el código |
|---|---|
| Función pura | `total_item`, `parsear_busqueda`, `total_carrito` |
| Inmutabilidad | `Producto`, `ItemCarrito`, `Venta` (namedtuples); el carrito nunca se muta, siempre se regresa uno nuevo |
| Funciones como valores / orden superior | `aplicar()`, `pipeline()` |
| lambda | en casi todos los `filter`/`map`/`reduce` de `core.py` |
| Operadores como funciones | `operator.add`, `operator.gt`, `operator.ge` |
| Predicados + `filter` | `buscar_productos`, `es_precio_valido` |
| `map` + `filter` + `reduce` combinados | `total_carrito`, `reporte_ventas` |
| Comprensiones de listas/diccionarios | `construir_arbol_categorias` |
| Recursividad | `valor_total_inventario`, `factorial` |
| Árboles | `construir_arbol_categorias` (categoría → productos) |
| Evaluación perezosa / generadores (`yield`) | `generar_folios`, `productos_con_stock_bajo`, `flujo_detalles` |

## Diferencias frente al proyecto original

- PostgreSQL/FireDAC → SQLite (sin servidor, un solo archivo `ventas.db`).
- El "Libro Mayor de Inventario" (vista SQL) se reemplaza por
  `construir_arbol_categorias` + `valor_total_inventario` en Python puro.
- El procedimiento `sp_registrar_movimiento_inventario` se reemplaza por
  `db.registrar_movimiento`.
- Las notificaciones push/SMS de recuperación de contraseña del login no
  se incluyeron (no aplican fuera de un proyecto móvil).
