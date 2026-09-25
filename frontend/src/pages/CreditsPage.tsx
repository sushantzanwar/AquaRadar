import { useEffect, useState } from "react";
import { getLeaderboard, type Leaderboard as Board, type SceneIndex } from "../api/client";
import { Leaderboard } from "../components/Leaderboard";
import { PhotoUpload } from "../components/PhotoUpload";

export function CreditsPage({ scenes }: { scenes: SceneIndex | null }) {
  const [bodyId, setBodyId] = useState(scenes?.water_bodies[0]?.id ?? "demo-reservoir");
  const [board, setBoard] = useState<Board | null>(null);

  function refresh() {
    getLeaderboard()
      .then(setBoard)
      .catch(() => setBoard(null));
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <section className="credits">
      <h2>AquaCredits</h2>
      <p className="muted">One demo user. A photo must fall inside the water boundary. Duplicates earn nothing.</p>
      <label>
        Water body
        <select value={bodyId} onChange={(event) => setBodyId(event.target.value)}>
          {(scenes?.water_bodies ?? []).map((body) => (
            <option key={body.id} value={body.id}>
              {body.name}
            </option>
          ))}
        </select>
      </label>
      <PhotoUpload waterBodyId={bodyId} onDone={refresh} />
      <h3>Leaderboard</h3>
      <Leaderboard board={board} />
    </section>
  );
}
