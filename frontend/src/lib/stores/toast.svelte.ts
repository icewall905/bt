export type ToastKind = 'info' | 'success' | 'error' | 'warn';

export interface ToastAction {
	label: string;
	run: () => void;
}

export interface Toast {
	id: number;
	kind: ToastKind;
	message: string;
	action?: ToastAction;
	timeout: number;
}

let seq = 0;

class ToastStore {
	items = $state<Toast[]>([]);

	push(message: string, kind: ToastKind = 'info', opts: { action?: ToastAction; timeout?: number } = {}): number {
		const id = ++seq;
		const timeout = opts.timeout ?? (kind === 'error' ? 6000 : 3500);
		// Collapse identical consecutive messages (e.g. repeated network errors).
		if (this.items.some((t) => t.message === message && t.kind === kind && !t.action)) return id;
		this.items = [...this.items.slice(-3), { id, kind, message, action: opts.action, timeout }];
		if (timeout > 0) setTimeout(() => this.dismiss(id), timeout);
		return id;
	}

	dismiss(id: number) {
		this.items = this.items.filter((t) => t.id !== id);
	}
}

export const toasts = new ToastStore();
export const toast = {
	info: (m: string, o?: { action?: ToastAction; timeout?: number }) => toasts.push(m, 'info', o),
	success: (m: string, o?: { action?: ToastAction; timeout?: number }) => toasts.push(m, 'success', o),
	error: (m: string, o?: { action?: ToastAction; timeout?: number }) => toasts.push(m, 'error', o),
	warn: (m: string, o?: { action?: ToastAction; timeout?: number }) => toasts.push(m, 'warn', o)
};
