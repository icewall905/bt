// See https://svelte.dev/docs/kit/types#app.d.ts
declare global {
	namespace App {}
}

declare module 'svelte/elements' {
	interface HTMLAttributes<T> {
		/** Fired by the on-screen keyboard when the user confirms (OK). */
		onosksubmit?: (e: CustomEvent) => void;
	}
}

export {};
