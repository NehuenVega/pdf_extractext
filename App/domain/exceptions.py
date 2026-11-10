"""Errores propios de la aplicación.

Los servicios no conocen HTTP: lanzan estas excepciones y la capa de API
(App/api/errors.py) las traduce al código de estado que corresponde.
"""


class PdfError(Exception):
    """Error al procesar el PDF recibido."""


class InvalidPdfError(PdfError):
    """El archivo no es un PDF (400)."""


class FileTooLargeError(PdfError):
    """El archivo supera el tamaño máximo permitido (413)."""


class UnreadablePdfError(PdfError):
    """Es un PDF, pero está dañado o protegido con contraseña (422)."""
