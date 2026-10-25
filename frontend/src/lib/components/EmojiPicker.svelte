<script lang="ts">
	import { focusable } from '$lib/nav';

	let { value = $bindable('🙂'), choices, group = 'emoji' }: { value: string; choices?: string[]; group?: string } = $props();
	const DEFAULT = [
		'🙂', '😎', '🤓', '🥳', '😺', '🐶', '🦊', '🐼', '🐸', '🦄', '🐙', '🦖',
		'🚀', '🔬', '🧪', '🎨', '🎵', '🎮', '⚽', '🏀', '🍕', '🌮', '🌍', '🌋',
		'📚', '🧠', '🛠️', '🎬', '🌟', '✨', '🔥', '🌈', '🏠', '👶', '👧', '👦',
		'👩', '👨', '👵', '👴', '🐱', '🐻', '🦁', '🐧', '🌸', '🍿', '🧩', '🪐'
	];
	const list = $derived(choices ?? DEFAULT);
	const COLS = 12;
</script>

<div class="emojis" role="radiogroup" aria-label="Emoji">
	{#each list as e, i}
		<button
			class="e"
			role="radio"
			aria-checked={value === e}
			class:sel={value === e}
			use:focusable={{ group: `${group}-${Math.floor(i / COLS)}`, onSelect: () => (value = e), scroll: 'nearest', memory: false }}>{e}</button
		>
	{/each}
</div>

<style>
	.emojis {
		display: grid;
		grid-template-columns: repeat(12, 1fr);
		gap: 0.3rem;
	}
	@media (max-width: 600px) {
		.emojis {
			grid-template-columns: repeat(8, 1fr);
		}
	}
	.e {
		--focus-scale: 1.2;
		aspect-ratio: 1;
		font-size: 1.35rem;
		border-radius: var(--r-sm);
		border: 1px solid transparent;
		background: rgba(255, 255, 255, 0.04);
		cursor: pointer;
		display: grid;
		place-items: center;
		padding: 0;
	}
	.e.sel {
		border-color: var(--accent);
		background: rgba(255, 181, 71, 0.15);
	}
</style>
