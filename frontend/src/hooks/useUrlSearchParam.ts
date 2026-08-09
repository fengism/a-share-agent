import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

interface UrlSearchParamOptions<T extends string> {
  allowedValues?: readonly T[];
  replace?: boolean;
}

export function resolveUrlSearchParam<T extends string>(
  rawValue: string | null,
  defaultValue: T,
  allowedValues?: readonly T[],
): T {
  if (rawValue === null) return defaultValue;
  if (allowedValues && !allowedValues.includes(rawValue as T)) return defaultValue;
  return rawValue as T;
}

export function updateUrlSearchParam(
  current: URLSearchParams,
  key: string,
  value: string,
  defaultValue: string,
): URLSearchParams {
  const next = new URLSearchParams(current);
  if (!value || value === defaultValue) next.delete(key);
  else next.set(key, value);
  return next;
}

export function useUrlSearchParam<T extends string = string>(
  key: string,
  defaultValue: NoInfer<T>,
  options: UrlSearchParamOptions<T> = {},
): [T, (value: string) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const value = resolveUrlSearchParam(searchParams.get(key), defaultValue, options.allowedValues);

  const setValue = useCallback((nextValue: string) => {
    setSearchParams(
      (current) => updateUrlSearchParam(current, key, nextValue, defaultValue),
      { replace: options.replace ?? false },
    );
  }, [defaultValue, key, options.replace, setSearchParams]);

  return [value, setValue];
}
