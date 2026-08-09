import { useCallback } from "react";
import { message } from "antd";
import { useUpdateConfig } from "../../api/queries";
import type { ConfigUpdate } from "../../types/settings";

export function useConfigSectionSave() {
  const { mutate, isPending } = useUpdateConfig();
  const save = useCallback((patch: ConfigUpdate, successMessage: string, afterSuccess?: () => void) => {
    mutate(patch, {
      onSuccess: () => {
        afterSuccess?.();
        message.success(successMessage);
      },
      onError: (error: Error) => message.error(`保存失败: ${error.message}`),
    });
  }, [mutate]);

  return { save, isSaving: isPending };
}
