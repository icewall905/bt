<script lang="ts">
	import type { LlmContextStats } from '$lib/types';
	let { context }: { context: LlmContextStats } = $props();
	const maximum = $derived(Math.max(1, ...context.hourly.map(h => Math.max(h.p95_input_tokens, h.average_input_tokens))));
	const histogramMax = $derived(Math.max(1, ...context.distribution.map(d => d.requests)));
	const localHour = (iso: string) => new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
	const compact = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(n < 10000 ? 1 : 0)}k` : String(n);
	const points = $derived(context.hourly.map((h, i) => `${48 + (i + 0.5) * 896 / context.hourly.length},${202 - h.p95_input_tokens / maximum * 170}`).join(' '));
</script>

<div class="context-charts">
	<section>
		<h3>Context size over time</h3>
		<p class="small muted">Hourly averages and P95 · local time · first and current hours may be partial</p>
		{#if context.requests}
			<div class="legend"><span><i style:background="var(--accent)"></i>Average input</span><span><i style:background="var(--ai)"></i>P95 input</span></div>
			<svg viewBox="0 0 960 240" role="img" aria-label="Hourly average and P95 input tokens over the last 24 hours. Exact figures are in Hourly figures below.">
				{#each [0, 0.5, 1] as fraction}
					<line x1="48" x2="944" y1={202 - fraction * 170} y2={202 - fraction * 170} stroke="var(--line)" />
					<text x="38" y={206 - fraction * 170} text-anchor="end">{compact(Math.round(maximum * fraction))}</text>
				{/each}
				{#each context.hourly as hour, i}
					{@const step = 896 / context.hourly.length}
					<rect x={48 + i * step + step * 0.2} y={202 - hour.average_input_tokens / maximum * 170} width={step * 0.6} height={hour.average_input_tokens / maximum * 170} rx="2" fill="var(--accent)"><title>{localHour(hour.hour)} · {hour.requests} requests · average {hour.average_input_tokens.toLocaleString()} · P95 {hour.p95_input_tokens.toLocaleString()}</title></rect>
					{#if i % 6 === 0}<text x={48 + (i + 0.5) * step} y="226" text-anchor="middle">{new Date(hour.hour).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}</text>{/if}
				{/each}
				<polyline {points} fill="none" stroke="var(--ai)" stroke-width="3" />
			</svg>
			<details><summary>Hourly figures</summary><div class="scroll"><table><thead><tr><th>Hour</th><th>Requests</th><th>Average</th><th>P95</th><th>Largest</th></tr></thead><tbody>{#each context.hourly as h}<tr><th scope="row">{localHour(h.hour)}</th><td>{h.requests}</td><td>{h.average_input_tokens.toLocaleString()}</td><td>{h.p95_input_tokens.toLocaleString()}</td><td>{h.max_input_tokens.toLocaleString()}</td></tr>{/each}</tbody></table></div></details>
		{:else}<p class="small muted">Context trends will appear after the first successful AI request.</p>{/if}
	</section>
	<section>
		<h3>Request size distribution</h3>
		<p class="small muted">Successful requests by input-token count</p>
		<div class="distribution">{#each context.distribution as bucket}<div><span>{bucket.label}</span><div class="track"><div style:width={`${bucket.requests / histogramMax * 100}%`}></div></div><strong>{bucket.requests.toLocaleString()}</strong></div>{/each}</div>
	</section>
</div>

<style>
	.context-charts { display:grid; grid-template-columns:minmax(0, 1.5fr) minmax(0, 1fr); gap:1.5rem; }
	section { min-width:0; }
	h3 { margin-bottom:0.4rem; }
	svg { display:block; width:100%; height:auto; }
	text { fill:var(--muted); font-size:12px; font-variant-numeric:tabular-nums; }
	.legend { display:flex; gap:1rem; font-size:0.8rem; color:var(--muted); margin-top:0.7rem; }
	.legend span { display:flex; align-items:center; gap:0.4rem; }
	i { width:0.6rem; height:0.6rem; border-radius:50%; }
	.distribution { display:grid; gap:0.85rem; padding:1.2rem 0; font-size:0.85rem; }
	.distribution > div { display:grid; grid-template-columns:5rem 1fr 3rem; align-items:center; gap:0.7rem; }
	.track { height:0.8rem; border-radius:1rem; background:var(--line); overflow:hidden; }
	.track > div { height:100%; background:var(--accent); border-radius:1rem; }
	strong { text-align:right; font-variant-numeric:tabular-nums; }
	summary { cursor:pointer; color:var(--muted); font-size:0.85rem; }
	.scroll { overflow:auto; max-height:20rem; margin-top:0.5rem; }
	table { border-collapse:collapse; width:100%; font-size:0.8rem; }
	th, td { padding:0.5rem; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap; }
	th:first-child { text-align:left; }
	@media (max-width:850px) { .context-charts { grid-template-columns:1fr; } }
</style>
