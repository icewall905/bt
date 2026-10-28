<script lang="ts">
	import type { LlmContextStats } from '$lib/types';
	let { context }: { context: LlmContextStats } = $props();
	const names: Record<string, string> = { verdict: 'Judging', plan: 'Search planning', lessons: 'Learning',
		memory_compaction: 'Memory consolidation', memory_audit: 'Memory audit', playlist_brief: 'Playlist import' };
</script>

<div class="context-summary">
	<div><strong>{context.average_input_tokens.toLocaleString()}</strong><span>Average input tokens / request</span></div>
	<div><strong>{context.max_input_tokens.toLocaleString()}</strong><span>Largest input</span></div>
	<div><strong>{context.requests.toLocaleString()}</strong><span>Successful requests · last 24 hours</span></div>
	<div><strong>{context.cached_tokens.toLocaleString()}</strong><span>Cached input tokens reported</span></div>
</div>
<p class="small muted">Includes core memory, corrections, task instructions, schemas, transcripts and comments across all profiles. {context.estimated_requests ? `${context.estimated_requests} requests use a text-only estimate (about 4 characters per token); image tokens are not included in estimates.` : 'Uses input-token counts reported by the model server, including images when reported.'} {context.failed ? `${context.failed} failed attempts are excluded from the averages.` : ''} Collection starts with this feature; older requests have no measurements.</p>
{#if context.requests}<p class="small muted">Average memory contribution: approximately {Math.ceil(context.average_core_chars / 4).toLocaleString()} core tokens + {Math.ceil(context.average_correction_chars / 4).toLocaleString()} recent-correction tokens. These two breakdowns use text estimates.</p>{/if}
{#if context.by_task.length}
	<ul class="task-context">
		{#each context.by_task as item}<li><span>{names[item.task] ?? item.task}</span><strong>{item.average_input_tokens.toLocaleString()} tokens on average</strong><span class="faint">{item.requests.toLocaleString()} requests</span></li>{/each}
	</ul>
{/if}

<style>
	.context-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 10rem), 1fr)); gap: 0.8rem; }
	.context-summary div { display: grid; gap: 0.25rem; padding: 0.9rem; background: rgba(255,255,255,0.035); border: 1px solid var(--line); border-radius: var(--r-md); }
	.context-summary strong { font-size: 1.6rem; font-variant-numeric: tabular-nums; }
	.context-summary span { color: var(--muted); font-size: 0.8rem; }
	.task-context { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.5rem; }
	.task-context li { display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; justify-content: space-between; font-size: 0.85rem; border-bottom: 1px solid var(--line); padding: 0.5rem 0; }
</style>
