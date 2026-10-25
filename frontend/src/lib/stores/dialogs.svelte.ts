// Global dialogs that any page can open.
export interface FeedbackTarget {
	videoId: string;
	categoryId?: number | null;
	title?: string;
	rating?: number;
	onDone?: () => void;
}

class Dialogs {
	feedback = $state<FeedbackTarget | null>(null);
	addTo = $state<{ videoId: string; title?: string } | null>(null);
	candidate = $state<number | null>(null);

	openFeedback(t: FeedbackTarget) {
		this.feedback = t;
	}
	openAddTo(videoId: string, title?: string) {
		this.addTo = { videoId, title };
	}
	openCandidate(id: number) {
		this.candidate = id;
	}
}

export const dialogs = new Dialogs();
