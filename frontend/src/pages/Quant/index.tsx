import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuthStore } from "../../store/authStore";
import QuantPageHeader from "./QuantPageHeader";
import QuantWorkspaceSwitcher from "./QuantWorkspaceSwitcher";
import { parseQuantStockCodes } from "./quantUrlState";
import { useQuantRunController } from "./useQuantRunController";
import "./quant.css";

export default function QuantPage() {
  const [searchParams] = useSearchParams();
  const isAdmin = Boolean(useAuthStore((state) => state.user?.is_admin));
  const initialCodes = useMemo(() => parseQuantStockCodes(searchParams), [searchParams]);
  const runController = useQuantRunController();

  return (
    <div className="quant-page">
      <QuantPageHeader />
      <QuantWorkspaceSwitcher
        initialCodes={initialCodes}
        isAdmin={isAdmin}
        runController={runController}
      />
    </div>
  );
}
