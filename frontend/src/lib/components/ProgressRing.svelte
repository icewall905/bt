<script lang="ts">
	let { value, size = '1.15rem', label }: { value: number; size?: string; label?: string } = $props();
	const C = 2 * Math.PI * 9;
</script>

<svg class="ring" viewBox="0 0 24 24" width={size} height={size} role="img" aria-label={label ?? `${Math.round(value * 100)}%`}>
	<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-opacity="0.25" stroke-width="3" />
	<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-dasharray={C} stroke-dashoffset={C * (1 - Math.max(0.02, Math.min(1, value)))} transform="rotate(-90 12 12)" />
</svg>

<style>
	.ring {
		flex: none;
		color: var(--ok);
	}
	.ring circle:last-child {
		transition: stroke-dashoffset 0.6s ease;
	}
</style>
