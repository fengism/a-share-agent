import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useImportFile } from "./useImportFile";

class Reader {
  static LOADING = 1;
  static instances: Reader[] = [];
  readyState = 0;
  result: string | null = null;
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  constructor() { Reader.instances.push(this); }
  readAsDataURL() { this.readyState = 1; }
  abort() { this.readyState = 2; this.onabort?.(); }
  complete(content: string) { this.result = `data:text/csv;base64,${content}`; this.readyState = 2; this.onload?.(); }
}

describe("useImportFile", () => {
  beforeEach(() => { Reader.instances = []; vi.stubGlobal("FileReader", Reader); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("ignores out-of-order callbacks after replacing a file", () => {
    const error = vi.fn();
    const { result } = renderHook(() => useImportFile(error));
    act(() => { result.current.select(new File(["first"], "a.csv")); });
    const old = Reader.instances[0];
    act(() => { result.current.select(new File(["second"], "b.csv")); });
    expect(result.current.file).toBeNull();
    act(() => { Reader.instances[1].complete("bmV3"); old.complete("b2xk"); old.onerror?.(); });
    expect(result.current.file).toEqual({ filename: "b.csv", content_base64: "bmV3" });
    expect(error).not.toHaveBeenCalled();
  });

  it("clears pending reads and cannot resurrect a removed file", () => {
    const { result } = renderHook(() => useImportFile(vi.fn()));
    act(() => { result.current.select(new File(["data"], "a.csv")); result.current.clear(); });
    act(() => { Reader.instances[0].complete("b2xk"); });
    expect(result.current.file).toBeNull();
    expect(result.current.selected).toBeNull();
    expect(result.current.reading).toBe(false);
  });

  it("invalidates ready data on failure and invalid replacement", () => {
    const error = vi.fn();
    const { result } = renderHook(() => useImportFile(error));
    act(() => { result.current.select(new File(["data"], "a.csv")); Reader.instances[0].complete("b2xk"); });
    act(() => { result.current.select(new File(["data"], "bad.txt")); });
    expect(result.current.file).toBeNull();
    act(() => { result.current.select(new File(["data"], "b.csv")); Reader.instances[1].onerror?.(); });
    expect(result.current.selected).toBeNull();
    expect(result.current.reading).toBe(false);
    expect(error).toHaveBeenCalledTimes(2);
  });

  it("rejects empty or oversized files and aborts on unmount", () => {
    const error = vi.fn();
    const { result, unmount } = renderHook(() => useImportFile(error));
    act(() => { result.current.select(new File([], "empty.csv")); });
    const big = new File(["data"], "big.csv");
    Object.defineProperty(big, "size", { value: 50 * 1024 * 1024 + 1 });
    act(() => { result.current.select(big); });
    expect(Reader.instances).toHaveLength(0);
    act(() => { result.current.select(new File(["data"], "ok.csv")); });
    unmount();
    expect(Reader.instances[0].readyState).toBe(2);
    expect(error).toHaveBeenCalledTimes(2);
  });
});
