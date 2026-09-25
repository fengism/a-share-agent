import { Tag } from "antd";
import type { IndustryChainClaim } from "../../types/stock";

export default function IndustryClaimStatus({ claim }: { claim: IndustryChainClaim }) {
  const basis = claim.claim_type === "inference" || claim.claim_type === "opinion" ? claim.claim_type : claim.evidence_basis;
  const label = basis ? { disclosed: "事实陈述", forecast: "机构预测", inference: "研究推断", opinion: "观点" }[basis] : "性质未标注";
  return <span style={{ display: "block", marginTop: 4 }}>
    <Tag>{label}</Tag>
    <Tag color={claim.verification_status === "quote_matched" ? "blue" : "orange"}>
      {claim.verification_status === "quote_matched" ? "原文匹配 · 非事实核实" : "待验证"}
    </Tag>
  </span>;
}
