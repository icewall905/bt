<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { focusable } from '$lib/nav';
	import { dialogs } from '$lib/stores/dialogs.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { fmtBytes, fmtDuration } from '$lib/util';
	import type { StatsExploreData, StatsExploreFilter, StatsExploreItem } from '$lib/types';
	import Modal from './Modal.svelte';

	let { title, filter, onClose }: { title: string; filter: StatsExploreFilter; onClose: () => void } = $props();
	let data = $state<StatsExploreData | null>(null);
	let loading = $state(false);
	let failed = $state(false);
	async function load(offset = 0) {
		loading = true;
		failed = false;
		try {
			const next = await api.statsExplore(filter, offset);
			data = { ...next, items: offset && data ? [...data.items, ...next.items] : next.items };
		} catch {
			failed = true;
		} finally {
			loading = false;
		}
	}
	onMount(() => load());

	async function play(item: StatsExploreItem, e?: Event) {
		e?.preventDefault();
		if (item.profile_id && item.profile_id !== session.profileId) await session.switchProfile(item.profile_id);
		onClose();
		goto(`/watch/${item.video_id}${item.category_id ? `?c=${item.category_id}` : ''}`);
	}
</script>

<Modal size="lg" {title} subtitle="Across all profiles · one row per counted record" {onClose}>
	<div class="stack">
		{#if data}
			<p class="small muted" aria-live="polite">Showing {data.items.length.toLocaleString()} of {data.total.toLocaleString()}{filter.day ? ` · ${filter.day}` : ''}. A video can appear in more than one playlist, profile, or attempt.</p>
			{#if !data.items.length}<p class="muted">No records here yet.</p>{/if}
			<ul class="results">
				{#each data.items as item (item.key)}
					<li class="result">
						{#if item.video_id}<img src={api.thumb(item.video_id, 'mq')} alt="" loading="lazy" />{/if}
						<div class="info">
							<strong>{item.title}</strong>
							<div class="small muted meta">
								{#if item.profile_name}<span>{item.profile_name}</span>{/if}
								{#if item.category_name}<span>{item.category_name}</span>{/if}
								{#if item.channel_name}<span>{item.channel_name}</span>{/if}
								{#if item.duration_s}<span>{fmtDuration(item.duration_s)}</span>{/if}
								{#if item.height}<span>{item.height}p</span>{/if}
								{#if item.size_bytes}<span>{fmtBytes(item.size_bytes)}</span>{/if}
								{#if item.score !== null}<span>Score {item.score}</span>{/if}
								{#if item.rating !== null}<span>{item.rating < 0 ? '👎 Disliked' : item.rating > 0 ? '👍 Liked' : 'Feedback'}</span>{/if}
								{#if item.offline}<span class="saved">Saved offline</span>{/if}
							</div>
							{#if item.detail}<p class="small detail">{item.detail}</p>{/if}
							{#if item.original_bytes && item.output_bytes}<span class="small muted">Original {fmtBytes(item.original_bytes)} → encoded {fmtBytes(item.output_bytes)}</span>{/if}
						</div>
						{#if item.video_id}
							<div class="actions">
								{#if item.candidate_id}<button class="btn mini" use:focusable={{ group: `stat-result-${item.key}`, onSelect: () => { onClose(); dialogs.openCandidate(item.candidate_id!); } }}>View verdict</button>{/if}
								<a class="btn mini" href="/watch/{item.video_id}{item.category_id ? `?c=${item.category_id}` : ''}" use:focusable={{ group: `stat-result-${item.key}`, onSelect: (e) => play(item, e) }}>Play</a>
							</div>
						{:else if item.channel_id}
							<a class="btn mini" href="/channel/{item.channel_id}" use:focusable={{ group: `stat-result-${item.key}` }}>View channel</a>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
		{#if loading}<p class="muted" role="status">Loading records…</p>{/if}
		{#if failed}<p class="muted">Could not load these records.</p><button class="btn" use:focusable={{ onSelect: () => load(data?.items.length ?? 0) }}>Try again</button>{/if}
		{#if data && data.items.length < data.total}
			<button class="btn" disabled={loading} use:focusable={{ onSelect: () => load(data!.items.length) }}>Show more</button>
		{/if}
	</div>
	{#snippet footer()}<button class="btn" use:focusable={{ autofocus: true, onSelect: onClose }}>Close</button>{/snippet}
</Modal>

<style>
	.results { display: grid; gap: 0.65rem; list-style: none; padding: 0; margin: 0; }
	.result { display: flex; align-items: center; gap: 1rem; padding: 0.9rem; border: 1px solid var(--line); border-radius: var(--r-md); background: rgba(255,255,255,0.035); }
	.result img { width: 7rem; aspect-ratio: 16/9; object-fit: cover; border-radius: 0.5rem; flex: none; }
	.info { min-width: 0; flex: 1; display: grid; gap: 0.35rem; overflow-wrap: anywhere; }
	.meta { display: flex; flex-wrap: wrap; gap: 0.25rem 0.8rem; }
	.detail { color: var(--muted); white-space: pre-wrap; }
	.saved { color: var(--ok); }
	.actions { display: grid; gap: 0.5rem; flex: none; }
	.mini { min-height: 2.2rem; padding: 0.35rem 0.75rem; font-size: 0.85rem; }
	@media (max-width: 600px) { .result { flex-wrap: wrap; gap: 0.65rem; } .result img { width: 4.8rem; } .actions { width: 100%; display: flex; justify-content: flex-end; } }
</style>
