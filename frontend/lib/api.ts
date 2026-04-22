const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type ApiErrorPayload = {
  detail?: string;
};

async function parseError(response: Response) {
  try {
    const payload = (await response.json()) as ApiErrorPayload;
    return payload.detail ?? `Request failed with status ${response.status}`;
  } catch {
    return `Request failed with status ${response.status}`;
  }
}

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${input}`, init);

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return (await response.json()) as T;
}

export type MeetingMeta = {
  meeting_id: number;
  title: string | null;
  filename: string;
  status: string;
  created_at: string;
};

export type TranscriptSegment = {
  start: number;
  end: number;
  text: string;
};

export type Decision = {
  text: string;
  timestamp: string | null;
};

export type ActionItem = {
  task: string;
  owner: string | null;
  due_date_iso: string | null;
  evidence_quote: string;
  timestamp: string | null;
  priority: string | null;
};

export type MeetingResult = {
  meeting_id: number;
  title: string | null;
  status: string;
  transcript_segments: TranscriptSegment[];
  summary: string | null;
  decisions: Decision[];
  action_items: ActionItem[];
};

export type MeetingInsights = {
  meeting_id: number;
  summary: string | null;
  decisions: Decision[];
  action_items: ActionItem[];
};

export async function createMeeting(formData: FormData) {
  return requestJson<{ meeting_id: number; status: string }>("/api/meetings", {
    method: "POST",
    body: formData,
  });
}

export async function getMeeting(meetingId: string) {
  return requestJson<MeetingMeta>(`/api/meetings/${meetingId}`);
}

export async function getResult(meetingId: string) {
  return requestJson<MeetingResult>(`/api/meetings/${meetingId}/result`);
}

export async function getInsights(meetingId: string) {
  return requestJson<MeetingInsights>(`/api/meetings/${meetingId}/insights`);
}

export async function transcribeMeeting(meetingId: string) {
  return requestJson<{ meeting_id: number; status: string; num_segments: number }>(
    `/api/meetings/${meetingId}/transcribe`,
    {
      method: "POST",
    },
  );
}

export async function extractMeeting(meetingId: string) {
  return requestJson<MeetingInsights>(`/api/meetings/${meetingId}/extract`, {
    method: "POST",
  });
}

