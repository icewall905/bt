<script lang="ts">
	import '@fontsource-variable/inter';
	import '../app.css';
	import { onMount, type Snippet } from 'svelte';
	import { afterNavigate, beforeNavigate, goto } from '$app/navigation';
	import { page } from '$app/state';
	import { nav } from '$lib/nav';
	import { session } from '$lib/stores/session.svelte';
	import { agent } from '$lib/stores/agent.svelte';
	import { dialogs } from '$lib/stores/dialogs.svelte';
	import TopBar from '$lib/components/TopBar.svelte';
	import Toasts from '$lib/components/Toasts.svelte';
	import OskOverlay from '$lib/components/OskOverlay.svelte';
	import FeedbackDialog from '$lib/components/FeedbackDialog.svelte';
	import AddToCategory from '$lib/components/AddToCategory.svelte';
	import CandidateDrawer from '$lib/components/CandidateDrawer.svelte';
	import ProfilePicker from '$lib/components/ProfilePicker.svelte';
	import Login from '$lib/components/Login.svelte';

	let { children }: { children: Snippet } = $props();
	// SvelteKit keeps a history index in history.state; back only pops entries this app created.
	const histIndex = () => Number((history.state ?? {})['sveltekit:history'] ?? 0);
	let baseIndex = histIndex();

	nav.install();
	nav.backFallback = () => {
		if (page.url.pathname === '/') return;
		if (histIndex() > baseIndex) history.back();
		else goto('/', { replaceState: true });
	};

	beforeNavigate((n) => {
		if (!n.willUnload) nav.beginNavigation();
	});

	afterNavigate((n) => {
		if (n.type === 'enter') baseIndex = histIndex();
		const key = page.url.pathname + page.url.search;
		if (n.type === 'goto' && n.from?.url.pathname === n.to?.url.pathname) nav.setRouteKey(key);
		else nav.setRoute(key);
	});

	onMount(() => {
		session.init();
		agent.start();
	});

	const fullscreen = $derived(page.url.pathname.startsWith('/watch/'));
</script>

{#if !session.ready}
	<div class="splash"><img src="/favicon.svg" alt="" width="96" height="96" /></div>
{:else if session.needsLogin}
	<Login />
{:else}
	{#if !fullscreen}<TopBar />{/if}
	<main class:fullscreen>
		{#key session.version}
			{@render children()}
		{/key}
	</main>
	{#if session.choosing}
		<ProfilePicker fullscreen onClose={() => (session.choosing = false)} />
	{/if}
	{#if dialogs.candidate != null}<CandidateDrawer />{/if}
	{#if dialogs.feedback}<FeedbackDialog />{/if}
	{#if dialogs.addTo}<AddToCategory />{/if}
{/if}
<OskOverlay />
<Toasts />

<style>
	main {
		position: relative;
		z-index: 1;
		padding-bottom: env(safe-area-inset-bottom);
	}
	@media (max-width: 760px) {
		main:not(.fullscreen) {
			padding-bottom: calc(4.5rem + env(safe-area-inset-bottom));
		}
	}
	.splash {
		position: fixed;
		inset: 0;
		display: grid;
		place-items: center;
	}
	.splash img {
		animation: pulse 1.4s ease-in-out infinite;
	}
</style>
