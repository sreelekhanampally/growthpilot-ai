import { Database, FileText } from "lucide-react";
import type { CopilotCitation } from "../api/client";

export function GroundingSources({ citations }: { citations: CopilotCitation[] }) {
  if (!citations.length) return null;
  return <section className="agent-panel">
    <div className="agent-panel-head"><strong>Grounding sources</strong></div>
    <div className="source-grid">
      {citations.map(citation => {
        const structured = citation.source.startsWith("SQL:") || citation.chunk_id.startsWith("customer-");
        const Icon = structured ? Database : FileText;
        return <article className="source-card" key={citation.chunk_id}>
          <div><Icon size={14}/><b>{citation.source}</b></div>
          <p>{citation.excerpt}</p>
          {typeof citation.score === "number" && <small>confidence {Math.round(citation.score * 100)}%</small>}
        </article>;
      })}
    </div>
  </section>;
}
