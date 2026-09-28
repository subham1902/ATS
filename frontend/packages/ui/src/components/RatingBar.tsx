export function RatingBar({
  value,
  grade,
  showLabel = true,
  height = 8,
}: {
  value: number;
  grade?: string;
  showLabel?: boolean;
  height?: number;
}) {
  const clamped = Math.max(0, Math.min(100, value));

  // Color gradient: red → orange → yellow → green → emerald
  let barColor: string;
  if (clamped >= 85)
    barColor = "#059669"; // emerald
  else if (clamped >= 70)
    barColor = "#16a34a"; // green
  else if (clamped >= 55)
    barColor = "#ca8a04"; // yellow
  else if (clamped >= 40)
    barColor = "#ea580c"; // orange
  else if (clamped >= 25)
    barColor = "#dc2626"; // red
  else barColor = "#991b1b"; // dark red

  const gradeColors: Record<string, string> = {
    S: "#059669",
    A: "#16a34a",
    B: "#ca8a04",
    C: "#ea580c",
    D: "#dc2626",
    F: "#991b1b",
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 100 }}>
      <div
        style={{
          flex: 1,
          height,
          background: "#f3f4f6",
          borderRadius: height,
          overflow: "hidden",
          position: "relative",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${clamped}%`,
            background: `linear-gradient(90deg, ${barColor}cc, ${barColor})`,
            borderRadius: height,
            transition: "width 0.5s ease, background 0.3s ease",
          }}
        />
      </div>
      {showLabel && (
        <span
          style={{
            fontSize: 11,
            fontWeight: 800,
            fontFamily: "monospace",
            color: barColor,
            minWidth: 28,
            textAlign: "right",
          }}
        >
          {clamped.toFixed(0)}
        </span>
      )}
      {grade && (
        <span
          style={{
            fontSize: 10,
            fontWeight: 900,
            padding: "1px 5px",
            borderRadius: 4,
            background: `${gradeColors[grade] ?? "#6b7280"}18`,
            color: gradeColors[grade] ?? "#6b7280",
            border: `1px solid ${gradeColors[grade] ?? "#6b7280"}40`,
            letterSpacing: "0.05em",
          }}
        >
          {grade}
        </span>
      )}
    </div>
  );
}
