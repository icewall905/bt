<script lang="ts">
	import type { LlmContextStats } from '$lib/types';
	import ContextCharts from './ContextCharts.svelte';
	let { context, detailed = false }: { context: LlmContextStats; detailed?: boolean } = $props();
	const names: Record<string, string> = { verdict: 'Judging', plan: 'Search planning', lessons: 'Learning',
		memory_compaction: 'Memory consolidation', memory_audit: 'Memory preservation audit',
		memory_continuity_audit: 'Core continuity audit', lesson_evidence: 'Rule evidence review',
		lesson_revision: 'Rule refinement', lesson_revision_audit: 'Rule revision audit', playlist_brief: 'Playlist import' };
	const pct = (v: number | null) => v === null ? 'Not reported' : `${v.toLocaleString()}%`;
</script>

<div class="context-summary">
	<div><strong>{context.average_input_tokens.toLocaleString()}</strong><span>Average input tokens / request</span></div>
	<div><strong>{context.max_input_tokens.toLocaleString()}</strong><span>Largest input</span></div>
	<div><strong>{context.requests.toLocaleString()}</strong><span>Successful requests · last 24 hours</span></div>
	<div><strong>{context.cached_tokens.toLocaleString()}</strong><span>Cached input tokens reported</span></div>
	{#if detailed}
		<div><strong>{context.median_input_tokens.toLocaleString()}</strong><span>Median input tokens</span></div>
		<div><strong>{context.p95_input_tokens.toLocaleString()}</strong><span>P95 input · 95% of requests at or below this size</span></div>
		<div><strong>{context.total_input_tokens.toLocaleString()}</strong><span>Total input tokens · last 24 hours</span></div>
		<div><strong>{pct(context.cache_hit_percent)}</strong><span>Cached share of server-reported input</span></div>
	{/if}
</div>
<p class="small muted">Includes core memory, corrections, task instructions, schemas, transcripts and comments across all profiles. {context.estimated_requests ? `${context.estimated_requests} requests use a text-only estimate (about 4 characters per token); image tokens are not included in estimates.` : 'Uses input-token counts reported by the model server, including images when reported.'} {context.failed ? `${context.failed} failed attempts are excluded from the averages.` : ''} Cache percentages use successful requests with server-reported input counts; servers that omit cache usage contribute no reported cache hits. Collection starts with this feature; older requests have no measurements.</p>
{#if context.requests}<p class="small muted">Average memory contribution: approximately {Math.ceil(context.average_core_chars / 4).toLocaleString()} core tokens + {Math.ceil(context.average_correction_chars / 4).toLocaleString()} recent-correction tokens{detailed ? ` + ${Math.ceil(context.average_other_chars / 4).toLocaleString()} other text tokens (task instructions, schema and video data)` : ''}. These breakdowns use text estimates.</p>{/if}
{#if detailed}<ContextCharts {context} />{/if}
{#if context.by_task.length}
	<h3>Context by task</h3>
	<div class="scroll"><table class="task-context"><thead><tr><th>Task</th><th>Requests</th><th>Average tokens</th>{#if detailed}<th>P95 tokens</th><th>Largest</th><th>Cache share</th>{/if}</tr></thead><tbody>
		{#each context.by_task as item}<tr><th scope="row">{names[item.task] ?? item.task}</th><td>{item.requests.toLocaleString()}</td><td>{item.average_input_tokens.toLocaleString()}</td>{#if detailed}<td>{item.p95_input_tokens.toLocaleString()}</td><td>{item.max_input_tokens.toLocaleString()}</td><td>{pct(item.cache_hit_percent)}</td>{/if}</tr>{/each}
	</tbody></table></div>
{/if}
{#if detailed}
	{#if context.by_model.length}
		<h3>Context by model</h3><div class="scroll"><table><thead><tr><th>Model</th><th>Requests</th><th>Average</th><th>P95</th><th>Largest</th></tr></thead><tbody>{#each context.by_model as model}<tr><th scope="row">{model.model}</th><td>{model.requests.toLocaleString()}</td><td>{model.average_input_tokens.toLocaleString()}</td><td>{model.p95_input_tokens.toLocaleString()}</td><td>{model.max_input_tokens.toLocaleString()}</td></tr>{/each}</tbody></table></div>
	{/if}
	<h3>Current core memory by profile</h3>
	<p class="small muted">Approximate text tokens. A stored core whose sources changed is excluded from active core use; current source rules apply until the next successful consolidation. The configured budget is {context.configured_core_budget_tokens.toLocaleString()} tokens per profile.</p>
	<div class="scroll"><table class="profile-context"><thead><tr><th>Profile</th><th>Core in use</th><th>Core size / budget</th><th>Raw source rules</th><th>Outside core</th><th>Active rules</th></tr></thead><tbody>
		{#each context.memory_profiles as profile}<tr><th scope="row">{profile.profile}</th><td>{profile.core_valid ? 'Yes' : profile.stored_core_tokens_estimate ? 'Needs rebuild' : 'Not built'}</td><td>{profile.core_tokens_estimate.toLocaleString()} / {context.configured_core_budget_tokens.toLocaleString()}<div class="budget-track" aria-hidden="true"><div style:width={`${Math.min(100, profile.core_tokens_estimate / context.configured_core_budget_tokens * 100)}%`}></div></div></td><td>≈ {profile.raw_rule_tokens_estimate.toLocaleString()}</td><td>≈ {profile.correction_tokens_estimate.toLocaleString()} tokens · {profile.corrections} rules</td><td>{profile.active_rules}</td></tr>{/each}
	</tbody></table></div>
	<p class="small muted">Active rule strength: {Object.entries(context.rule_strengths).map(([kind, count]) => `${count} ${kind}`).join(' · ')}. {context.revisions_24h} automatic rule refinements in the last 24 hours.</p>
{/if}

<style>
	.context-summary { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 10rem), 1fr)); gap:0.8rem; }
	.context-summary div { display:grid; gap:0.25rem; padding:0.9rem; background:rgba(255,255,255,0.035); border:1px solid var(--line); border-radius:var(--r-md); }
	.context-summary strong { font-size:1.6rem; font-variant-numeric:tabular-nums; }
	.context-summary span { color:var(--muted); font-size:0.8rem; }
	.scroll { overflow-x:auto; min-width:0; max-width:100%; }
	table { border-collapse:collapse; width:100%; font-size:0.85rem; font-variant-numeric:tabular-nums; }
	th, td { padding:0.65rem 0.7rem; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap; }
	th:first-child { text-align:left; }
	thead th { color:var(--muted); font-weight:500; }
	.budget-track { height:0.3rem; background:var(--line); border-radius:1rem; margin-top:0.3rem; min-width:7rem; }
	.budget-track > div { height:100%; border-radius:1rem; background:var(--accent); }
</style>
