import { useColors } from "../../../styles/ui";

export function CategoryChip({
  label,
  active,
  colors,
  onClick,
}: {
  label: string;
  active: boolean;
  colors: ReturnType<typeof useColors>;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="atlas-category-chip"
      onClick={onClick}
      style={{
        border: `1px solid ${active ? colors.primary : colors.border}`,
        background: active ? `${colors.primary}1f` : "transparent",
        color: active ? colors.primary : colors.textSecondary,
        borderRadius: 999,
        padding: "3px 14px",
        fontSize: "var(--c-font-md)",
        cursor: "pointer",
        transition: "all 0.15s ease",
      }}
    >
      {label}
    </button>
  );
}
