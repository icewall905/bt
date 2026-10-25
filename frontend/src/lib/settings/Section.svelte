<script lang="ts">
	import type { Snippet } from 'svelte';
	let { title, intro, children, actions }: { title: string; intro?: string; children: Snippet; actions?: Snippet } = $props();
</script>

<section class="sec">
	<header>
		<div>
			<h2>{title}</h2>
			{#if intro}<p class="muted">{intro}</p>{/if}
		</div>
		{#if actions}<div class="acts">{@render actions()}</div>{/if}
	</header>
	<div class="body">{@render children()}</div>
</section>

<style>
	.sec {
		display: grid;
		gap: 1.2rem;
	}
	header {
		display: flex;
		gap: 1rem;
		align-items: flex-end;
		justify-content: space-between;
		flex-wrap: wrap;
	}
	header > div {
		display: grid;
		gap: 0.4rem;
		max-width: 46rem;
	}
	.acts {
		display: flex;
		gap: 0.6rem;
		flex-wrap: wrap;
	}
	.body {
		display: grid;
		gap: 0.75rem;
	}
</style>
