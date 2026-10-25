<script lang="ts">
	import { focusable } from '$lib/nav';
	import { clamp } from '$lib/util';

	interface Props {
		value: number;
		label: string;
		hint?: string;
		min?: number;
		max?: number;
		step?: number;
		format?: (v: number) => string;
		group?: string;
		id?: string;
		onchange?: (v: number) => void;
	}
	let { value = $bindable(0), label, hint, min = 0, max = 1e9, step = 1, format = (v) => String(v), group, id, onchange }: Props = $props();
	function set(v: number) {
		value = clamp(Number(v.toFixed(3)), min, max);
		onchange?.(value);
	}
</script>

<div
	class="stepper"
	role="spinbutton"
	aria-label={label}
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
	<span class="text">
		<span class="lbl">{label}</span>
		{#if hint}<span class="hint">{hint}</span>{/if}
	</span>
	<button class="b" tabindex="-1" aria-label="Decrease" onclick={() => set(value - step)}>−</button>
	<span class="val">{format(value)}</span>
	<button class="b" tabindex="-1" aria-label="Increase" onclick={() => set(value + step)}>+</button>
</div>

<style>
	.stepper {
		--focus-scale: 1.02;
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.6rem 0.75rem 0.6rem 1rem;
		border-radius: var(--r-md);
		border: 1px solid var(--line);
		background: rgba(255, 255, 255, 0.03);
	}
	.text {
		flex: 1;
		display: grid;
		gap: 0.15rem;
	}
	.lbl {
		font-weight: 600;
	}
	.hint {
		font-size: 0.8rem;
		color: var(--faint);
	}
	.val {
		min-width: 4.5rem;
		text-align: center;
		font-weight: 700;
		color: var(--accent);
		font-variant-numeric: tabular-nums;
	}
	.b {
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 50%;
		border: 1px solid var(--line-strong);
		background: var(--surface-2);
		cursor: pointer;
		font-size: 1.1rem;
	}
</style>
