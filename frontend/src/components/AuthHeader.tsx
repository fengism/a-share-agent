import type { ReactNode } from "react";
import { LineChartOutlined } from "@ant-design/icons";

interface AuthHeaderProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
}

export default function AuthHeader({ title, description, icon }: AuthHeaderProps) {
  return (
    <header className="auth-header">
      <div className="auth-header__logo" aria-hidden="true">
        {icon ?? <LineChartOutlined />}
      </div>
      <h1>{title}</h1>
      {description && <div className="auth-header__description">{description}</div>}
    </header>
  );
}
