"""Ajuste do Swagger para mostrar só os erros do contrato (PRD, seção 5.6)."""

import json
from typing import Any

from fastapi import FastAPI

FASTAPI_ERROR_SCHEMAS = ("HTTPValidationError", "ValidationError")


def use_contract_errors(app: FastAPI) -> None:
    """Remove do OpenAPI o 422 automático do FastAPI, no formato {"detail": ...}.

    A API responde todo erro como {"error": {"code", "message"}}; o 422 no
    formato do contrato é declarado nas rotas que recebem corpo.
    """
    generate = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = generate()
        for path in schema["paths"].values():
            for operation in path.values():
                responses = operation.get("responses", {})
                if "HTTPValidationError" in json.dumps(responses.get("422", {})):
                    del responses["422"]
        for name in FASTAPI_ERROR_SCHEMAS:
            schema["components"]["schemas"].pop(name, None)
        return schema

    app.openapi = openapi
