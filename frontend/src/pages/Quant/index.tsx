import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useStyles } from "../../styles/ui";
import { useAuthStore } from "../../store/authStore";
import QuantPageHeader from "./QuantPageHeader";
import QuantWorkspaceSwitcher from "./QuantWorkspaceSwitcher";
import { parseQuantStockCodes } from "./quantUrlState";
import { useQuantRunController } from "./useQuantRunController";
import "./quant.css";

export default function QuantPage() {
  const [searchParams] = useSearchParams();
  const isAdmin = Boolean(useAuthStore((state) => state.user?.is_admin));
  const { pageContainerStyle } = useStyles();
  const initialCodes = useMemo(() => parseQuantStockCodes(searchParams), [searchParams]);
  const runController = useQuantRunController();

  return (
    <div className="quant-page" style={pageContainerStyle}>
      <QuantPageHeader />
      <QuantWorkspaceSwitcher
        initialCodes={initialCodes}
        isAdmin={isAdmin}
        runController={runController}
      />
    </div>
  );
}
