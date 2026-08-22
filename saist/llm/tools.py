"""Provider-neutral tool definitions for LLM function calling.

Wraps a type-annotated, docstring-bearing callable into a provider-neutral
definition (name, description, JSON Schema parameters) that adapters can
translate into provider-specific formats. Supported argument types:

* primitives (``str``, ``int``, ``float``, ``bool``, ``None``)
* containers (``list``, ``set``, ``tuple``, ``dict``), ``Literal``,
  ``Optional``/``Union``, and ``Annotated[T, "description"]``
* ``enum.Enum`` subclasses and Pydantic models
"""

from __future__ import annotations

import enum
import inspect
import json
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel

__all__ = [
    "ToolArgument",
    "ToolDefinition",
    "Tool",
    "schema_for",
    "pydantic_schema",
    "strict_schema",
]

JsonSchema = dict[str, Any]

NONE = type(None)
_EMPTY = inspect.Signature.empty

PRIMITIVES: dict[type, str] = {
    bool: "boolean",  # Before int: bool is a subclass of int.
    int: "integer",
    float: "number",
    str: "string",
}

_SET_ORIGINS = frozenset({set, frozenset})
_ARRAY_ORIGINS = frozenset({list, set, frozenset})


# ---------------------------------------------------------------------------
# Annotation helpers
# ---------------------------------------------------------------------------


def _is_any(annotation: Any) -> bool:
    return annotation is Any or annotation is _EMPTY


def _is_union(annotation: Any) -> bool:
    return get_origin(annotation) in (Union, types.UnionType)


def _is_enum(annotation: Any) -> bool:
    return inspect.isclass(annotation) and issubclass(annotation, enum.Enum)


def _is_pydantic_model(annotation: Any) -> bool:
    return inspect.isclass(annotation) and issubclass(annotation, BaseModel)


def _unwrap_annotated(annotation: Any) -> tuple[Any, str | None]:
    """Return ``(type, description)``; the first string metadata item wins."""
    if get_origin(annotation) is Annotated:
        underlying, *metadata = get_args(annotation)
        description = next((m for m in metadata if isinstance(m, str)), None)
        return underlying, description
    return annotation, None


def _accepts_none(annotation: Any) -> bool:
    annotation, _ = _unwrap_annotated(annotation)
    if _is_any(annotation) or annotation in (None, NONE):
        return True
    if _is_union(annotation):
        return any(_accepts_none(arg) for arg in get_args(annotation))
    if get_origin(annotation) is Literal:
        return None in get_args(annotation)
    return False


def _primitive_type(value: Any) -> str:
    for python_type, json_type in PRIMITIVES.items():
        if isinstance(value, python_type):
            return json_type
    return "string"


def _type_hints(obj: Any) -> dict[str, Any]:
    try:
        return get_type_hints(obj, include_extras=True)
    except Exception:
        return {}


def _type_name(annotation: Any) -> str:
    return getattr(annotation, "__name__", None) or str(annotation)


# ---------------------------------------------------------------------------
# Schema generation
# ---------------------------------------------------------------------------


def schema_for(annotation: Any, *, description: str | None = None) -> JsonSchema:
    """Build a provider-neutral JSON Schema for a type annotation."""
    annotation, annotated_description = _unwrap_annotated(annotation)
    schema = _schema_for_type(annotation)
    if description or annotated_description:
        schema["description"] = description or annotated_description
    return schema


def _schema_for_type(annotation: Any) -> JsonSchema:
    if _is_any(annotation):
        return {}
    if annotation in (None, NONE):
        return {"type": "null"}

    if _is_union(annotation):
        variants: list[JsonSchema] = []
        for arg in get_args(annotation):
            variant = schema_for(arg)
            if variant not in variants:
                variants.append(variant)
        return variants[0] if len(variants) == 1 else {"anyOf": variants}

    origin = get_origin(annotation)
    if origin is Literal:
        values = [v.value if isinstance(v, enum.Enum) else v for v in get_args(annotation)]
        schema: JsonSchema = {"enum": values}
        kinds = {"null" if v is None else _primitive_type(v) for v in values}
        if len(kinds) == 1:
            schema["type"] = kinds.pop()
        return schema
    if origin in _ARRAY_ORIGINS:
        args = get_args(annotation)
        schema = {"type": "array", "items": schema_for(args[0] if args else Any)}
        if origin in _SET_ORIGINS:
            schema["uniqueItems"] = True
        return schema
    if origin is tuple:
        args = get_args(annotation)
        if not args or (len(args) == 2 and args[1] is Ellipsis):
            return {"type": "array", "items": schema_for(args[0] if args else Any)}
        return {
            "type": "array",
            "prefixItems": [schema_for(arg) for arg in args],
            "minItems": len(args),
            "maxItems": len(args),
        }
    if origin is dict:
        args = get_args(annotation)
        value_type = args[1] if len(args) == 2 else Any
        return {"type": "object", "additionalProperties": schema_for(value_type)}

    if annotation in PRIMITIVES:
        return {"type": PRIMITIVES[annotation]}
    if annotation in (list, set, frozenset, tuple):
        return {"type": "array", "items": {}}
    if annotation is dict:
        return {"type": "object"}

    if _is_enum(annotation):
        values = [member.value for member in annotation]
        schema = {"enum": values}
        kinds = {_primitive_type(v) for v in values}
        if len(kinds) == 1:
            schema["type"] = kinds.pop()
        return schema
    if _is_pydantic_model(annotation):
        return pydantic_schema(annotation)

    raise TypeError(f"Unsupported annotation for tool schema: {annotation!r}")


def pydantic_schema(cls: type[BaseModel]) -> JsonSchema:
    """Schema via Pydantic's own generator, with ``$ref``s inlined."""
    raw = cls.model_json_schema() if hasattr(cls, "model_json_schema") else cls.schema()
    return _inline_refs(dict(raw))


def _inline_refs(schema: JsonSchema) -> JsonSchema:
    definitions: dict[str, Any] = {
        **schema.pop("$defs", {}),
        **schema.pop("definitions", {}),
    }

    def resolve(node: Any, seen: frozenset[str]) -> Any:
        if isinstance(node, list):
            return [resolve(item, seen) for item in node]
        if not isinstance(node, dict):
            return node
        if isinstance(ref := node.get("$ref"), str):
            name = ref.rsplit("/", 1)[-1]
            if name in seen or name not in definitions:
                return {"type": "object"}  # Recursive or unknown reference.
            merged = {**definitions[name], **{k: v for k, v in node.items() if k != "$ref"}}
            return resolve(merged, seen | {name})
        return {key: resolve(value, seen) for key, value in node.items()}

    return resolve(schema, frozenset())


# ---------------------------------------------------------------------------
# Provider-neutral tool representation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolArgument:
    """Provider-neutral description of one callable argument."""

    name: str
    annotation: Any
    schema: JsonSchema
    required: bool
    default: Any = _EMPTY
    description: str | None = None

    @property
    def has_default(self) -> bool:
        return self.default is not _EMPTY


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Provider-neutral description of a callable tool."""

    name: str
    description: str
    arguments: list[ToolArgument]
    function: Callable[..., Any] = field(repr=False)
    return_annotation: Any = Any

    @property
    def args(self) -> dict[str, ToolArgument]:
        return {argument.name: argument for argument in self.arguments}


_ACCEPTED_KINDS = frozenset(
    {
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    }
)


class Tool:
    """Wrap a callable as a tool with a schema and validated invocation."""

    def __init__(
        self,
        fn: Callable[..., Any],
        *,
        override_description: str | None = None,
        override_name: str | None = None,
        override_types: list[Any] | None = None,
    ) -> None:
        self.fn = fn
        self.name = override_name or fn.__name__
        self.description = override_description or inspect.getdoc(fn) or ""

        signature = inspect.signature(fn)
        hints = _type_hints(fn)
        parameters = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind in _ACCEPTED_KINDS
        ]
        self._positional_only = tuple(
            parameter.name
            for parameter in parameters
            if parameter.kind is inspect.Parameter.POSITIONAL_ONLY
        )

        arguments = []
        for index, parameter in enumerate(parameters):
            if parameter.name.startswith("_"):
                continue
            if override_types is not None and index < len(override_types):
                annotation = override_types[index]
            else:
                annotation = hints.get(parameter.name, Any)
            _, description = _unwrap_annotated(annotation)
            arguments.append(
                ToolArgument(
                    name=parameter.name,
                    annotation=annotation,
                    schema=schema_for(annotation),
                    required=parameter.default is _EMPTY,
                    default=parameter.default,
                    description=description,
                )
            )

        self.definition = ToolDefinition(
            name=self.name,
            description=self.description,
            arguments=arguments,
            function=fn,
            return_annotation=hints.get("return", Any),
        )
        self.args = self.definition.args
        self.return_type = self.definition.return_annotation

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"

    # -- Invocation -----------------------------------------------------------

    async def call(self, input_data: str | dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Execute the wrapped function with validated, converted arguments.

        The wrapped function may be sync or async; async functions are
        awaited. Returns ``{"success": True, "result": ...}`` with the
        *native* result (use :meth:`serialize` before sending it back to a
        provider), or ``{"success": False, "error": ...}`` on failure.

        Keyword arguments may provide values for function parameters whose
        names begin with ``_``; these parameters are omitted from the schema.
        """
        try:
            result = await self._invoke({**self._arguments(input_data), **kwargs})
        except Exception as exc:
            return {"success": False, "error": f"{type(exc).__name__}: {exc}", "exception": exc}
        return {"success": True, "result": result}

    async def _invoke(self, kwargs: dict[str, Any]) -> Any:
        # Positional-only parameters cannot be passed as keywords.
        args = [kwargs.pop(name) for name in self._positional_only if name in kwargs]
        result = self.fn(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result

    def _arguments(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Tool arguments are not valid JSON: {exc}") from exc
        else:
            data = input_data
        if not isinstance(data, dict):
            raise TypeError("Tool arguments must be a JSON object")

        missing = [a.name for a in self.definition.arguments if a.required and a.name not in data]
        if missing:
            raise ValueError(f"Missing required argument(s): {', '.join(missing)}")

        kwargs: dict[str, Any] = {}
        for argument in self.definition.arguments:
            if argument.name not in data:
                continue
            try:
                kwargs[argument.name] = self._convert(data[argument.name], argument.annotation)
            except Exception as exc:
                raise ValueError(f"Invalid value for argument {argument.name!r}: {exc}") from exc
        return kwargs

    # -- Value conversion -------------------------------------------------------

    def _convert(self, value: Any, annotation: Any) -> Any:
        annotation, _ = _unwrap_annotated(annotation)

        if value is None:
            if _accepts_none(annotation):
                return None
            raise TypeError(f"null is not valid for {_type_name(annotation)}")
        if _is_any(annotation):
            return value
        if _is_union(annotation):
            return self._convert_union(value, annotation)

        origin = get_origin(annotation)
        if origin is Literal:
            return self._convert_literal(value, annotation)
        if origin in _ARRAY_ORIGINS or annotation in (list, set, frozenset):
            return self._convert_array(value, annotation, origin or annotation)
        if origin is tuple or annotation is tuple:
            return self._convert_tuple(value, annotation)
        if origin is dict or annotation is dict:
            if not isinstance(value, dict):
                raise TypeError(f"Expected an object, got {type(value).__name__}")
            args = get_args(annotation)
            value_type = args[1] if len(args) == 2 else Any
            return {key: self._convert(item, value_type) for key, item in value.items()}

        # Strict primitives: no cross-type coercion the model shouldn't rely on.
        if annotation is bool:
            if type(value) is not bool:
                raise TypeError(f"Expected a boolean, got {type(value).__name__}")
            return value
        if annotation is int:
            if type(value) is not int:
                raise TypeError(f"Expected an integer, got {type(value).__name__}")
            return value
        if annotation is float:
            if type(value) not in (int, float):
                raise TypeError(f"Expected a number, got {type(value).__name__}")
            return float(value)
        if annotation is str:
            if not isinstance(value, str):
                raise TypeError(f"Expected a string, got {type(value).__name__}")
            return value

        if _is_enum(annotation):
            if isinstance(value, annotation):
                return value
            try:
                return annotation(value)
            except ValueError:
                raise ValueError(f"{value!r} is not a valid {annotation.__name__}") from None
        if _is_pydantic_model(annotation):
            if isinstance(value, annotation):
                return value
            if hasattr(annotation, "model_validate"):
                return annotation.model_validate(value)
            return annotation.parse_obj(value)

        raise TypeError(f"Unsupported annotation: {annotation!r}")

    def _convert_union(self, value: Any, annotation: Any) -> Any:
        errors: list[str] = []
        for branch in get_args(annotation):
            if branch is NONE:
                continue
            try:
                return self._convert(value, branch)
            except Exception as exc:
                errors.append(f"{_type_name(branch)}: {exc}")
        raise TypeError(
            f"{value!r} did not match any variant of {_type_name(annotation)} "
            f"({'; '.join(errors)})"
        )

    def _convert_literal(self, value: Any, annotation: Any) -> Any:
        allowed = get_args(annotation)
        for candidate in allowed:
            if isinstance(candidate, enum.Enum):
                if value is candidate or value == candidate.value:
                    return candidate
            elif type(candidate) is type(value) and candidate == value:
                return candidate
        raise ValueError(f"{value!r} is not one of {allowed!r}")

    def _convert_array(self, value: Any, annotation: Any, origin: Any) -> Any:
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"Expected an array, got {type(value).__name__}")
        args = get_args(annotation)
        items = [self._convert(item, args[0] if args else Any) for item in value]
        if origin is frozenset:
            return frozenset(items)
        if origin is set:
            return set(items)
        return items

    def _convert_tuple(self, value: Any, annotation: Any) -> tuple[Any, ...]:
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"Expected an array, got {type(value).__name__}")
        args = get_args(annotation)
        if not args:
            return tuple(value)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(self._convert(item, args[0]) for item in value)
        if len(value) != len(args):
            raise ValueError(f"Expected exactly {len(args)} items, got {len(value)}")
        return tuple(self._convert(item, arg) for item, arg in zip(value, args))

    # -- Serialization ----------------------------------------------------------

    @staticmethod
    def serialize(value: Any) -> Any:
        """Convert a native result into JSON-compatible data for the model."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, enum.Enum):
            return Tool.serialize(value.value)
        if isinstance(value, BaseModel):
            if hasattr(value, "model_dump"):
                return value.model_dump(mode="json")
            return json.loads(value.json())  # Pydantic v1: JSON-safe round trip.
        if isinstance(value, dict):
            return {str(key): Tool.serialize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set, frozenset)):
            return [Tool.serialize(item) for item in value]
        return str(value)


# ---------------------------------------------------------------------------
# Provider adaptation helper (OpenAI strict mode)
# ---------------------------------------------------------------------------


def strict_schema(schema: Any) -> Any:
    """Normalize a schema for OpenAI strict mode (pure; input not mutated).

    Every property becomes required (previously optional ones are made
    nullable so the model can still opt out) and objects reject unknown keys.
    """
    if isinstance(schema, list):
        return [strict_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    result = {key: strict_schema(value) for key, value in schema.items()}

    if isinstance(result.get("properties"), dict):
        result.setdefault("type", "object")
        previously_required = set(result.get("required", ()))
        result["properties"] = {
            name: prop if name in previously_required else _allow_null(prop)
            for name, prop in result["properties"].items()
        }
        result["required"] = list(result["properties"])
        result.setdefault("additionalProperties", False)

    return result


def _allow_null(schema: JsonSchema) -> JsonSchema:
    if not schema:
        return schema  # The empty schema already permits null.
    result = dict(schema)
    if "enum" in result and None not in result["enum"]:
        result["enum"] = [*result["enum"], None]
    schema_type = result.get("type")
    if isinstance(schema_type, str):
        if schema_type != "null":
            result["type"] = [schema_type, "null"]
        return result
    if isinstance(schema_type, list):
        if "null" not in schema_type:
            result["type"] = [*schema_type, "null"]
        return result
    if isinstance(result.get("anyOf"), list):
        variants = result["anyOf"]
        if not any(isinstance(v, dict) and v.get("type") == "null" for v in variants):
            result["anyOf"] = [*variants, {"type": "null"}]
        return result
    return {"anyOf": [result, {"type": "null"}]}
