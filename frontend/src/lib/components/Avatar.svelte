<script lang="ts">
	let { emoji, color, size = '2.6rem' }: { emoji: string; color: string; size?: string } = $props();
</script>

<span class="av" style:--c={color} style:--s={size} aria-hidden="true">{emoji}</span>

<style>
	.av {
		display: inline-grid;
		place-items: center;
		flex: none;
		width: var(--s);
		height: var(--s);
		border-radius: 50%;
		font-size: calc(var(--s) * 0.52);
		line-height: 1;
		background: radial-gradient(circle at 30% 25%, color-mix(in srgb, var(--c) 70%, white), var(--c) 55%, color-mix(in srgb, var(--c) 60%, black));
		box-shadow:
			inset 0 -3px 8px rgba(0, 0, 0, 0.25),
			0 4px 14px -4px color-mix(in srgb, var(--c) 70%, transparent);
	}
</style>
