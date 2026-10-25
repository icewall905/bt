<script lang="ts">
	import { page } from '$app/state';
	import { api, ApiError } from '$lib/api';
	import { toast } from '$lib/stores/toast.svelte';
	import { session } from '$lib/stores/session.svelte';
	import { focusable } from '$lib/nav';
	import type { ChannelInfo, Video } from '$lib/types';
	import VideoCard from '$lib/components/VideoCard.svelte';

	const ref = $derived(page.params.id ?? '');
	let ch = $state<ChannelInfo | null>(null);
	let videos = $state<Video[] | null>(null);
	let error = $state('');

	$effect(() => {
		const r = ref;
		ch = null;
		videos = null;
		error = '';
		api.channel(r).then(
			(d) => {
				ch = d.channel;
				videos = session.settings?.extras.hide_shorts ? d.videos.filter((v) => !v.is_short) : d.videos;
			},
			(e) => {
				error = e instanceof ApiError && e.status === 503 ? 'YouTube is blocking requests from the server right now.' : 'This channel could not be loaded.';
				videos = [];
			}
		);
	});

	async function set(body: { subscribed?: boolean; blocked?: boolean }) {
		if (!ch?.id) return;
		const r = await api.putChannel(ch.id, { ...body, name: ch.name, handle: ch.handle, avatar: ch.avatar_src });
		ch = { ...ch, subscribed: r.subscribed, blocked: r.blocked };
		toast.success(body.blocked !== undefined ? (r.blocked ? `Blocked ${ch.name}` : `Unblocked ${ch.name}`) : r.subscribed ? `Subscribed to ${ch.name}` : `Unsubscribed from ${ch.name}`);
	}
</script>

<svelte:head><title>{ch?.name ?? 'Channel'} · BetterTube</title></svelte:head>

<div class="page">
	<header class="head">
		{#if ch?.id}
			<img class="av" src={api.channelAvatar(ch.id)} alt="" onerror={(e) => ((e.currentTarget as HTMLImageElement).style.opacity = '0')} />
		{:else}
			<div class="av skeleton"></div>
		{/if}
		<div class="t">
			<h1>{ch?.name ?? (error ? 'Channel' : '…')}</h1>
			{#if ch?.handle}<p class="muted">{ch.handle}</p>{/if}
		</div>
		{#if ch?.id}
			<div class="hstack">
				<button class="btn" class:primary={!ch.subscribed} use:focusable={{ group: 'ch-acts', autofocus: true, onSelect: () => set({ subscribed: !ch!.subscribed }) }}>
					{ch.subscribed ? '✓ Subscribed' : 'Subscribe'}
				</button>
				<button class="btn danger" use:focusable={{ group: 'ch-acts', onSelect: () => set({ blocked: !ch!.blocked }) }}>{ch.blocked ? 'Unblock' : 'Block'}</button>
			</div>
		{/if}
	</header>
	{#if error}
		<div class="empty"><span class="big-emoji">📡</span><p>{error}</p></div>
	{:else if videos === null}
		<div class="grid-cards">{#each Array(8) as _}<div class="skeleton" style="aspect-ratio:16/10"></div>{/each}</div>
	{:else}
		<div class="grid-cards" data-nav-center>
			{#each videos as v (v.id)}<VideoCard video={v} size="grid" group="ch-videos" />{/each}
		</div>
	{/if}
</div>

<style>
	.head {
		display: flex;
		align-items: center;
		gap: 1.4rem;
		flex-wrap: wrap;
		padding: 1rem 0 2rem;
	}
	.av {
		width: clamp(4.5rem, 6vw, 7rem);
		height: clamp(4.5rem, 6vw, 7rem);
		border-radius: 50%;
		object-fit: cover;
		background: var(--surface-2);
	}
	.t {
		flex: 1;
		min-width: 12rem;
		display: grid;
		gap: 0.3rem;
	}
</style>
