<script lang="ts">
	import Section from './Section.svelte';
	import SaveBar from './SaveBar.svelte';
	import { SettingsDraft } from './useSettings.svelte';
	import Toggle from '$lib/components/form/Toggle.svelte';

	const d = new SettingsDraft('extras');
</script>

<Section title="Extras" intro="Small community add-ons. Each one makes an anonymous request from the server, never from your browser.">
	<Toggle label="Hide Shorts" hint="Keep vertical clips under a minute out of search results, feeds and the AI's picks." bind:checked={d.value.hide_shorts} />
	<Toggle label="Show dislike counts" hint="Estimated dislikes from Return YouTube Dislike." bind:checked={d.value.ryd} />
	<Toggle label="Better titles (DeArrow)" hint="Replace clickbait titles with community-written ones when available." bind:checked={d.value.dearrow} />
	<SaveBar dirty={d.dirty} busy={d.busy} onsave={() => d.save('Extras saved')} onreset={() => d.reset()} />
</Section>
