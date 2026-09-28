import { FormEvent, useState } from "react";
import "../agent.css";
import { api, type CopilotResponse } from "../api/client";
import { AgentTrace } from "../components/AgentTrace";
import { GroundingSources } from "../components/GroundingSources";

const labels: Record<string, string> = {
  analytics: "SQL analytics",
  sales_opportunities: "SQL opportunities",
  customer_intelligence: "Customer 360",
  knowledge: "RAG playbook",
  hybrid: "Hybrid SQL + RAG",
};

export function CopilotPage() {
  const [question, setQuestion] = useState("Which customers should my sales team contact today?");
  const [answer, setAnswer] = useState(
    "Ask about revenue, segments, opportunities, a specific customer, or a retention strategy.",
  );
  const [intent, setIntent] = useState("");
  const [response, setResponse] = useState<CopilotResponse | null>(null);
  const [busy, setBusy] = useState(false);

  async function ask(nextQuestion: string) {
    const normalizedQuestion = nextQuestion.trim();
    if (!normalizedQuestion || busy) return;

    setBusy(true);
    setAnswer("Analyzing your latest question…");
    setIntent("");
    setResponse(null);
    try {
      const result = await api.copilot(normalizedQuestion);
      setAnswer(result.answer);
      setIntent(result.intent);
      setResponse(result);
    } catch (error) {
      setAnswer(error instanceof Error ? error.message : "Request failed");
      setIntent("");
      setResponse(null);
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  return <section>
    <div className="section-head">
      <div><h2>GrowthPilot Copilot</h2><p>Grounded in structured analytics, model outputs, and your sales playbook.</p></div>
      <span className="pill">Multi-agent · grounded</span>
    </div>
    <article className="copilot" aria-busy={busy}>
      <div className="chat-answer" aria-live="polite"><span>GP</span><div>{intent && <small>{labels[intent] ?? intent}</small>}<p>{answer}</p></div></div>
      <form onSubmit={submit}>
        <textarea value={question} onChange={event => setQuestion(event.target.value)} rows={3} disabled={busy}/>
        <button type="submit" disabled={busy || !question.trim()}>{busy ? "Thinking…" : "Ask GrowthPilot"}</button>
      </form>
      <div className="prompts">{["Why is Customer 15000 at risk?", "Which segment is largest?", "What is our revenue?"].map(prompt => <button type="button" key={prompt} disabled={busy} onClick={() => { setQuestion(prompt); void ask(prompt); }}>{prompt}</button>)}</div>
    </article>
    {response && <div className="agent-results">
      <AgentTrace trace={response.trace} validation={response.validation}/>
      <GroundingSources citations={response.citations}/>
      <p className="provider-note">Answer provider: {response.provider}</p>
    </div>}
  </section>;
}
