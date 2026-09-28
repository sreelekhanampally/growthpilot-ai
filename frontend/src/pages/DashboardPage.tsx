import { useQuery } from "@tanstack/react-query";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api } from "../api/client";
import { ErrorState, Loading } from "../components/States";

const colors = ["#6d5dfc", "#20c997", "#ffb547", "#ff6b6b", "#3ca6ff", "#9b7bff"];
export function DashboardPage() {
  const query = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  if (query.isLoading) return <Loading/>; if (query.error) return <ErrorState error={query.error}/>; const data = query.data!;
  const cards = [["Lifetime revenue", `${data.currency} ${data.lifetime_revenue.toLocaleString(undefined,{maximumFractionDigits:0})}`],["Known customers",data.customers.toLocaleString()],["High churn risk",data.high_churn_risk.toLocaleString()],["Sales opportunities",data.sales_opportunities.toLocaleString()]];
  return <section><div className="section-head"><div><h2>Executive overview</h2><p>Live decisions from transaction behavior and approved model runs.</p></div><span className="pill">As-of latest snapshot</span></div><div className="metrics">{cards.map(([label,value],i)=><article className="metric" key={label}><small>{label}</small><strong>{value}</strong><span>{i < 2 ? "Source reconciled" : "Probability ≥ 70%"}</span></article>)}</div><div className="grid two"><article className="panel"><h3>Customer mix</h3><p>Current behavioral segments</p><div className="chart"><ResponsiveContainer width="100%" height={270}><PieChart><Pie data={data.segments} dataKey="customers" nameKey="name" innerRadius={72} outerRadius={108} paddingAngle={2}>{data.segments.map((item,index)=><Cell key={item.name} fill={colors[index%colors.length]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></div></article><article className="panel"><h3>What GrowthPilot sees</h3><p>Recommended operating rhythm</p><div className="insight"><b>1</b><div><strong>Protect value first</strong><span>Work high-value churn risks before broad campaigns.</span></div></div><div className="insight"><b>2</b><div><strong>Convert active intent</strong><span>Use ranked products for high-propensity customers.</span></div></div><div className="insight"><b>3</b><div><strong>Record outcomes</strong><span>Close the loop so future policies can learn.</span></div></div></article></div></section>;
}
