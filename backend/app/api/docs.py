from __future__ import annotations

from flask import Blueprint, Response, current_app, send_from_directory

docs_bp = Blueprint("api_docs", __name__)


@docs_bp.get("/openapi.json")
def openapi_spec():
    return send_from_directory(current_app.root_path, "openapi.json", mimetype="application/json")


@docs_bp.get("/docs")
def swagger_ui():
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SemanticFit API Documentation</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({
      url: "/api/openapi.json",
      dom_id: "#swagger-ui",
      deepLinking: true,
      displayRequestDuration: true,
      persistAuthorization: true
    });
  </script>
</body>
</html>
"""
    return Response(html, mimetype="text/html")