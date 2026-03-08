"""Agent service: chat loop with LLM proxy, tools from tools_api OpenAPI, execute via HTTP."""

from collections.abc import Sequence
from dataclasses import dataclass

from openai.types.chat import ChatCompletionFunctionToolParam
from openai.types.shared_params import FunctionDefinition
from openapi_pydantic import (
    DataType,
    OpenAPI,
    Parameter,
    PathItem,
    Reference,
    RequestBody,
    Schema,
)
from openapi_pydantic.v3.v3_1.operation import Operation
from openapi_pydantic.v3.v3_1.parameter import ParameterLocation

from .path_method_ops import PathMethodOperations

# Media type for JSON request/response bodies (OpenAPI content key).
APPLICATION_JSON = "application/json"


@dataclass(frozen=True)
class SchemaProp:
    key: str
    schema: Schema
    required: bool


class OpenAPISpecParser:
    def __init__(self, path_method_operations: PathMethodOperations) -> None:
        self._path_method_ops = path_method_operations
        self._default_schema = Schema(type=DataType.STRING, enum=None)

    def parse_api_spec_as_tools(
        self, openapi_spec: OpenAPI
    ) -> Sequence[ChatCompletionFunctionToolParam]:
        """
        Convert OpenAPI paths to OpenAI-format tool definitions.
        Uses operationId as function name, summary as description, path/query/body as parameters.
        """
        tools: list[ChatCompletionFunctionToolParam] = []
        paths = openapi_spec.paths or {}
        for _, path_item in paths.items():
            tools += self._parse_path_item(path_item)
        return tools

    def _parse_path_item(self, path_item: PathItem) -> list[ChatCompletionFunctionToolParam]:
        tools: list[ChatCompletionFunctionToolParam] = []
        for method in self._path_method_ops.supported_methods():
            op = self._path_method_ops.get_path_method_operation(path_item, method)
            if op is None or not op.operationId:
                continue
            desc = op.summary or op.description or op.operationId
            parameters_schema = self._parse_function_params(op)
            params_dict = parameters_schema.model_dump(mode="json", by_alias=True)
            tools.append(
                ChatCompletionFunctionToolParam(
                    type="function",
                    function=FunctionDefinition(
                        name=op.operationId,
                        description=desc,
                        parameters=params_dict,
                    ),
                )
            )
        return tools

    def _parse_function_params(self, op: Operation) -> Schema:
        props: list[SchemaProp] = []
        for param in op.parameters or []:
            if isinstance(param, Reference):
                continue
            props.append(self._parse_parameter(param))
        if op.requestBody and not isinstance(op.requestBody, Reference):
            props.extend(self._parse_body(op.requestBody))
        return Schema(
            type=DataType.OBJECT,
            properties={p.key: p.schema for p in props},
            required=[p.key for p in props if p.required],
            enum=None,
        )

    def _parse_parameter(self, param: Parameter) -> SchemaProp:
        required = param.required or param.param_in == ParameterLocation.PATH
        if param.param_schema and not isinstance(param.param_schema, Reference):
            return SchemaProp(key=param.name, schema=param.param_schema, required=required)

        return SchemaProp(key=param.name, schema=self._default_schema, required=required)

    def _parse_body(self, request_body: RequestBody) -> Sequence[SchemaProp]:
        """Return the Schema for application/json content, or None if absent or a Reference."""
        content = request_body.content or {}
        mt = content.get(APPLICATION_JSON)
        schema_props: list[SchemaProp] = []
        if not mt or not mt.media_type_schema or isinstance(mt.media_type_schema, Reference):
            return schema_props

        media_type_schema = mt.media_type_schema
        if not media_type_schema or not media_type_schema.properties:
            return schema_props

        required = media_type_schema.required or []
        for k, v in media_type_schema.properties.items():
            if not v or isinstance(v, Reference):
                continue
            schema_props.append(SchemaProp(key=k, schema=v, required=k in required))
        return schema_props
