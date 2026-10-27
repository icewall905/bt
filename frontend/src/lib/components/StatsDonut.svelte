<script lang="ts">
	import { focusable } from '$lib/nav';
	let { title, segments, onSelect }: {
		title: string;
		segments: { label: string; value: number; color: string; key: string }[];
		onSelect?: (key: string, label: string) => void;
	} = $props();
	const total = $derived(segments.reduce((sum, s) => sum + s.value, 0));
	const slices = $derived(segments.map((s, i) => ({ ...s,
		length: total ? s.value / total * 100 : 0,
		offset: total ? -segments.slice(0, i).reduce((sum, p) => sum + p.value, 0) / total * 100 : 0
	})));
</script>

<div class="donut-chart">
	<svg viewBox="0 0 160 160" role="img" aria-label="{title}: {segments.map(s => `${s.label} ${s.value}`).join(', ')}">
		<circle cx="80" cy="80" r="60" fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="19" />
		{#each slices as s (s.key)}
			{#if s.value}<circle cx="80" cy="80" r="60" fill="none" stroke={s.color} stroke-width="19" pathLength="100" stroke-dasharray="{s.length} {100 - s.length}" stroke-dashoffset={s.offset} transform="rotate(-90 80 80)"><title>{s.label}: {s.value.toLocaleString()} ({Math.round(s.length)}%)</title></circle>{/if}
		{/each}
		<text x="80" y="78" text-anchor="middle" class="total">{total.toLocaleString()}</text>
		<text x="80" y="97" text-anchor="middle" class="caption">{total ? 'total' : 'no data yet'}</text>
	</svg>
	<div class="legend">
		{#each slices as s (s.key)}
			{#if onSelect}
				<button class="legend-row" use:focusable={{ group: `chart-${title}`, onSelect: () => onSelect?.(s.key, s.label) }}>
					<span class="swatch" style:background={s.color}></span><span>{s.label}</span><strong>{s.value.toLocaleString()}</strong><span class="percent">{Math.round(s.length)}%</span>
				</button>
			{:else}
				<div class="legend-row"><span class="swatch" style:background={s.color}></span><span>{s.label}</span><strong>{s.value.toLocaleString()}</strong><span class="percent">{Math.round(s.length)}%</span></div>
			{/if}
		{/each}
	</div>
</div>

<style>
	.donut-chart { display: flex; align-items: center; justify-content: center; gap: 1.25rem; min-width: 0; flex-wrap: wrap; }
	svg { width: min(42%, 12rem); min-width: 8rem; max-width: 12rem; flex: 0 1 11rem; overflow: visible; }
	.total { fill: var(--text); font-size: 20px; font-weight: 750; font-variant-numeric: tabular-nums; }
	.caption { fill: var(--muted); font-size: 10px; }
	.legend { display: grid; gap: 0.25rem; flex: 2; min-width: min(100%, 13rem); }
	.legend-row { width: 100%; display: grid; grid-template-columns: 0.6rem 1fr auto 2.5rem; align-items: center; gap: 0.65rem; padding: 0.5rem 0.3rem; text-align: left; font-size: 0.82rem; color: var(--muted); border: 0; border-radius: 0.4rem; background: transparent; }
	button.legend-row { cursor: pointer; }
	button.legend-row:hover { background: rgba(255,255,255,0.07); color: var(--text); }
	.swatch { width: 0.55rem; height: 0.55rem; border-radius: 50%; }
	strong { color: var(--text); font-variant-numeric: tabular-nums; }
	.percent { color: var(--faint); text-align: right; }
</style>
