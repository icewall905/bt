<script lang="ts">
	import { focusable } from '$lib/nav';
	import { clamp } from '$lib/util';

	interface Props {
		value: number;
		min: number;
		max: number;
		step?: number;
		label: string;
		hint?: string;
		format?: (v: number) => string;
		group?: string;
		id?: string;
		onchange?: (v: number) => void;
	}
	let { value = $bindable(0), min, max, step = 1, label, hint, format = (v) => String(v), group, id, onchange }: Props = $props();
	const pct = $derived(((value - min) / (max - min)) * 100);

	function set(v: number) {
		const n = clamp(Math.round(v / step) * step, min, max);
		value = Number(n.toFixed(4));
		onchange?.(value);
	}
	let track: HTMLDivElement;
	function onPointer(e: PointerEvent) {
		const r = track.getBoundingClientRect();
		set(min + ((e.clientX - r.left) / r.width) * (max - min));
	}
</script>

<div
	class="slider"
	role="slider"
	aria-label={label}
	aria-valuemin={min}
	aria-valuemax={max}
	aria-valuenow={value}
	tabindex="0"
	use:focusable={{
		group,
		id,
		onKey: (k) => {
			if (k === 'left') return set(value - step), true;
			if (k === 'right') return set(value + step), true;
			return false;
		}
	}}
>
	<div class="top">
		<span class="lbl">{label}</span>
		<span class="val">{format(value)}</span>
	</div>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="track"
		bind:this={track}
		onpointerdown={(e) => {
			track.setPointerCapture(e.pointerId);
			onPointer(e);
		}}
		onpointermove={(e) => e.buttons && onPointer(e)}
	>
		<div class="fill" style:width="{pct}%"></div>
		<div class="thumb" style:left="{pct}%"></div>
	</div>
	{#if hint}<div class="hint">{hint}</div>{/if}
</div>

<style>
	.slider {
		--focus-scale: 1.02;
		display: grid;
		gap: 0.6rem;
		padding: 0.75rem 1rem 0.9rem;
		border-radius: var(--r-md);
		border: 1px solid var(--line);
		background: rgba(255, 255, 255, 0.03);
	}
	.top {
		display: flex;
		justify-content: space-between;
		font-weight: 600;
	}
	.val {
		font-variant-numeric: tabular-nums;
		color: var(--accent);
	}
	.track {
		position: relative;
		height: 0.45rem;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.12);
		cursor: pointer;
		touch-action: none;
	}
	.fill {
		position: absolute;
		inset: 0 auto 0 0;
		border-radius: inherit;
		background: linear-gradient(90deg, var(--ai), var(--accent));
	}
	.thumb {
		position: absolute;
		top: 50%;
		width: 1.2rem;
		height: 1.2rem;
		border-radius: 50%;
		background: #fff;
		transform: translate(-50%, -50%);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
	}
	.hint {
		font-size: 0.8rem;
		color: var(--faint);
	}
</style>
