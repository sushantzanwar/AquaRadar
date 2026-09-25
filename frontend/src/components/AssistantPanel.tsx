import { useState, type FormEvent } from "react";
import { askAssistant, type AssistantAnswer } from "../api/client";

type Props = { waterBodyId: string; zoneId?: string; date?: string };

export function AssistantPanel({ waterBodyId, zoneId, date }: Props) {
  const [question, setQuestion] = useState("What does a turbidity flag mean?");
  const [answer, setAnswer] = useState<AssistantAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      setAnswer(await askAssistant(question, waterBodyId, zoneId, date));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assistant failed");
    }
  }

  return (
    <section>
      <h3>Science assistant</h3>
      <form onSubmit={submit} className="stack">
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} />
        <button type="submit">Ask</button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {answer ? (
        <div>
          <p>{answer.answer}</p>
          <p className="muted">Sources: {answer.source_ids.join(", ") || "none"}</p>
        </div>
      ) : null}
    </section>
  );
}
