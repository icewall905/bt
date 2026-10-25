<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { toast } from '$lib/stores/toast.svelte';
	import { focusable } from '$lib/nav';
	import type { ChannelEntry, Video } from '$lib/types';
	import VideoCard from '$lib/components/VideoCard.svelte';
	import TextField from '$lib/components/form/TextField.svelte';

	let channels = $state<ChannelEntry[] | null>(null);
	let latest = $state<Video[] | null>(null);
	let ref = $state('');

	async function load() {
		const [c, home] = await Promise.all([api.channels().catch(() => []), api.home(40).catch(() => [])]);
		channels = c;
		latest = (home.find((r) => r.kind === 'subscriptions')?.items ?? []).map((i) => i.video!).filter(Boolean);
	}
	onMount(load);

	const subs = $derived((channels ?? []).filter((c) => c.subscribed));
	const blocked = $derived((channels ?? []).filter((c) => c.blocked));

	async function unblock(c: ChannelEntry) {
		await api.putChannel(c.id, { blocked: false });
		toast.success(`Unblocked ${c.name || c.id}`);
		load();
	}
	function open() {
		const r = ref.trim();
		if (!r) return;
		goto(`/channel/${encodeURIComponent(r.replace(/^https?:\/\/(www\.)?youtube\.com\//, ''))}`);
	}
</script>

<svelte:head><title>Subscriptions · BetterTube</title></svelte:head>

<div class="page stack" style="gap:2.2rem">
	<header class="head">
		<h1>Subscriptions</h1>
		<p class="muted">Channels you follow here stay on this server. Nothing is sent to a YouTube account. New uploads also feed the AI.</p>
	</header>

	<section class="stack">
		<div class="hstack"><h2>Your channels</h2><span class="faint small">{subs.length}</span></div>
		{#if channels === null}
			<div class="chans">{#each Array(6) as _}<div class="skeleton" style="height:9rem"></div>{/each}</div>
		{:else if subs.length === 0}
			<p class="muted">No subscriptions yet. Open a channel from any video's details and press Subscribe, or add one below.</p>
		{:else}
			<div class="chans">
				{#each subs as c (c.id)}
					<a class="chan" href="/channel/{c.id}" use:focusable={{ group: 'chans', id: `chan-${c.id}` }}>
						<img src={api.channelAvatar(c.id)} alt="" loading="lazy" onerror={(e) => ((e.currentTarget as HTMLImageElement).style.opacity = '0')} />
						<span class="n">{c.name || c.handle || c.id}</span>
					</a>
				{/each}
			</div>
		{/if}
		<form class="add" onsubmit={(e) => (e.preventDefault(), open())}>
			<TextField bind:value={ref} placeholder="@handle, channel ID or URL" label="Open a channel" onsubmit={open} group="add-chan" />
			<button class="btn" type="submit" use:focusable={{ group: 'add-chan' }}>Open</button>
		</form>
	</section>

	<section class="stack">
		<h2>New from subscriptions</h2>
		{#if latest === null}
			<div class="grid-cards">{#each Array(4) as _}<div class="skeleton" style="aspect-ratio:16/10"></div>{/each}</div>
		{:else if latest.length === 0}
			<p class="muted">Nothing new yet. The AI checks your channels' feeds in the background.</p>
		{:else}
			<div class="grid-cards" data-nav-center>
				{#each latest as v (v.id)}<VideoCard video={v} size="grid" group="latest" />{/each}
			</div>
		{/if}
	</section>

	{#if blocked.length}
		<section class="stack">
			<h2>Blocked channels</h2>
			<p class="muted small">The AI never suggests videos from these.</p>
			<div class="blocked">
				{#each blocked as c (c.id)}
					<div class="brow">
						<span>{c.name || c.handle || c.id}</span>
						<button class="btn" use:focusable={{ group: 'blocked', onSelect: () => unblock(c) }}>Unblock</button>
					</div>
				{/each}
			</div>
		</section>
	{/if}
</div>

<style>
	.head {
		display: grid;
		gap: 0.5rem;
		padding-top: 1rem;
	}
	.chans {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
		gap: 1rem;
	}
	.chan {
		--focus-scale: 1.07;
		display: grid;
		justify-items: center;
		gap: 0.6rem;
		padding: 1rem 0.6rem;
		border-radius: var(--r-lg);
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid var(--line);
		text-align: center;
	}
	.chan img {
		width: 5rem;
		height: 5rem;
		border-radius: 50%;
		object-fit: cover;
		background: var(--surface-2);
	}
	.n {
		font-weight: 600;
		font-size: 0.9rem;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 100%;
		white-space: nowrap;
	}
	.add {
		display: flex;
		gap: 0.75rem;
		align-items: end;
		max-width: 40rem;
	}
	.add :global(.field) {
		flex: 1;
	}
	.blocked {
		display: grid;
		gap: 0.5rem;
		max-width: 40rem;
	}
	.brow {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.6rem 0.6rem 0.6rem 1rem;
		border-radius: var(--r-md);
		background: rgba(255, 255, 255, 0.04);
	}
</style>
