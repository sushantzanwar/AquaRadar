import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { askAssistant, type AssistantAnswer, type ChatMessage } from "../api/client";
import { ConfidenceBadge } from "./ConfidenceBadge";

type Props = { waterBodyId: string; zoneId?: string; date?: string };

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  answer?: AssistantAnswer;
  loading?: boolean;
  error?: string;
};

const SUGGESTED_QUESTIONS = [
  "What does a turbidity flag mean?",
  "Explain the current alert",
  "What are WHO water quality guidelines?",
  "What causes harmful algal blooms?",
  "How should I interpret the sigma score?",
];

let _id = 0;
const uid = () => `msg-${++_id}`;

export function AssistantPanel({ waterBodyId, zoneId, date }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: uid(),
      role: "assistant",
      content:
        "Hello! I'm **AquaWatch AI** — your water quality assistant. I can explain satellite indicators, interpret alerts and anomaly scores, answer questions about WHO/EPA guidelines, and help you understand the current dashboard data.\n\nWhat would you like to know?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState<Record<string, boolean>>({});
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function buildHistory(): ChatMessage[] {
    return messages
      .filter((m) => !m.loading && !m.error && m.role !== "assistant" || m.role === "assistant")
      .slice(-10) // last 5 turns
      .map((m) => ({ role: m.role, content: m.content }));
  }

  async function send(question: string) {
    if (!question.trim() || isLoading) return;

    const userMsg: Message = { id: uid(), role: "user", content: question.trim() };
    const loadingMsg: Message = { id: uid(), role: "assistant", content: "", loading: true };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInput("");
    setIsLoading(true);

    const history = buildHistory();

    try {
      const answer = await askAssistant(
        question.trim(),
        waterBodyId,
        zoneId,
        date,
        history,
      );
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, content: answer.answer, answer, loading: false }
            : m,
        ),
      );
    } catch (err) {
      const errorText = err instanceof Error ? err.message : "Failed to get a response.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? { ...m, content: "", loading: false, error: errorText }
            : m,
        ),
      );
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  function toggleSources(id: string) {
    setSourcesOpen((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function renderContent(text: string) {
    // Convert simple markdown to HTML-like spans
    return text
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`(.*?)`/g, "<code>$1</code>")
      .replace(/\n/g, "<br/>");
  }

  return (
    <section className="assistant-panel">
      {/* Header */}
      <div className="assistant-header">
        <div className="assistant-avatar">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2z"/>
            <path d="M12 8v4l3 3"/>
          </svg>
        </div>
        <div>
          <strong>AquaWatch AI</strong>
          <span className="assistant-subtitle">Water quality assistant · RAG-powered</span>
        </div>
        <div className="assistant-status">
          <span className="status-dot" />
          online
        </div>
      </div>

      {/* Messages */}
      <div className="assistant-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-row chat-row--${msg.role}`}>
            {msg.role === "assistant" && (
              <div className="chat-avatar">AI</div>
            )}
            <div className={`chat-bubble chat-bubble--${msg.role}`}>
              {msg.loading ? (
                <div className="chat-typing">
                  <span /><span /><span />
                </div>
              ) : msg.error ? (
                <p className="chat-error">⚠️ {msg.error}</p>
              ) : (
                <>
                  <div
                    className="chat-text"
                    dangerouslySetInnerHTML={{ __html: renderContent(msg.content) }}
                  />
                  {/* Confidence + sources for assistant messages */}
                  {msg.answer && (
                    <div className="chat-meta">
                      <ConfidenceBadge score={msg.answer.confidence} reasons={msg.answer.confidence_reasons} />
                      {msg.answer.source_ids.length > 0 && (
                        <button
                          className="sources-toggle"
                          onClick={() => toggleSources(msg.id)}
                        >
                          {sourcesOpen[msg.id] ? "▲" : "▼"} {msg.answer.source_ids.length} source
                          {msg.answer.source_ids.length !== 1 ? "s" : ""}
                        </button>
                      )}
                    </div>
                  )}
                  {/* Expanded sources */}
                  {msg.answer && sourcesOpen[msg.id] && msg.answer.passages.length > 0 && (
                    <div className="chat-sources">
                      {msg.answer.passages.map((p) => (
                        <div key={p.source_id} className="chat-source-item">
                          <span className="source-label">{p.title}</span>
                          <p className="source-text">{p.text.slice(0, 220)}…</p>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Suggested questions — show only at the start */}
      {messages.length <= 1 && (
        <div className="assistant-suggestions">
          {SUGGESTED_QUESTIONS.map((q) => (
            <button key={q} className="suggestion-chip" onClick={() => send(q)}>
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <form className="assistant-input" onSubmit={handleSubmit}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about water quality, alerts, or satellite data…"
          rows={2}
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading || !input.trim()} className="send-btn">
          {isLoading ? (
            <svg className="spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          )}
        </button>
      </form>
      <p className="assistant-disclaimer">
        Satellite indicators are not laboratory measurements. Lab verification required for operational decisions.
      </p>
    </section>
  );
}
