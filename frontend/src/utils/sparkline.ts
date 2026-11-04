export interface SparklineGeometry {
  path: string;
  width: number;
  height: number;
  count: number;
  delta: number;
  min: number;
  max: number;
}

export function buildSparklinePath(
  values: number[],
  width: number,
  height: number,
): SparklineGeometry | null {
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const step = width / (values.length - 1);
  const path = values
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / span) * height;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return {
    path,
    width,
    height,
    count: values.length,
    delta: values[values.length - 1] - values[0],
    min,
    max,
  };
}
