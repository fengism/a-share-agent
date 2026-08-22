interface LoadingSpinnerProps {
  size?: "medium" | "large";
}

export default function LoadingSpinner({ size = "medium" }: LoadingSpinnerProps) {
  return <span className={`app-spinner app-spinner--${size}`} aria-hidden="true" />;
}
