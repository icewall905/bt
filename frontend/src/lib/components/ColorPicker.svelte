<script lang="ts">
	import { focusable } from '$lib/nav';
	import { PALETTE } from '$lib/util';

	let { value = $bindable('#7c5cff'), group = 'colors' }: { value: string; group?: string } = $props();
</script>

<div class="colors" role="radiogroup" aria-label="Colour">
	{#each PALETTE as c}
		<button
			class="c"
			role="radio"
			aria-checked={value === c}
			aria-label={c}
			class:sel={value.toLowerCase() === c}
			style:--c={c}
			use:focusable={{ group, onSelect: () => (value = c), scroll: 'nearest' }}
		></button>
	{/each}
</div>

<style>
	.colors {
		display: flex;
		flex-wrap: wrap;
		gap: 0.55rem;
	}
	.c {
		--focus-scale: 1.2;
		width: 2.3rem;
		height: 2.3rem;
		border-radius: 50%;
		background: var(--c);
		border: 3px solid transparent;
		cursor: pointer;
		padding: 0;
	}
	.c.sel {
		border-color: #fff;
	}
</style>
