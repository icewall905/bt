<script lang="ts">
	import { agent, STATE_LABEL } from '$lib/stores/agent.svelte';
	import AgentGlyph from './AgentGlyph.svelte';
	import { fmtCountdown } from '$lib/util';

	let { categoryId, color }: { categoryId?: number; color?: string } = $props();
	const mine = $derived(agent.state.category_id === categoryId);
	const st = $derived(mine ? agent.effective : agent.effective === 'paused' || agent.effective === 'offline' ? agent.effective : 'searching');
</script>

<div class="looking" style:--cat={color ?? 'var(--ai)'}>
	{#each [0, 1, 2] as i}
		<div class="ghost" style:animation-delay="{i * 0.25}s"></div>
	{/each}
	<div class="msg">
		<span class="g"><AgentGlyph state={st} size="2rem" /></span>
		<div>
			<div class="t">
				{#if st === 'paused'}The AI is paused. Resume it to fill this row.{:else if st === 'offline'}The AI worker is offline.{:else}The AI is looking for videos…{/if}
			</div>
			{#if mine}
				<div class="small muted">
					{STATE_LABEL[agent.effective] ?? agent.effective}{agent.state.detail ? `: ${agent.state.detail}` : ''}{agent.secondsLeft ? ` (${fmtCountdown(agent.secondsLeft)})` : ''}
				</div>
			{:else}
				<div class="small muted">New picks appear here as soon as they pass review.</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.looking {
		position: relative;
		display: flex;
		gap: clamp(0.9rem, 1.3vw, 1.6rem);
		width: 100%;
	}
	.ghost {
		flex: none;
		width: var(--card-w);
		aspect-ratio: 16/9;
		border-radius: var(--r-md);
		background: linear-gradient(100deg, rgba(255, 255, 255, 0.03) 20%, color-mix(in srgb, var(--cat) 18%, transparent) 40%, rgba(255, 255, 255, 0.03) 60%) var(--surface);
		background-size: 220% 100%;
		animation: shimmer 2.2s linear infinite;
		border: 1px dashed color-mix(in srgb, var(--cat) 35%, transparent);
	}
	.msg {
		position: absolute;
		left: 0;
		top: 50%;
		transform: translateY(-50%);
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-left: 1.25rem;
		padding: 0.9rem 1.2rem;
		border-radius: var(--r-md);
		background: rgba(12, 10, 28, 0.82);
		border: 1px solid var(--line);
		backdrop-filter: blur(8px);
		max-width: min(36rem, 85vw);
	}
	.g {
		color: var(--accent);
	}
	.t {
		font-weight: 650;
	}
</style>
