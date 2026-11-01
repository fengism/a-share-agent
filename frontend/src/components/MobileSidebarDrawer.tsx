import type { ReactNode } from "react";
import { Drawer } from "antd";
import { themes } from "../theme/themes";
import type { ThemeKey } from "../styles/ui";

interface MobileSidebarDrawerProps {
  open: boolean;
  onClose: () => void;
  themeKey: ThemeKey;
  children: ReactNode;
}

export default function MobileSidebarDrawer({
  open,
  onClose,
  themeKey,
  children,
}: MobileSidebarDrawerProps) {
  return (
    <Drawer
      placement="left"
      open={open}
      onClose={onClose}
      size={264}
      closable={false}
      styles={{
        body: {
          padding: 0,
          display: "flex",
          flexDirection: "column",
          background: themes[themeKey].siderBg,
          boxShadow: "6px 0 28px rgba(0, 0, 0, 0.4)",
          paddingTop: "env(safe-area-inset-top, 0px)",
        },
        mask: {
          backdropFilter: "blur(8px)",
          WebkitBackdropFilter: "blur(8px)",
          background: "rgba(0, 0, 0, 0.5)",
        },
        header: { display: "none" },
      }}
    >
      {children}
    </Drawer>
  );
}
