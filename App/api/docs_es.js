// Traduce al castellano los textos fijos de Swagger UI (no trae idiomas).
// Solo reemplaza textos completos que coinciden exactamente, y nunca dentro
// de bloques de código, para no tocar las respuestas de la API.
(function () {
  const TEXTS = {
    "Try it out": "Probar",
    "Cancel": "Cancelar",
    "Execute": "Ejecutar",
    "Clear": "Limpiar",
    "Parameters": "Parámetros",
    "No parameters": "Sin parámetros",
    "Name": "Nombre",
    "Description": "Descripción",
    "Request body": "Cuerpo del pedido",
    "required": "obligatorio",
    "Responses": "Respuestas",
    "Response": "Respuesta",
    "Code": "Código",
    "Details": "Detalle",
    "Links": "Enlaces",
    "No links": "Sin enlaces",
    "Media type": "Tipo de contenido",
    // "Controls <code>Accept</code> header." viene en tres partes.
    "Controls": "Define el encabezado",
    "header.": "",
    "Example Value": "Ejemplo",
    "Schema": "Esquema",
    "Server response": "Respuesta del servidor",
    "Response body": "Cuerpo de la respuesta",
    "Response headers": "Encabezados de la respuesta",
    "Request URL": "URL del pedido",
    "Request duration": "Duración del pedido",
    "Download": "Descargar",
    "Undocumented": "Sin documentar",
    "Send empty value": "Enviar vacío",
    "Failed to fetch.": "No se pudo conectar.",
    "Possible Reasons:": "Posibles causas:",
  };
  const SKIP = "pre, code, textarea, .microlight, .highlight-code";

  function translate(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.nodeValue.trim();
      const spanish = Object.hasOwn(TEXTS, text) ? TEXTS[text] : undefined;
      if (spanish !== undefined && !node.parentElement.closest(SKIP)) {
        node.nodeValue = node.nodeValue.replace(text, spanish);
      }
    }
  }

  const container = document.getElementById("swagger-ui");
  new MutationObserver(() => translate(container)).observe(container, {
    childList: true,
    subtree: true,
    characterData: true,
  });
})();
