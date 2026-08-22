import type { CSSProperties } from "react";
import type { ConfigUpdate } from "../../types/settings";

export interface ConfigSectionProps {
  form: ConfigUpdate;
  onChange: (patch: ConfigUpdate) => void;
  isSaving: boolean;
  sectionTitleStyle: CSSProperties;
}
