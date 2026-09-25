import { useState, type FormEvent } from "react";
import { askAssistant, type AssistantAnswer } from "../api/client";

type Props = { waterBodyId?: string; zoneId?: string; date?: string };

const PROMPTS = [
  "What is elevated on this water body?",
  "Which indicators are we monitoring?",
  "Are there active alerts?",
];

export function AssistantPanel({ waterBodyId, zoneId, date }: Props) {
  const [question, setQuestion] = useState(PROMPTS[0]);
  const [answer, setAnswer] = useState<AssistantAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event?: FormEvent, next?: string) {
    event?.preventDefault();
    const asked = (next ?? question).trim();
    if (!asked) return;
    setQuestion(asked);
    setError(null);
    try {
      setAnswer(await askAssistant(asked, waterBodyId, zoneId, date));
    } catch (err) {
      setAnswer(null);
      setError(err instanceof Error ? err.message : "Assistant failed");
    }
  }

  return (
    <section className="card">
      <h3>Water body assistant</h3>
      <p className="muted">
        Answers quote this water body's stored series, alerts, and scene evidence, plus the local corpus. No external model is called.
      </p>
      <div className="assistant-prompts">
        {PROMPTS.map((prompt) => (
          <button key={prompt} type="button" onClick={() => submit(undefined, prompt)}>
            {prompt}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="stack">
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} />
        <button type="submit">Ask</button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {answer ? (
        <div>
          <p className="assistant-answer">{answer.answer}</p>
          <p className="muted">Sources: {answer.source_ids.join(", ") || "platform series"}</p>
          <p className="disclaimer-inline">{answer.disclaimer}</p>
        </div>
      ) : null}
    </section>
  );
}
