import { CheckCircle2, GitBranch, Search, ShieldCheck, Sparkles, UserRound } from "lucide-react";
import type { TraceEvent, ValidationResult } from "../api/client";

const icons = {
  supervisor_agent: GitBranch,
  analytics_agent: Search,
  customer_intelligence_agent: UserRound,
  retrieval_agent: Search,
  reasoning_agent: Sparkles,
  validator_agent: ShieldCheck,
  repair_agent: CheckCircle2,
};

export function AgentTrace({ trace, validation }: {
  trace: TraceEvent[];
  validation?: ValidationResult;
}) {
  if (!trace.length) return null;
  return <section className="agent-panel">
    <div className="agent-panel-head">
      <strong>Multi-agent workflow</strong>
      {validation && <span className={validation.grounded ? "grounded" : "needs-review"}>
        {validation.grounded ? "Grounded" : "Needs review"} · {Math.round(validation.confidence * 100)}%
      </span>}
    </div>
    <div className="agent-trace">
      {trace.map((event, index) => {
        const Icon = icons[event.node as keyof typeof icons] ?? CheckCircle2;
        return <div className="agent-step" key={`${event.node}-${index}`}>
          <i><Icon size={14}/></i>
          <div><b>{event.node.replaceAll("_", " ")}</b><p>{event.detail}</p></div>
        </div>;
      })}
    </div>
  </section>;
}
