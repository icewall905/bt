<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { nav, focusable } from '$lib/nav';
	import Section from './Section.svelte';

	interface K {
		key: string;
		code: string;
		keyCode: number;
		action: string;
		at: number;
	}
	let keys = $state<K[]>([]);
	let capture = $state(false);
	let backs: number[] = [];
	let idle: ReturnType<typeof setTimeout> | null = null;

	const ACTION: Record<string, string> = {
		ArrowUp: 'Move up', ArrowDown: 'Move down', ArrowLeft: 'Move left', ArrowRight: 'Move right',
		Enter: 'Select (OK)', NumpadEnter: 'Select (OK)', Backspace: 'Back', Escape: 'Back', BrowserBack: 'Back',
		' ': 'Play / pause', MediaPlayPause: 'Play / pause', MediaTrackNext: 'Next video', MediaTrackPrevious: 'Restart video',
		MediaFastForward: 'Forward 30 s', MediaRewind: 'Back 30 s', AudioVolumeUp: 'Volume (system)', AudioVolumeDown: 'Volume (system)', AudioVolumeMute: 'Mute (system)'
	};

	let offRaw: (() => void) | null = null;
	let offCap: (() => void) | null = null;
	onMount(() => {
		offRaw = nav.onRawKey((e) => {
			keys = [{ key: e.key, code: e.code, keyCode: e.keyCode, action: ACTION[e.key] ?? (e.key.length === 1 ? 'Types a character' : 'Not used'), at: Date.now() }, ...keys].slice(0, 12);
			if (capture) {
				if (idle) clearTimeout(idle);
				idle = setTimeout(stop, 20000);
				if (ACTION[e.key] === 'Back') {
					backs = [...backs.filter((t) => Date.now() - t < 1500), Date.now()];
					if (backs.length >= 3) stop();
				}
			}
		});
	});
	onDestroy(() => {
		offRaw?.();
		offCap?.();
		if (idle) clearTimeout(idle);
	});

	function start() {
		capture = true;
		backs = [];
		offCap = nav.handleKeys(() => true);
		idle = setTimeout(stop, 20000);
	}
	function stop() {
		capture = false;
		// Defer unhooking: raw key listeners run first in the engine's handler, so the
		// Back press that stops capture would otherwise fall through and navigate.
		const off = offCap;
		offCap = null;
		if (off) setTimeout(off, 0);
		if (idle) clearTimeout(idle);
	}
	const last = $derived(keys[0]);
</script>

<Section title="Remote and keys" intro="Press buttons on the remote to see what the browser receives. Useful when setting up a new remote or input-remapper.">
	<div class="big panel" class:cap={capture}>
		{#if last}
			<div class="k">{last.key === ' ' ? 'Space' : last.key}</div>
			<div class="meta">
				<span>code <strong>{last.code || '–'}</strong></span>
				<span>keyCode <strong>{last.keyCode}</strong></span>
				<span>does <strong>{last.action}</strong></span>
			</div>
		{:else}
			<div class="k faint">Press a key</div>
		{/if}
	</div>
	<div class="hstack">
		<!-- The button stays mounted while capturing so focus has somewhere to stay. -->
		<button class="btn" class:primary={!capture} use:focusable={{ group: 'keys', id: 'keys-capture', onSelect: () => (capture ? stop() : start()) }}>
			{capture ? 'Stop capturing' : 'Capture all keys'}
		</button>
		{#if capture}
			<p class="small warn">Capturing: buttons do nothing else. Press Back three times quickly, or wait 20 seconds, to stop.</p>
		{:else}
			<p class="small faint">Without capture, keys still work normally while being shown here.</p>
		{/if}
	</div>
	{#if keys.length > 1}
		<ol class="hist">
			{#each keys.slice(1) as k}
				<li><span class="kk">{k.key === ' ' ? 'Space' : k.key}</span><span class="faint">{k.code}</span><span class="muted">{k.action}</span></li>
			{/each}
		</ol>
	{/if}
	<div class="panel small muted map">
		<strong>Default mapping:</strong> arrows move, OK/Enter selects, Back/Backspace/Escape goes back, Space or Play/Pause toggles playback, Next/Previous track skip videos. In the player, Left/Right on the seek bar jump 10 seconds and Down opens details.
	</div>
</Section>

<style>
	.big {
		display: grid;
		place-items: center;
		gap: 1rem;
		min-height: 12rem;
		text-align: center;
		transition: border-color 0.2s;
	}
	.big.cap {
		border-color: var(--accent);
	}
	.k {
		font-size: clamp(2.5rem, 5vw, 5rem);
		font-weight: 800;
		letter-spacing: -0.03em;
	}
	.meta {
		display: flex;
		gap: 1.5rem;
		flex-wrap: wrap;
		justify-content: center;
		color: var(--muted);
	}
	.warn {
		color: var(--accent-2);
	}
	.hist {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.3rem;
	}
	.hist li {
		display: grid;
		grid-template-columns: 10rem 10rem 1fr;
		gap: 1rem;
		padding: 0.35rem 0.8rem;
		border-radius: var(--r-sm);
		background: rgba(255, 255, 255, 0.03);
		font-size: 0.9rem;
	}
	.kk {
		font-weight: 700;
	}
	.map {
		line-height: 1.6;
	}
</style>
