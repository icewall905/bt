<script lang="ts">
	import type { Snippet } from 'svelte';
	import { focusable } from '$lib/nav';

	interface Props {
		title: string;
		emoji?: string;
		color?: string;
		badge?: string;
		href?: string;
		children: Snippet;
		aside?: Snippet;
	}
	let { title, emoji, color, badge, href, children, aside }: Props = $props();
</script>

<section class="row" style:--cat={color ?? 'var(--ai)'}>
	<header>
		<h2>
			{#if href}
				<a class="t" href={href} use:focusable={{ group: `head-${href}`, id: `head-${href}` }}>
					{#if emoji}<span class="emo">{emoji}</span>{/if}
					<span>{title}</span>
				</a>
			{:else}
				{#if emoji}<span class="emo">{emoji}</span>{/if}
				<span>{title}</span>
			{/if}
		</h2>
		{#if badge}<span class="badge">{badge}</span>{/if}
		<span class="spacer"></span>
		{#if aside}{@render aside()}{/if}
	</header>
	<div class="scroller" data-nav-row>
		{@render children()}
	</div>
</section>

<style>
	.row {
		display: grid;
		gap: 0.6rem;
		margin-top: clamp(1.25rem, 2.2vw, 2.6rem);
	}
	header {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		padding: 0 var(--gutter);
	}
	h2 {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	h2 .t {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		color: inherit;
		text-decoration: none;
	}
	h2 .t:hover span:not(.emo) {
		text-decoration: underline;
		text-decoration-color: var(--cat);
		text-underline-offset: 0.35rem;
	}
	h2::before {
		content: '';
		width: 0.3rem;
		height: 1.1em;
		border-radius: 1rem;
		background: var(--cat);
		box-shadow: 0 0 14px var(--cat);
	}
	.emo {
		font-size: 0.95em;
	}
	.badge {
		font-size: 0.78rem;
		font-weight: 650;
		padding: 0.2rem 0.65rem;
		border-radius: var(--r-pill);
		color: color-mix(in srgb, var(--cat) 60%, white);
		background: color-mix(in srgb, var(--cat) 16%, transparent);
		border: 1px solid color-mix(in srgb, var(--cat) 40%, transparent);
	}
	.scroller {
		display: flex;
		gap: clamp(0.9rem, 1.3vw, 1.6rem);
		overflow-x: auto;
		overflow-y: visible;
		padding: 1.1rem var(--gutter) 1.6rem;
		margin: -0.6rem 0 -1rem;
		scroll-padding: 0 var(--gutter);
		scrollbar-width: none;
		overscroll-behavior-x: contain;
	}
	.scroller::-webkit-scrollbar {
		display: none;
	}
</style>
