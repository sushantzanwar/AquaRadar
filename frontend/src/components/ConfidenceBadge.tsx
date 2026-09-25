export function ConfidenceBadge({ score, reasons }: { score: number; reasons: string[] }) {
  return (
    <span className="badge" title={reasons.join(", ")}>
      confidence {score.toFixed(2)}
      {reasons[0] ? ` · ${reasons[0]}` : ""}
    </span>
  );
}
