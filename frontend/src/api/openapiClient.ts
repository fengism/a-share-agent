import {
  apiDelete,
  apiGet,
  apiPost,
  apiPut,
  type ApiQueryParams,
  type ApiRequestOptions,
} from "./client";
import type { paths } from "./generated/schema";
import type { paths as requestPaths } from "./generated/request-schema";

type HttpMethod = "get" | "post" | "put" | "delete";
type Operation<Path extends keyof paths, Method extends HttpMethod> =
  Method extends keyof paths[Path] ? NonNullable<paths[Path][Method]> : never;
type RequestOperation<Path extends keyof requestPaths, Method extends HttpMethod> =
  Method extends keyof requestPaths[Path] ? NonNullable<requestPaths[Path][Method]> : never;

export type OpenApiPath<Method extends HttpMethod> = {
  [Path in keyof paths]: Operation<Path, Method> extends never ? never : Path;
}[keyof paths] & string;

type OperationParameters<OperationType> = OperationType extends {
  parameters: infer Parameters;
} ? Parameters : never;

type ParameterGroup<OperationType, Group extends string> =
  OperationParameters<OperationType> extends { [Key in Group]?: infer Value }
    ? Exclude<Value, undefined>
    : never;

type ParameterArgument<OperationType, Group extends "path" | "query"> =
  [ParameterGroup<OperationType, Group>] extends [never]
    ? Record<never, never>
    : OperationParameters<OperationType> extends Record<Group, unknown>
      ? { [Key in Group]: ParameterGroup<OperationType, Group> }
      : { [Key in Group]?: ParameterGroup<OperationType, Group> };

export type OpenApiPathParameters<
  Path extends keyof paths,
  Method extends HttpMethod,
> = ParameterGroup<Operation<Path, Method>, "path">;

export type OpenApiQuery<
  Path extends keyof paths,
  Method extends HttpMethod,
> = ParameterGroup<Operation<Path, Method>, "query">;

export type OpenApiRequestBody<
  Path extends keyof paths,
  Method extends HttpMethod,
> = RequestOperation<Path, Method> extends { requestBody?: infer RequestBody }
  ? Exclude<RequestBody, undefined> extends {
      content: { "application/json": infer Body };
    }
    ? Body
    : never
  : never;

type BodyArgument<OperationType> =
  [OpenApiRequestBodyForOperation<OperationType>] extends [never]
    ? Record<never, never>
    : OperationType extends { requestBody: unknown }
      ? { body: OpenApiRequestBodyInput<OperationType> }
      : { body?: OpenApiRequestBodyInput<OperationType> };

type OpenApiRequestBodyForOperation<OperationType> =
  OperationType extends { requestBody?: infer RequestBody }
    ? Exclude<RequestBody, undefined> extends {
        content: { "application/json": infer Body };
      }
      ? Body
      : never
    : never;

type OpenApiRequestBodyInput<OperationType> =
  OpenApiRequestBodyForOperation<OperationType>;

type JsonContent<Response> = Response extends {
  content: { "application/json": infer Content };
} ? Content : never;

type SuccessfulResponse<Responses> =
  | (200 extends keyof Responses ? Responses[200] : never)
  | (201 extends keyof Responses ? Responses[201] : never)
  | (202 extends keyof Responses ? Responses[202] : never)
  | (204 extends keyof Responses ? Responses[204] : never);

export type OpenApiResponse<
  Path extends keyof paths,
  Method extends HttpMethod,
> = Operation<Path, Method> extends { responses: infer Responses }
  ? JsonContent<SuccessfulResponse<Responses>>
  : never;

export type OpenApiRequestArgs<
  Path extends keyof paths,
  Method extends HttpMethod,
> = ParameterArgument<Operation<Path, Method>, "path">
  & ParameterArgument<Operation<Path, Method>, "query">
  & BodyArgument<RequestOperation<Path, Method>>
  & {
  options?: ApiRequestOptions;
};

type OpenApiRequestArguments<
  Path extends keyof paths,
  Method extends HttpMethod,
> = Record<never, never> extends OpenApiRequestArgs<Path, Method>
  ? [args?: OpenApiRequestArgs<Path, Method>]
  : [args: OpenApiRequestArgs<Path, Method>];

interface RuntimeRequestArgs {
  path?: Record<string, unknown>;
  query?: ApiQueryParams;
  body?: unknown;
  options?: ApiRequestOptions;
}

type Defined<Value> = Exclude<Value, null | undefined>;
type ModelFields<Value> = Defined<Value> extends readonly (infer Item)[]
  ? keyof Defined<Item>
  : keyof Defined<Value>;
type ResponseFields<Value> = Defined<Value> extends readonly (infer Item)[]
  ? keyof Defined<Item>
  : keyof Defined<Value>;
type ApiModelSource<Model, Response> = Exclude<ModelFields<Model>, ResponseFields<Response>> extends never
  ? Response
  : never;

export function asApiModel<Model>() {
  return <Response>(response: ApiModelSource<Model, Response>): Model => response as unknown as Model;
}

function resolvePath(template: string, parameters?: Record<string, unknown>): string {
  const resolved = template.replace(/\{([^}]+)\}/g, (_match, name: string) => {
    const value = parameters?.[name];
    if (value === undefined || value === null) {
      throw new Error(`缺少 OpenAPI 路径参数: ${name}`);
    }
    return encodeURIComponent(String(value));
  });
  return resolved.startsWith("/api/") ? resolved.slice(4) : resolved;
}

function requestPath<Path extends keyof paths>(
  path: Path,
  args: RuntimeRequestArgs,
): string {
  return resolvePath(path as string, args.path);
}

export function openApiGet<Path extends OpenApiPath<"get">>(
  path: Path,
  ...requestArguments: OpenApiRequestArguments<Path, "get">
): Promise<OpenApiResponse<Path, "get">> {
  const args = (requestArguments[0] ?? {}) as RuntimeRequestArgs;
  return apiGet<OpenApiResponse<Path, "get">>(
    requestPath(path, args),
    args.query,
    args.options,
  );
}

export function openApiPost<Path extends OpenApiPath<"post">>(
  path: Path,
  ...requestArguments: OpenApiRequestArguments<Path, "post">
): Promise<OpenApiResponse<Path, "post">> {
  const args = (requestArguments[0] ?? {}) as RuntimeRequestArgs;
  return apiPost<OpenApiResponse<Path, "post">>(
    requestPath(path, args),
    args.body,
    args.options,
  );
}

export function openApiPut<Path extends OpenApiPath<"put">>(
  path: Path,
  ...requestArguments: OpenApiRequestArguments<Path, "put">
): Promise<OpenApiResponse<Path, "put">> {
  const args = (requestArguments[0] ?? {}) as RuntimeRequestArgs;
  return apiPut<OpenApiResponse<Path, "put">>(
    requestPath(path, args),
    args.body,
    args.options,
  );
}

export function openApiDelete<Path extends OpenApiPath<"delete">>(
  path: Path,
  ...requestArguments: OpenApiRequestArguments<Path, "delete">
): Promise<OpenApiResponse<Path, "delete">> {
  const args = (requestArguments[0] ?? {}) as RuntimeRequestArgs;
  const resolvedPath = requestPath(path, args);
  if (args.options === undefined) {
    return apiDelete<OpenApiResponse<Path, "delete">>(resolvedPath);
  }
  return apiDelete<OpenApiResponse<Path, "delete">>(resolvedPath, args.options);
}
