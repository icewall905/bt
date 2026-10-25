<script lang="ts">
	import Section from './Section.svelte';
	import SaveBar from './SaveBar.svelte';
	import { SettingsDraft } from './useSettings.svelte';
	import Select from '$lib/components/form/Select.svelte';
	import Toggle from '$lib/components/form/Toggle.svelte';
	import Slider from '$lib/components/form/Slider.svelte';
	import { SB_COLORS, SB_LABELS } from '$lib/util';
	import type { SbAction } from '$lib/types';

	const d = new SettingsDraft('sponsorblock');
	const ACTIONS: { value: SbAction; label: string; hint: string }[] = [
		{ value: 'skip', label: 'Skip automatically', hint: 'Jumps over it and shows a short note.' },
		{ value: 'ask', label: 'Ask me', hint: 'Shows a Skip button. Press OK to skip.' },
		{ value: 'show', label: 'Mark on the bar', hint: 'Coloured section on the seek bar only.' },
		{ value: 'off', label: 'Ignore', hint: 'Not shown at all.' }
	];
	const DESC: Record<string, string> = {
		sponsor: 'Paid promotion and ad reads',
		selfpromo: 'Merch, Patreon, shout-outs to their other channels',
		interaction: '"Like and subscribe" reminders',
		intro: 'Intro animations and openers without content',
		outro: 'End cards and credits',
		preview: 'Recaps and "coming up" previews',
		filler: 'Off-topic tangents and jokes',
		music_offtopic: 'Non-music parts in music videos',
		poi_highlight: 'The part most people came for'
	};
</script>

<Section title="SponsorBlock" intro="Community-submitted segment times from sponsor.ajay.app. Lookups are anonymous: the server sends only a short hash prefix of the video ID.">
	<Toggle label="Use SponsorBlock" bind:checked={d.value.enabled} />
	{#if d.value.enabled}
		<div class="cats">
			{#each Object.keys(d.value.categories ?? {}) as k}
				<div class="cat" style:--c={SB_COLORS[k] ?? '#fff'}>
					<span class="sw"></span>
					<div class="grow">
						<Select label={SB_LABELS[k] ?? k} hint={DESC[k]} bind:value={d.value.categories[k]} options={ACTIONS} group="sb-{k}" />
					</div>
				</div>
			{/each}
		</div>
		<Slider label="Ignore tiny segments" hint="Segments shorter than this are not skipped." bind:value={d.value.min_segment_s} min={0} max={10} step={0.5} format={(v) => `${v} s`} />
	{/if}
	<SaveBar dirty={d.dirty} busy={d.busy} onsave={() => d.save('SponsorBlock settings saved')} onreset={() => d.reset()} />
</Section>

<style>
	.cats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 26rem), 1fr));
		gap: 0.6rem;
	}
	.cat {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.sw {
		width: 0.5rem;
		align-self: stretch;
		border-radius: 1rem;
		background: var(--c);
	}
	.grow {
		flex: 1;
	}
</style>
