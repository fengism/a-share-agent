import { useColors} from "../../../styles/ui";

export function BlinkingCursor() {
  const c = useColors();
  return (
    <span
      style={{
        display: "inline-block",
        width: 2,
        height: 14,
        background: c.primary,
        marginLeft: 2,
        verticalAlign: "text-bottom",
        animation: "blink 1s step-end infinite",
      }}
    />
  );
}
