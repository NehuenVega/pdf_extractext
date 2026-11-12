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


class ServiceOverloadedError(Exception):
    """La réplica no puede aceptar más trabajo en este momento (503)."""


class QueueFullError(ServiceOverloadedError):
    """La cola de espera está llena: el pedido se rechaza al llegar."""


class QueueTimeoutError(ServiceOverloadedError):
    """El pedido esperó demasiado en la cola y ya no es útil procesarlo."""


class WorkerCrashedError(Exception):
    """Un proceso worker murió mientras procesaba un pedido (500)."""
