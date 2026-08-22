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
      size={240}
      closable={false}
      styles={{
        body: {
          padding: 0,
          display: "flex",
          flexDirection: "column",
          background: themes[themeKey].siderBg,
        },
        header: { display: "none" },
      }}
    >
      {children}
    </Drawer>
  );
}
