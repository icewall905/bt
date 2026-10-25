<script lang="ts">
	import Section from './Section.svelte';
	import SaveBar from './SaveBar.svelte';
	import { SettingsDraft } from './useSettings.svelte';
	import Select from '$lib/components/form/Select.svelte';
	import Toggle from '$lib/components/form/Toggle.svelte';

	const d = new SettingsDraft('player');
	const HEIGHTS = [480, 720, 1080, 1440, 2160].map((h) => ({ value: h, label: `${h}p`, hint: h === 1080 ? 'Best for the projector' : h > 1080 ? 'Needs a fast CPU or GPU decoding' : undefined }));
	const CODECS = [
		{ value: 'avc1', label: 'H.264', hint: 'Plays everywhere, lightest on the CPU. Recommended.' },
		{ value: 'vp9', label: 'VP9', hint: 'Better picture per bit, heavier to decode.' },
		{ value: 'av01', label: 'AV1', hint: 'Newest and most efficient, needs hardware support.' }
	];
	const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2].map((s) => ({ value: s, label: s === 1 ? 'Normal' : `${s}×` }));
	const LANGS = [
		{ value: '', label: 'Off' },
		{ value: 'en', label: 'English' },
		{ value: 'da', label: 'Danish' },
		{ value: 'de', label: 'German' },
		{ value: 'sv', label: 'Swedish' },
		{ value: 'no', label: 'Norwegian' },
		{ value: 'fr', label: 'French' },
		{ value: 'es', label: 'Spanish' }
	];
</script>

<Section title="Player" intro="How videos play on this server, for everyone.">
	<Select label="Maximum quality" hint="Higher quality uses more bandwidth through the server." bind:value={d.value.max_height} options={HEIGHTS} />
	<Select label="Preferred video format" bind:value={d.value.prefer_codec} options={CODECS} />
	<Select label="Default speed" bind:value={d.value.default_speed} options={SPEEDS} />
	<Select label="Captions" hint="Turn captions on automatically in this language when available." bind:value={d.value.captions_lang} options={LANGS} />
	<Toggle label="Autoplay next" hint="When a video ends, play the next pick from the same category after a 10 second countdown." bind:checked={d.value.autoplay_next} />
	<SaveBar dirty={d.dirty} busy={d.busy} onsave={() => d.save('Player settings saved')} onreset={() => d.reset()} />
</Section>
