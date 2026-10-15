import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Modal, Select, Skeleton, Typography } from "antd";
import { apiGet } from "../../api/client";
import type { AnalysisResult } from "../../types/stock";
import ResearchFrameworkPanel from "./ResearchFrameworkPanel";

interface VersionItem {
  report_id: string;
  generated_at: string | null;
  overall_rating: number;
}

export default function AnalysisReportVersions({ analysis }: { analysis: AnalysisResult }) {
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [analysis.stock_code, analysis.analysis_date, analysis.report_id]);
  return <div className="pdf-hide" style={{ marginBottom: 12 }}>
    <Button onClick={() => setOpen(true)}>查看同日报告版本</Button>
    {open && <ReportVersionDialog analysis={analysis} onClose={() => setOpen(false)} />}
  </div>;
}

function ReportVersionDialog({ analysis, onClose }: { analysis: AnalysisResult; onClose: () => void }) {
  const [selected, setSelected] = useState("");
  const [page, setPage] = useState(0);
  const code = analysis.stock_code;
  const date = analysis.analysis_date.replace(/-/g, "");
  const root = `/analysis/${encodeURIComponent(code)}/versions/${encodeURIComponent(date)}`;
  const versions = useQuery({
    queryKey: ["analysisVersions", code, date, analysis.report_id, page],
    queryFn: ({ signal }) => apiGet<VersionItem[]>(root, { limit: 50, offset: page * 50 }, { signal }),
    enabled: true,
    staleTime: 0,
  });
  const snapshot = useQuery({
    queryKey: ["analysisVersion", code, date, selected],
    queryFn: ({ signal }) => apiGet<AnalysisResult>(`${root}/${encodeURIComponent(selected)}`, undefined, { signal }),
    enabled: Boolean(selected),
    staleTime: 0,
  });
  return <Modal title={`${code} · ${date} 报告版本（只读）`} open onCancel={onClose} footer={null} width="90%" destroyOnHidden>
      {versions.isError ? <Alert type="error" title="版本列表加载失败" action={<Button onClick={() => void versions.refetch()}>重试</Button>} /> :
        versions.isLoading ? <Skeleton active /> : <>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginBottom: 12 }}>
            <Select
              aria-label="报告版本"
              style={{ width: "100%", maxWidth: 360, minWidth: 0 }}
              placeholder="选择要查看的版本"
              value={selected || undefined}
              onChange={setSelected}
              options={(versions.data || []).map((item) => ({
                value: item.report_id,
                label: `${item.generated_at || "历史版本"} · ${item.report_id.slice(0, 8)} · ${item.overall_rating}/10`,
              }))}
            />
            <div style={{ display: "inline-flex", gap: 8 }}>
              <Button disabled={page === 0} onClick={() => { setPage(page - 1); setSelected(""); }}>上一页</Button>
              <Button disabled={(versions.data?.length || 0) < 50} onClick={() => { setPage(page + 1); setSelected(""); }}>下一页</Button>
            </div>
          </div>
          {!versions.data?.length && <Typography.Paragraph>暂无独立版本。旧报告会在下次重新分析前保留为历史版本。</Typography.Paragraph>}
        </>}
      {snapshot.isError && <Alert type="error" title="报告版本加载失败" action={<Button onClick={() => void snapshot.refetch()}>重试</Button>} />}
      {selected && snapshot.isLoading && <Skeleton active />}
      {selected && snapshot.data && !snapshot.isError && <div style={{ marginTop: 16 }}>
        <Typography.Paragraph>{snapshot.data.overall_summary}</Typography.Paragraph>
        <ResearchFrameworkPanel analysis={snapshot.data} forceFullReport />
      </div>}
    </Modal>;
}
