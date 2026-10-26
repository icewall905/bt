<script lang="ts">
	import { api } from '$lib/api';
	import { focusable } from '$lib/nav';
	import { agent, STATE_LABEL } from '$lib/stores/agent.svelte';
	import type { LlmTestResult } from '$lib/types';
	import Section from './Section.svelte';
	import SaveBar from './SaveBar.svelte';
	import { SettingsDraft } from './useSettings.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import Toggle from '$lib/components/form/Toggle.svelte';
	import Slider from '$lib/components/form/Slider.svelte';
	import Stepper from '$lib/components/form/Stepper.svelte';

	const llm = new SettingsDraft('llm');
	const ag = new SettingsDraft('agent');
	const th = new SettingsDraft('throttle');

	let testing = $state(false);
	let result = $state<LlmTestResult | null>(null);
	let tookMs = $state(0);

	async function test() {
		testing = true;
		result = null;
		const t0 = performance.now();
		try {
			result = await api.llmTest({ base_url: llm.value.base_url, model: llm.value.model, api_key: llm.value.api_key });
		} catch (e) {
			result = { ok: false, error: (e as Error).message };
		} finally {
			tookMs = Math.round(performance.now() - t0);
			testing = false;
		}
	}

	const mins = (s: number) => (s >= 3600 ? `${(s / 3600).toFixed(s % 3600 ? 1 : 0)} h` : s >= 60 ? `${Math.round(s / 60)} min` : `${s} s`);
	const perHourAvg = $derived(Math.round(3600 / Math.max(1, (th.value.min_delay_s + th.value.max_delay_s) / 2)));
</script>

<Section title="AI model" intro="BetterTube talks to any OpenAI-compatible server: llama.cpp, Ollama, vLLM, LM Studio or a hosted API. The model reads transcripts and comments, so a long context window helps.">
	<div class="conn panel">
		<TextField label="Server URL" hint="Ends in /v1 for most servers." bind:value={llm.value.base_url} placeholder="http://10.0.10.23:8080/v1" type="url" group="llm-url" id="llm-url" />
		<div class="two">
			<TextField label="Model" hint="Pick one from the test results below, or type its name." bind:value={llm.value.model} placeholder="currentmodel" group="llm-model" />
			<TextField label="API key" hint="Leave empty for local servers. Stored on the server, never shown again." type="password" bind:value={llm.value.api_key} placeholder="none" group="llm-model" />
		</div>
		<div class="test-row">
			<button class="btn primary big" disabled={testing} use:focusable={{ group: 'llm-test', id: 'llm-test', onSelect: test }}>
				{#if testing}<span class="spin"></span> Testing…{:else}Test connection{/if}
			</button>
			<p class="small faint">Lists the server's models and asks the selected model to reply "pong". Uses the values above, even before you save.</p>
		</div>
		{#if result}
			<div class="result" class:ok={result.ok} class:bad={!result.ok} role="status">
				{#if result.ok}
					<div class="rh"><span class="big">✓</span><div><strong>Connected</strong><div class="small muted">Answered in {(tookMs / 1000).toFixed(1)} s</div></div></div>
					<div class="reply"><span class="small faint">Model replied</span><code>{result.reply || '(empty reply)'}</code></div>
				{:else}
					<div class="rh"><span class="big">✕</span><div><strong>Could not reach the model</strong><div class="small muted">After {(tookMs / 1000).toFixed(1)} s</div></div></div>
					<code class="err">{result.error}</code>
					<p class="small muted">Check the URL (including /v1), that the server is running and reachable from the BetterTube container, and the model name.</p>
				{/if}
				{#if result.models?.length}
					<div class="models">
						<span class="small faint">Models on this server (select to use)</span>
						<div class="hstack">
							{#each result.models as m}
								<button class="chip" class:on={m === llm.value.model} use:focusable={{ group: 'llm-models', onSelect: () => (llm.value.model = m) }}>{m}</button>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
	<div class="one">
		<Toggle label="Model can see images" hint="Send each thumbnail to the model too. Turn off for text-only models." bind:checked={llm.value.vision} />
		<Stepper label="Timeout" hint="How long to wait for one answer." bind:value={llm.value.timeout_s} min={30} max={1800} step={30} format={(v) => mins(v)} />
	</div>
	<Slider label="Creativity" hint="Temperature. Low keeps verdicts consistent; higher gives more varied search ideas." bind:value={llm.value.temperature} min={0} max={1.5} step={0.05} format={(v) => v.toFixed(2)} />
	<SaveBar dirty={llm.dirty} busy={llm.busy} onsave={() => llm.save('AI model settings saved')} onreset={() => llm.reset()} />
</Section>

<div class="gap"></div>

<Section title="Curator" intro="The background worker that searches, reads and judges videos for every profile's categories.">
	<div class="status small muted">Right now: <strong>{STATE_LABEL[agent.effective] ?? agent.effective}</strong>{agent.state.detail ? `, ${agent.state.detail}` : ''}</div>
	<Toggle label="Curator enabled" hint="Off stops all background searching. Search and playback keep working. For a short break use Pause AI in the top bar instead." bind:checked={ag.value.enabled} />
	<SaveBar dirty={ag.dirty} busy={ag.busy} onsave={() => ag.save(ag.value.enabled ? 'Curator enabled' : 'Curator disabled')} onreset={() => ag.reset()} />
</Section>

<div class="gap"></div>

<Section title="Pace and limits" intro="YouTube blocks servers that make too many requests. These limits keep the curator slow and polite. Your own searches and playback are not limited by them.">
	<div class="explain panel small">
		With these settings the curator makes at most <strong>{th.value.max_per_hour}</strong> YouTube requests an hour (on average about {Math.min(perHourAvg, th.value.max_per_hour)}), and
		<strong>{th.value.max_per_day}</strong> a day. If YouTube shows a bot check, it stops for {mins(th.value.backoff_min_s)} at first, up to {mins(th.value.backoff_max_s)} if it keeps happening.
	</div>
	<div class="one">
		<Stepper label="Shortest pause between requests" hint="A random wait between this and the longest pause looks more human." bind:value={th.value.min_delay_s} min={2} max={600} step={5} format={mins} />
		<Stepper label="Longest pause between requests" bind:value={th.value.max_delay_s} min={5} max={1800} step={5} format={mins} />
		<Stepper label="Requests per hour" bind:value={th.value.max_per_hour} min={5} max={1000} step={5} />
		<Stepper label="Requests per day" bind:value={th.value.max_per_day} min={20} max={20000} step={50} />
		<Stepper label="First backoff after a bot check" bind:value={th.value.backoff_min_s} min={300} max={86400} step={900} format={mins} />
		<Stepper label="Longest backoff" bind:value={th.value.backoff_max_s} min={900} max={172800} step={1800} format={mins} />
	</div>
	<Toggle label="Pause while someone is watching" hint="Keeps the internet connection free for playback and avoids two kinds of YouTube traffic at once." bind:checked={th.value.pause_while_playing} />
	<TextField label="Quiet hours" hint='No curator work in this window, e.g. "01:00-07:00". Leave empty for none.' bind:value={th.value.quiet_hours} placeholder="01:00-07:00" group="quiet" />
	<TextField label="YouTube proxy" hint="Route every YouTube request through a proxy so your IP is not the one YouTube sees. PIA subscribers: socks5://user:pass@proxy-nl.privateinternetaccess.com:1080 (generate proxy credentials in the PIA dashboard). Leave empty for a direct connection." bind:value={th.value.proxy} placeholder="socks5://user:pass@host:1080" type="password" group="proxy" />
	<div class="one">
		<Stepper label="Results per search" hint="How many videos the AI looks at per search." bind:value={th.value.search_results} min={5} max={50} step={1} />
		<Stepper label="Comments to read" hint="Top comments often reveal what a video is really like." bind:value={th.value.max_comments} min={0} max={200} step={5} />
		<Stepper label="Transcript length" hint="Longer gives the AI more to judge with, but is slower." bind:value={th.value.transcript_max_chars} min={2000} max={200000} step={2000} format={(v) => `${Math.round(v / 1000)}k chars`} />
	</div>
	<SaveBar dirty={th.dirty} busy={th.busy} onsave={() => th.save('Limits saved')} onreset={() => th.reset()} />
</Section>

<style>
	.conn {
		display: grid;
		gap: 1rem;
	}
	.two {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));
		gap: 0.9rem;
	}
	/* Steppers use Left/Right to change values, so they sit in one column: Up/Down reaches every one. */
	.one {
		display: grid;
		gap: 0.75rem;
	}
	.test-row {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
	}
	.test-row p {
		flex: 1;
		min-width: 14rem;
	}
	.spin {
		width: 1em;
		height: 1em;
		border-radius: 50%;
		border: 2px solid currentColor;
		border-right-color: transparent;
		animation: spin 0.8s linear infinite;
	}
	.result {
		display: grid;
		gap: 0.9rem;
		padding: 1rem 1.1rem;
		border-radius: var(--r-md);
		animation: rise 0.25s var(--ease);
	}
	.result.ok {
		background: rgba(61, 220, 151, 0.08);
		border: 1px solid rgba(61, 220, 151, 0.4);
	}
	.result.bad {
		background: rgba(255, 92, 122, 0.08);
		border: 1px solid rgba(255, 92, 122, 0.45);
	}
	.rh {
		display: flex;
		align-items: center;
		gap: 0.8rem;
	}
	.rh .big {
		display: grid;
		place-items: center;
		width: 2.4rem;
		height: 2.4rem;
		border-radius: 50%;
		font-weight: 800;
		background: rgba(255, 255, 255, 0.08);
	}
	.ok .rh .big {
		color: var(--ok);
	}
	.bad .rh .big {
		color: var(--bad);
	}
	.reply {
		display: grid;
		gap: 0.25rem;
	}
	code {
		font-size: 0.9rem;
		padding: 0.5rem 0.7rem;
		border-radius: var(--r-sm);
		background: rgba(0, 0, 0, 0.3);
		white-space: pre-wrap;
		word-break: break-word;
	}
	.err {
		color: #ffc2cd;
	}
	.models {
		display: grid;
		gap: 0.45rem;
	}
	.explain {
		line-height: 1.6;
		background: rgba(108, 198, 255, 0.07);
		border-color: rgba(108, 198, 255, 0.25);
	}
	.gap {
		height: 2.4rem;
	}
</style>
