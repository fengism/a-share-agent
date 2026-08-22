/**
 * Quiet auto-refresh hint: a soft pulsing dot + label.
 *
 * Unlike an antd <Tag>, this has no filled background, so it never produces a
 * light chip in dark theme. The dot uses the brand primary with a slowed
 * pulse so it reads as "live" without being noisy, and respects
 * prefers-reduced-motion.
 */
export default function RefreshBadge({ label = "每 60 秒刷新" }: { label?: string }) {
  return (
    <span className="refresh-badge" role="status" aria-label={label}>
      <span className="refresh-badge__dot" aria-hidden="true" />
      <span className="refresh-badge__label">{label}</span>
    </span>
  );
}
