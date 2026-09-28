export function Loading() { return <div className="state">Loading customer intelligence…</div>; }
export function ErrorState({ error }: { error: Error }) { return <div className="state error">Could not load data: {error.message}</div>; }
export function Percent({ value }: { value: number }) { return <span className={value >= .7 ? "risk" : value >= .4 ? "warn" : "good"}>{Math.round(value * 100)}%</span>; }
