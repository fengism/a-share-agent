import { useCallback, useEffect, useRef, useState } from "react";

const MAX_FILE_SIZE = 50 * 1024 * 1024;

/** 文件被替换/移除/关闭时，过期的 FileReader 回调不得恢复旧内容。 */
export function useImportFile(onError: (message: string) => void) {
  const [file, setFile] = useState<{ filename: string; content_base64: string } | null>(null);
  const [selected, setSelected] = useState<{ uid: string; name: string; size: number } | null>(null);
  const [reading, setReading] = useState(false);
  const reader = useRef<FileReader | null>(null);
  const generation = useRef(0);

  const invalidate = useCallback(() => {
    generation.current += 1;
    const pending = reader.current;
    reader.current = null;
    if (pending?.readyState === FileReader.LOADING) pending.abort();
  }, []);

  const clear = useCallback(() => {
    invalidate();
    setFile(null);
    setSelected(null);
    setReading(false);
  }, [invalidate]);

  useEffect(() => invalidate, [invalidate]);

  const select = (next: File): boolean => {
    clear();
    if (!/\.(csv|xlsx|xls)$/i.test(next.name)) {
      onError("请选择 CSV 或 Excel (.xlsx/.xls) 文件");
      return false;
    }
    if (next.size > MAX_FILE_SIZE || next.size === 0) {
      onError(next.size === 0 ? "文件不能为空" : "文件不能超过 50 MiB");
      return false;
    }
    const version = generation.current;
    const pending = new FileReader();
    reader.current = pending;
    setSelected({ uid: String(version), name: next.name, size: next.size });
    setReading(true);
    const fail = () => {
      if (version !== generation.current) return;
      clear();
      onError("读取文件失败，请重新选择");
    };
    pending.onload = () => {
      if (version !== generation.current) return;
      const result = pending.result;
      const separator = typeof result === "string" ? result.indexOf(",") : -1;
      if (separator < 0 || typeof result !== "string" || !result.slice(separator + 1)) {
        fail();
        return;
      }
      reader.current = null;
      setFile({ filename: next.name, content_base64: result.slice(separator + 1) });
      setReading(false);
    };
    pending.onerror = fail;
    pending.onabort = fail;
    try {
      pending.readAsDataURL(next);
    } catch {
      fail();
    }
    return true;
  };

  return { file, selected, reading, select, clear };
}
