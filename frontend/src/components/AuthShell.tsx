import type { ReactNode } from "react";
import { useColors, useStyles } from "../styles/ui";

/** Centered, themed container for the login / register screens. */
export default function AuthShell({ children }: { children: ReactNode }) {
  const c = useColors();
  const { cardStyle } = useStyles();
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        background: c.pageBg,
      }}
    >
      <div
        style={{
          ...cardStyle,
          width: "100%",
          maxWidth: 400,
          padding: "32px 28px",
          background: c.cardBg,
        }}
      >
        {children}
      </div>
    </div>
  );
}
