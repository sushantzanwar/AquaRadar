import type { Leaderboard as Board } from "../api/client";

export function Leaderboard({ board }: { board: Board | null }) {
  if (!board) return <p className="muted">Leaderboard unavailable.</p>;
  return (
    <ol className="priority">
      {board.entries.map((entry) => (
        <li key={entry.user_id}>
          <strong>{entry.user_id}</strong>
          <span>{entry.credits} credits</span>
        </li>
      ))}
    </ol>
  );
}
