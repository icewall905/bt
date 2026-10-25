<script lang="ts">
	// Small animated glyph per agent state. Pure SVG + CSS so it stays crisp on a projector.
	let { state, size = '1.4em' }: { state: string; size?: string } = $props();
	const group = $derived(
		({
			searching: 'search',
			planning: 'think',
			fetching: 'search',
			transcript: 'read',
			comments: 'talk',
			judging: 'judge',
			learning: 'think',
			sleeping: 'sleep',
			waiting: 'watch',
			backoff: 'backoff',
			error: 'backoff',
			paused: 'paused',
			offline: 'offline'
		} as Record<string, string>)[state] ?? 'idle'
	);
</script>

<svg class="g {group}" viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
	{#if group === 'search'}
		<g class="orbit"><circle cx="10.5" cy="10.5" r="5.5" fill="none" stroke="currentColor" stroke-width="2.2" /><path d="M15 15l4.5 4.5" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" /></g>
	{:else if group === 'read'}
		<rect x="4" y="3" width="16" height="18" rx="3" fill="none" stroke="currentColor" stroke-width="2" />
		<g class="lines"><path d="M8 8h8M8 12h8M8 16h5" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></g>
	{:else if group === 'talk'}
		<path d="M4 6a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3h-6l-4 4v-4a3 3 0 0 1-3-3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
		<g class="dots"><circle cx="8.5" cy="9.5" r="1.4" fill="currentColor" /><circle cx="12" cy="9.5" r="1.4" fill="currentColor" /><circle cx="15.5" cy="9.5" r="1.4" fill="currentColor" /></g>
	{:else if group === 'judge'}
		<g class="tilt"><path d="M12 4v15M6 19h12M4 8h16" stroke="currentColor" stroke-width="2" stroke-linecap="round" /><path d="M4 8l-2.5 6h5zM20 8l-2.5 6h5z" fill="currentColor" opacity=".85" /></g>
	{:else if group === 'think'}
		<g class="spark"><path d="M12 2l2.2 6.3L20.5 10l-6.3 2.2L12 18.5l-2.2-6.3L3.5 10l6.3-1.7z" fill="currentColor" /></g>
		<circle class="spark2" cx="19" cy="19" r="2" fill="currentColor" />
	{:else if group === 'sleep'}
		<path d="M15.5 3.5A8.5 8.5 0 1 0 20.5 15 7 7 0 0 1 15.5 3.5z" fill="currentColor" opacity=".9" />
		<text class="z" x="17" y="7" font-size="6" font-weight="800" fill="currentColor">z</text>
	{:else if group === 'watch'}
		<path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z" fill="none" stroke="currentColor" stroke-width="2" />
		<circle class="pupil" cx="12" cy="12" r="3" fill="currentColor" />
	{:else if group === 'backoff'}
		<g class="shake"><path d="M7 3h10M7 21h10M8 3c0 5 8 5 8 9s-8 4-8 9M16 3c0 5-8 5-8 9s8 4 8 9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" /></g>
	{:else if group === 'paused'}
		<rect x="6" y="5" width="4" height="14" rx="1.5" fill="currentColor" /><rect x="14" y="5" width="4" height="14" rx="1.5" fill="currentColor" />
	{:else if group === 'offline'}
		<circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="3 3" />
	{:else}
		<circle class="breathe" cx="12" cy="12" r="6" fill="currentColor" />
	{/if}
</svg>

<style>
	.g {
		flex: none;
		overflow: visible;
	}
	.orbit {
		transform-origin: 12px 12px;
		animation: orbit 2.2s ease-in-out infinite;
	}
	.lines {
		animation: scroll 1.6s linear infinite;
	}
	.dots circle {
		animation: blink 1.2s infinite;
	}
	.dots circle:nth-child(2) {
		animation-delay: 0.2s;
	}
	.dots circle:nth-child(3) {
		animation-delay: 0.4s;
	}
	.tilt {
		transform-origin: 12px 6px;
		animation: tilt 1.8s ease-in-out infinite;
	}
	.spark {
		transform-origin: 12px 10px;
		animation: twinkle 1.6s ease-in-out infinite;
	}
	.spark2 {
		animation: blink 1.6s infinite 0.5s;
	}
	.z {
		animation: float 2.4s ease-in-out infinite;
	}
	.pupil {
		animation: look 3s ease-in-out infinite;
	}
	.shake {
		transform-origin: 12px 12px;
		animation: flip 2.4s ease-in-out infinite;
	}
	.breathe {
		transform-origin: 12px 12px;
		animation: breathe 2.6s ease-in-out infinite;
	}
	@keyframes orbit {
		0%,
		100% {
			transform: translate(0, 0);
		}
		25% {
			transform: translate(2px, -1px);
		}
		50% {
			transform: translate(0, -2px);
		}
		75% {
			transform: translate(-2px, -1px);
		}
	}
	@keyframes scroll {
		from {
			transform: translateY(1.5px);
			opacity: 0.6;
		}
		50% {
			opacity: 1;
		}
		to {
			transform: translateY(-1.5px);
			opacity: 0.6;
		}
	}
	@keyframes blink {
		0%,
		100% {
			opacity: 0.25;
		}
		40% {
			opacity: 1;
		}
	}
	@keyframes tilt {
		0%,
		100% {
			transform: rotate(-8deg);
		}
		50% {
			transform: rotate(8deg);
		}
	}
	@keyframes twinkle {
		0%,
		100% {
			transform: scale(0.8) rotate(0);
		}
		50% {
			transform: scale(1.1) rotate(20deg);
		}
	}
	@keyframes float {
		0% {
			transform: translate(0, 2px);
			opacity: 0;
		}
		50% {
			opacity: 1;
		}
		100% {
			transform: translate(2px, -3px);
			opacity: 0;
		}
	}
	@keyframes look {
		0%,
		100% {
			transform: translateX(-1.5px);
		}
		50% {
			transform: translateX(1.5px);
		}
	}
	@keyframes flip {
		0%,
		40% {
			transform: rotate(0);
		}
		50%,
		90% {
			transform: rotate(180deg);
		}
		100% {
			transform: rotate(360deg);
		}
	}
	@keyframes breathe {
		0%,
		100% {
			transform: scale(0.6);
			opacity: 0.6;
		}
		50% {
			transform: scale(1);
			opacity: 1;
		}
	}
</style>
