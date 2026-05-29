import { darkColors } from "../../../styles/ui";

export function BlinkingCursor() {
  return (
    <span
      style={{
        display: "inline-block",
        width: 2,
        height: 14,
        background: darkColors.primary,
        marginLeft: 2,
        verticalAlign: "text-bottom",
        animation: "blink 1s step-end infinite",
      }}
    />
  );
}
