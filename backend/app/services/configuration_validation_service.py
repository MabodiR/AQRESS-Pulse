from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError

from app.core.errors import AppError

ROOT_KEYWORDS = {"type", "properties", "required", "title", "description", "additionalProperties"}
FIELD_KEYWORDS = {"type", "title", "description", "default", "minimum", "maximum", "enum"}
VALUE_TYPES = {"string", "integer", "number", "boolean"}


class ConfigurationValidationService:
    @classmethod
    def validate_schema(cls, schema: dict[str, Any]) -> None:
        try:
            Draft202012Validator.check_schema(schema)
            cls._validate_supported_subset(schema)
        except (SchemaError, ValueError) as exc:
            raise AppError(status_code=422, code="INVALID_CONFIGURATION_SCHEMA", message="The sensor configuration schema is invalid.", details={"reason": str(exc)}) from exc

    @classmethod
    def validate_configuration(cls, schema: dict[str, Any], configuration: dict[str, Any]) -> None:
        cls.validate_schema(schema)
        try:
            Draft202012Validator(schema).validate(configuration)
        except ValidationError as exc:
            raise AppError(status_code=422, code="INVALID_SENSOR_CONFIGURATION", message="The sensor configuration does not match its schema.", details={"path": list(exc.absolute_path), "reason": exc.message}) from exc

    @staticmethod
    def _validate_supported_subset(schema: dict[str, Any]) -> None:
        unsupported = set(schema) - ROOT_KEYWORDS
        if unsupported:
            raise ValueError(f"Unsupported root keywords: {', '.join(sorted(unsupported))}")
        if schema.get("type") != "object" or not isinstance(schema.get("properties"), dict):
            raise ValueError("The root schema must be an object with properties.")
        if schema.get("additionalProperties") is not False:
            raise ValueError("additionalProperties must be false.")
        properties = schema["properties"]
        required = schema.get("required", [])
        if not isinstance(required, list) or any(key not in properties for key in required):
            raise ValueError("required must contain only defined property names.")
        for key, field in properties.items():
            if not isinstance(field, dict):
                raise ValueError(f"Property {key} must be a schema object.")
            extras = set(field) - FIELD_KEYWORDS
            if extras:
                raise ValueError(f"Property {key} uses unsupported keywords: {', '.join(sorted(extras))}")
            if field.get("type") not in VALUE_TYPES:
                raise ValueError(f"Property {key} has an unsupported type.")
