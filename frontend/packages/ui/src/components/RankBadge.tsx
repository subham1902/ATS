export function RankBadge({ rank }: { rank: number }) {
  if (rank === 1)
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 28,
          height: 28,
          borderRadius: 8,
          background: "linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)",
          border: "2px solid #d97706",
          fontSize: 14,
          boxShadow: "0 2px 8px rgba(245,158,11,0.35)",
        }}
        title="1st Place"
      >
        🥇
      </span>
    );
  if (rank === 2)
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 28,
          height: 28,
          borderRadius: 8,
          background: "linear-gradient(135deg, #e5e7eb 0%, #d1d5db 100%)",
          border: "2px solid #9ca3af",
          fontSize: 14,
          boxShadow: "0 2px 6px rgba(156,163,175,0.3)",
        }}
        title="2nd Place"
      >
        🥈
      </span>
    );
  if (rank === 3)
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 28,
          height: 28,
          borderRadius: 8,
          background: "linear-gradient(135deg, #fed7aa 0%, #fdba74 100%)",
          border: "2px solid #ea580c",
          fontSize: 14,
          boxShadow: "0 2px 6px rgba(234,88,12,0.25)",
        }}
        title="3rd Place"
      >
        🥉
      </span>
    );
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 28,
        height: 28,
        borderRadius: 8,
        background: rank <= 10 ? "#f3f4f6" : "#fafafa",
        border: `1.5px solid ${rank <= 10 ? "#d1d5db" : "#e5e7eb"}`,
        fontSize: 11,
        fontWeight: 800,
        color: rank <= 10 ? "#374151" : "#9ca3af",
        fontFamily: "monospace",
      }}
    >
      {rank}
    </span>
  );
}
