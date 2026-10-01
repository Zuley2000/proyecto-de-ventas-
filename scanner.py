# -*- coding: utf-8 -*-
"""
scanner.py
==========
Escaneo de códigos de barras (EAN-13, UPC, etc.) usando la cámara del
dispositivo. Es un módulo aparte porque, igual que db.py, tiene efectos
secundarios (abre la cámara) — no toca core.py ni app.py directamente.

Requiere una de estas dos opciones instaladas:

    pip install opencv-contrib-python
    # (trae el detector de códigos de barras integrado, sin dependencias
    #  externas de sistema — es la opción recomendada)

    pip install opencv-python pyzbar
    # (alternativa; pyzbar necesita además la librería nativa libzbar)

En Android, si usas Pydroid 3 u otra app similar, recuerda darle permiso
de Cámara a la aplicación en Ajustes → Apps → (tu app) → Permisos.
"""

from __future__ import annotations


def escanear_codigo_barras() -> str | None:
    """Abre una ventana con la vista de la cámara y regresa el texto del
    primer código de barras detectado, o None si el usuario cancela
    (tecla ESC) o no se detecta nada al cerrar la cámara.
    """
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "No está instalado OpenCV. Instálalo con:\n"
            "pip install opencv-contrib-python"
        ) from exc

    detector = None
    metodo = None
    if hasattr(cv2, "barcode") and hasattr(cv2.barcode, "BarcodeDetector"):
        detector = cv2.barcode.BarcodeDetector()
        metodo = "opencv"
    else:
        try:
            from pyzbar.pyzbar import decode as zbar_decode
        except ImportError as exc:
            raise RuntimeError(
                "Tu versión de OpenCV no trae detector de códigos de barras "
                "(cv2.barcode). Instala 'opencv-contrib-python' o, en su "
                "defecto, 'pyzbar' para poder escanear."
            ) from exc
        metodo = "pyzbar"

    camara = cv2.VideoCapture(0)
    if not camara.isOpened():
        raise RuntimeError(
            "No se pudo abrir la cámara. Revisa que la app tenga permiso "
            "de cámara y que ninguna otra aplicación la esté usando."
        )

    codigo_encontrado: str | None = None
    try:
        while True:
            ok, frame = camara.read()
            if not ok:
                break

            if metodo == "opencv":
                ok_det, textos, _puntos, _recta = detector.detectAndDecode(frame)
                if ok_det:
                    textos_validos = [t for t in textos if t]
                    if textos_validos:
                        codigo_encontrado = textos_validos[0]
            else:
                resultados = zbar_decode(frame)
                if resultados:
                    codigo_encontrado = resultados[0].data.decode("utf-8")

            cv2.putText(
                frame, "Apunta al codigo de barras  |  ESC para cancelar",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2,
            )
            cv2.imshow("Escanear codigo de barras", frame)

            tecla = cv2.waitKey(1) & 0xFF
            if codigo_encontrado is not None or tecla == 27:  # ESC
                break
    finally:
        camara.release()
        cv2.destroyAllWindows()

    return codigo_encontrado
