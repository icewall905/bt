<script lang="ts">
	import { goto } from '$app/navigation';
	import { agent, STATE_LABEL, toneOf, cleanDetail } from '$lib/stores/agent.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { focusable, navScope } from '$lib/nav';
	import { fmtCountdown, clockTime } from '$lib/util';
	import { api } from '$lib/api';
	import AgentGlyph from './AgentGlyph.svelte';
	import ProgressRing from './ProgressRing.svelte';
	import { fmtBytes } from '$lib/util';

	let open = $state(false);
	const st = $derived(agent.effective);
	const tone = $derived(toneOf(st));
	const label = $derived(STATE_LABEL[st] ?? st);
	const cat = $derived(session.categoryById(agent.state.category_id ?? null));
	const extra = $derived.by(() => {
		if (st === 'sleeping' && agent.secondsLeft != null) return `next in ${fmtCountdown(agent.secondsLeft)}`;
		const bu = st === 'backoff'
			? (agent.state.backoff_until || agent.state.until_end || agent.state.until)
			: agent.state.until;
		if (st === 'backoff' && bu) return `until ${clockTime(bu)}`;
		if (st === 'paused' || st === 'offline') return '';
		return cleanDetail(st, agent.state.detail);
	});
	const title = $derived((agent.state.title as string | undefined) ?? '');
	const dl = $derived(agent.downloader);
	const downloading = $derived(dl.state === 'downloading');
</script>

<div class="wrap">
	<button
		class="pill {tone}"
		aria-expanded={open}
		aria-label="AI status: {label} {extra}"
		use:focusable={{ group: 'topbar', id: 'status-pill', scroll: 'none', onSelect: () => (open = !open) }}
	>
		<span class="glyph"><AgentGlyph state={st} /></span>
		<span class="txt">
			<span class="lbl">{label}</span>
			{#if extra}<span class="extra">{extra}</span>{/if}
		</span>
		{#if downloading}<span class="dl" title="Saving offline: {dl.title ?? ''}"><ProgressRing value={dl.progress ?? 0} label="Saving offline {Math.round((dl.progress ?? 0) * 100)}%" /></span>{/if}
	</button>
	<div class="tip glass" role="tooltip">
		<strong>{label}</strong>
		{#if agent.state.detail}<span>{agent.state.detail}</span>{/if}
		{#if title}<span class="muted">🎬 {title}</span>{/if}
		{#if downloading}<span class="muted">⤓ Saving offline {Math.round((dl.progress ?? 0) * 100)}%: {dl.title}</span>{/if}
	</div>

	{#if open}
		<div class="pop glass" use:navScope={{ onBack: () => (open = false) }}>
			<div class="pop-head {tone}">
				<span class="big"><AgentGlyph state={st} size="2.2rem" /></span>
				<div>
					<div class="lbl">{label}</div>
					{#if extra}<div class="muted small">{extra}</div>{/if}
				</div>
			</div>
			{#if agent.state.detail && agent.state.detail !== extra}<p class="small">{agent.state.detail}</p>{/if}
			{#if cat}<p class="small muted">Working on {cat.emoji} {cat.name}</p>{/if}
			{#if agent.state.video_id}
				<div class="vid">
					<img src={api.thumb(String(agent.state.video_id), 'mq')} alt="" />
					<span class="small">{title || 'Current video'}</span>
				</div>
			{/if}
			{#if downloading}
				<p class="small muted">⤓ Saving offline: {dl.title} ({Math.round((dl.progress ?? 0) * 100)}%{dl.speed ? `, ${fmtBytes(dl.speed)}/s` : ''})</p>
			{/if}
			{#if !agent.connected}<p class="small muted">The live connection to the server dropped. Reconnecting…</p>{/if}
			<div class="hstack">
				<button class="btn primary" use:focusable={{ autofocus: true, scroll: 'none', onSelect: () => ((open = false), goto('/agent')) }}>Open AI activity</button>
				<button class="btn" use:focusable={{ scroll: 'none', onSelect: () => agent.toggle() }}>{agent.control.paused ? 'Resume AI' : 'Pause AI'}</button>
			</div>
		</div>
	{/if}
</div>

<style>
	.wrap {
		position: relative;
		min-width: 0;
	}
	.pill {
		--focus-scale: 1.05;
		display: flex;
		align-items: center;
		gap: 0.6rem;
		max-width: clamp(10rem, 22vw, 30rem);
		height: 2.6rem;
		padding: 0 1rem 0 0.55rem;
		border-radius: var(--r-pill);
		border: 1px solid var(--line-strong);
		background: rgba(20, 16, 46, 0.7);
		cursor: pointer;
		color: var(--text);
		text-align: left;
	}
	.glyph {
		display: grid;
		place-items: center;
		width: 1.9rem;
		height: 1.9rem;
		border-radius: 50%;
		flex: none;
		color: var(--tone);
		background: color-mix(in srgb, var(--tone) 18%, transparent);
		box-shadow: 0 0 0 0 color-mix(in srgb, var(--tone) 50%, transparent);
	}
	.work {
		--tone: var(--accent);
	}
	.work .glyph {
		animation: ring 2s ease-out infinite;
	}
	.rest {
		--tone: var(--info);
	}
	.bad {
		--tone: var(--bad);
	}
	.bad.pill {
		border-color: rgba(255, 92, 122, 0.55);
	}
	.paused {
		--tone: var(--muted);
	}
	.off {
		--tone: var(--faint);
	}
	.idle {
		--tone: var(--ai);
	}
	.txt {
		display: flex;
		gap: 0.5rem;
		min-width: 0;
		align-items: baseline;
		white-space: nowrap;
	}
	.lbl {
		font-weight: 650;
		font-size: 0.9rem;
	}
	.extra {
		font-size: 0.82rem;
		color: var(--muted);
		overflow: hidden;
		text-overflow: ellipsis;
		font-variant-numeric: tabular-nums;
	}
	.dl {
		display: grid;
		place-items: center;
		flex: none;
		margin-left: -0.2rem;
	}
	.tip {
		position: absolute;
		top: calc(100% + 0.6rem);
		right: 0;
		width: max-content;
		max-width: 22rem;
		display: grid;
		gap: 0.25rem;
		padding: 0.7rem 0.9rem;
		border-radius: var(--r-md);
		font-size: 0.85rem;
		opacity: 0;
		pointer-events: none;
		transform: translateY(-4px);
		transition: 0.18s var(--ease);
		background: rgba(24, 20, 56, 0.95);
		z-index: 60;
	}
	.wrap:hover .tip {
		opacity: 1;
		transform: none;
	}
	.pop {
		position: absolute;
		top: calc(100% + 0.6rem);
		right: 0;
		width: min(90vw, 26rem);
		display: grid;
		gap: 0.8rem;
		padding: 1.1rem;
		border-radius: var(--r-lg);
		background: rgba(24, 20, 56, 0.96);
		box-shadow: var(--shadow-lg);
		z-index: 70;
		animation: rise 0.2s var(--ease);
	}
	.wrap:has(.pop) .tip {
		display: none;
	}
	.pop-head {
		display: flex;
		gap: 0.9rem;
		align-items: center;
	}
	.pop-head .big {
		color: var(--tone);
	}
	.pop-head .lbl {
		font-size: 1.1rem;
	}
	.vid {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}
	.vid img {
		width: 7rem;
		aspect-ratio: 16/9;
		object-fit: cover;
		border-radius: var(--r-sm);
	}
	@keyframes ring {
		0% {
			box-shadow: 0 0 0 0 color-mix(in srgb, var(--tone) 55%, transparent);
		}
		100% {
			box-shadow: 0 0 0 0.6rem transparent;
		}
	}
	@media (max-width: 720px) {
		.extra {
			display: none;
		}
		.pill {
			padding-right: 0.8rem;
		}
	}
	@media (max-width: 480px) {
		.lbl {
			display: none;
		}
		.pill {
			padding: 0 0.35rem;
		}
	}
</style>
