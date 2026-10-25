<script lang="ts">
	import { focusable } from '$lib/nav';

	interface Props {
		value: string;
		label?: string;
		hint?: string;
		placeholder?: string;
		multiline?: boolean;
		type?: 'text' | 'password' | 'url' | 'search' | 'number';
		rows?: number;
		id?: string;
		group?: string;
		autofocus?: boolean;
		onsubmit?: () => void;
		oninput?: (v: string) => void;
	}
	let { value = $bindable(''), label, hint, placeholder = '', multiline = false, type = 'text', rows = 5, id, group, autofocus, onsubmit, oninput }: Props = $props();

	function onInput(e: Event) {
		value = (e.currentTarget as HTMLInputElement).value;
		oninput?.(value);
	}
</script>

<label class="field">
	{#if label}<span class="label">{label}</span>{/if}
	{#if multiline}
		<textarea
			class="input"
			{rows}
			{placeholder}
			aria-label={label ?? placeholder}
			{value}
			oninput={onInput}
			use:focusable={{ id, group, autofocus, label: label ?? placeholder }}
		></textarea>
	{:else}
		<input
			class="input"
			{type}
			{placeholder}
			aria-label={label ?? placeholder}
			{value}
			oninput={onInput}
			onosksubmit={() => onsubmit?.()}
			use:focusable={{ id, group, autofocus, label: label ?? placeholder, onSelect: onsubmit }}
		/>
	{/if}
	{#if hint}<span class="hint">{hint}</span>{/if}
</label>
