<script lang="ts">
	import type { StatsDay } from '$lib/types';
	let { daily }: { daily: StatsDay[] } = $props();
	const maximum = $derived(Math.max(1, ...daily.map(d => Math.max(d.found, d.accepted, d.watched))));
	const series = [
		{ key: 'found' as const, label: 'Discovered', color: '#a996ff' },
		{ key: 'accepted' as const, label: 'Accepted', color: '#5ed9b0' },
		{ key: 'watched' as const, label: 'Watched', color: '#76bbff' }
	];
</script>

<div class="legend">{#each series as s}<span><i style:background={s.color}></i>{s.label}</span>{/each}</div>
<svg viewBox="0 0 960 240" role="img" aria-label="Daily discoveries, accepted videos and watched videos. Exact figures and video lists are in the Daily activity table below.">
	{#each [0, 0.5, 1] as fraction}
		<line x1="48" x2="944" y1={202 - fraction * 170} y2={202 - fraction * 170} stroke="rgba(255,255,255,0.09)" />
		<text x="38" y={206 - fraction * 170} text-anchor="end">{Math.round(maximum * fraction)}</text>
	{/each}
	{#each daily as day, i (day.date)}
		{@const step = 896 / daily.length}
		{@const width = Math.max(1, step * 0.23)}
		{#each series as s, j}
			<rect x={48 + i * step + step * 0.1 + j * width} y={202 - day[s.key] / maximum * 170} width={width} height={day[s.key] / maximum * 170} rx="1" fill={s.color}><title>{day.date} · {s.label}: {day[s.key]}</title></rect>
		{/each}
		{#if i === 0 || i === daily.length - 1 || (daily.length > 14 && i % Math.ceil(daily.length / 5) === 0)}
			<text x={48 + (i + 0.5) * step} y="226" text-anchor="middle">{day.date.slice(5).replace('-', '/')}</text>
		{/if}
	{/each}
</svg>

<style>
	svg { display: block; width: 100%; height: auto; min-height: 9rem; }
	text { fill: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
	.legend { display: flex; gap: 1.25rem; flex-wrap: wrap; margin-bottom: 0.8rem; font-size: 0.8rem; color: var(--muted); }
	.legend span { display: flex; gap: 0.4rem; align-items: center; }
	i { display: inline-block; width: 0.55rem; height: 0.55rem; border-radius: 50%; }
</style>
