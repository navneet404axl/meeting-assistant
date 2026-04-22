"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ActionItem,
  Decision,
  MeetingMeta,
  MeetingResult,
  SpeakerOption,
  TranscriptSegment,
  diarizeMeeting,
  extractMeeting,
  getInsights,
  getMeeting,
  getResult,
  getSpeakers,
  saveSpeakerMapping,
  transcribeMeeting,
} from "@/lib/api";

function formatSeconds(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function parseSummarySections(summary: string | null | undefined) {
  if (!summary) {
    return [];
  }

  return summary
    .split(/\n\s*\n/)
    .map((section) => section.trim())
    .filter(Boolean)
    .map((section) => {
      const [title, ...rest] = section.split("\n");
      return {
        title: title?.trim() || "Summary",
        body: rest.join("\n").trim(),
      };
    });
}

export default function MeetingPage() {
  const params = useParams<{ id: string }>();
  const meetingId = params.id;

  const [meeting, setMeeting] = useState<MeetingMeta | null>(null);
  const [result, setResult] = useState<MeetingResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState<"transcribe" | "extract" | "refresh" | "diarize" | "saveSpeakers" | null>(null);
  const [speakers, setSpeakers] = useState<SpeakerOption[]>([]);
  const [speakerInputs, setSpeakerInputs] = useState<Record<string, string>>({});

  const loadMeetingData = useCallback(async (mode: "refresh" | null = null) => {
    try {
      if (mode) {
        setWorking(mode);
        setError(null);
        setMessage(null);
      } else {
        setError(null);
      }

      const [meetingData, resultData, speakerData] = await Promise.all([
        getMeeting(meetingId),
        getResult(meetingId),
        getSpeakers(meetingId),
      ]);

      setMeeting(meetingData);
      setResult(resultData);
      setSpeakers(speakerData.speakers);
      setSpeakerInputs(
        speakerData.speakers.reduce<Record<string, string>>((acc, speaker) => {
          acc[speaker.speaker_label] = speaker.display_name;
          return acc;
        }, {}),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load meeting.");
    } finally {
      setLoading(false);
      setWorking(null);
    }
  }, [meetingId]);

  useEffect(() => {
    let active = true;

    async function loadInitialMeetingData() {
      try {
        const [meetingData, resultData, speakerData] = await Promise.all([
          getMeeting(meetingId),
          getResult(meetingId),
          getSpeakers(meetingId),
        ]);

        if (!active) {
          return;
        }

        setMeeting(meetingData);
        setResult(resultData);
        setSpeakers(speakerData.speakers);
        setSpeakerInputs(
          speakerData.speakers.reduce<Record<string, string>>((acc, speaker) => {
            acc[speaker.speaker_label] = speaker.display_name;
            return acc;
          }, {}),
        );
        setError(null);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load meeting.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadInitialMeetingData();

    return () => {
      active = false;
    };
  }, [meetingId]);

  const transcriptSegments = result?.transcript_segments ?? [];
  const decisions = result?.decisions ?? [];
  const actionItems = result?.action_items ?? [];
  const summarySections = parseSummarySections(result?.summary);

  const stats = useMemo(
    () => [
      { label: "Transcript segments", value: String(transcriptSegments.length) },
      { label: "Decisions", value: String(decisions.length) },
      { label: "Action items", value: String(actionItems.length) },
    ],
    [actionItems.length, decisions.length, transcriptSegments.length],
  );

  async function handleTranscribe() {
    try {
      setWorking("transcribe");
      setMessage("Transcription started. This can take a while for large files.");
      setError(null);
      await transcribeMeeting(meetingId);
      await loadMeetingData();
      setMessage("Transcription finished.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transcription failed.");
      setWorking(null);
    }
  }

  async function handleExtract() {
    try {
      setWorking("extract");
      setMessage("Generating insights with the local Ollama model...");
      setError(null);
      await extractMeeting(meetingId);
      await loadMeetingData();
      const savedInsights = await getInsights(meetingId);
      setResult((current) =>
        current
          ? {
              ...current,
              summary: savedInsights.summary,
              decisions: savedInsights.decisions,
              action_items: savedInsights.action_items,
            }
          : current,
      );
      setMessage("Insights are ready.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Insight extraction failed.");
      setWorking(null);
    }
  }

  async function handleDiarize() {
    try {
      setWorking("diarize");
      setMessage("Running speaker diarization...");
      setError(null);
      await diarizeMeeting(meetingId);
      await loadMeetingData();
      setMessage("Speaker labels are ready.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Diarization failed.");
      setWorking(null);
    }
  }

  async function handleSaveSpeakers() {
    try {
      setWorking("saveSpeakers");
      setMessage("Saving speaker names...");
      setError(null);
      const saved = await saveSpeakerMapping(meetingId, speakerInputs);
      setSpeakers(saved.speakers);
      await loadMeetingData();
      setMessage("Speaker names updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Saving speaker names failed.");
      setWorking(null);
    }
  }

  function downloadJson() {
    if (!result) {
      return;
    }

    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `meeting-${meetingId}-result.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-[rgb(246,248,251)] px-6 py-12 text-slate-950 sm:px-8">
        <div className="mx-auto max-w-6xl rounded-lg border border-black/10 bg-white p-6 shadow-sm">
          Loading meeting...
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[rgb(246,248,251)] px-6 py-8 text-slate-950 sm:px-8">
      <div className="mx-auto grid max-w-6xl gap-6">
        <div className="flex flex-wrap items-start justify-between gap-4 rounded-lg border border-black/10 bg-white p-6 shadow-sm">
          <div className="space-y-3">
            <Link href="/" className="text-sm font-medium text-cyan-700 hover:text-cyan-900">
              Back to upload
            </Link>
            <div>
              <p className="text-sm uppercase tracking-wide text-slate-500">
                Meeting {meetingId}
              </p>
              <h1 className="text-3xl font-semibold tracking-tight">
                {meeting?.title || "Untitled meeting"}
              </h1>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
                Status: {meeting?.status ?? result?.status ?? "unknown"}
              </span>
              {stats.map((item) => (
                <span
                  key={item.label}
                  className="rounded-full bg-cyan-50 px-3 py-1 text-sm text-cyan-900"
                >
                  {item.label}: {item.value}
                </span>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => void handleTranscribe()}
              disabled={working !== null}
              className="rounded-md bg-slate-900 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {working === "transcribe" ? "Transcribing..." : "Run transcription"}
            </button>
            <button
              onClick={() => void handleDiarize()}
              disabled={working !== null}
              className="rounded-md bg-emerald-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {working === "diarize" ? "Diarizing..." : "Run diarization"}
            </button>
            <button
              onClick={() => void handleExtract()}
              disabled={working !== null}
              className="rounded-md bg-cyan-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-cyan-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {working === "extract" ? "Extracting..." : "Generate insights"}
            </button>
            <button
              onClick={() => void loadMeetingData("refresh")}
              disabled={working !== null}
              className="rounded-md border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
            >
              {working === "refresh" ? "Refreshing..." : "Refresh result"}
            </button>
            <button
              onClick={downloadJson}
              disabled={!result}
              className="rounded-md border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
            >
              Download JSON
            </button>
          </div>
        </div>

        {message ? (
          <p className="rounded-lg border border-cyan-200 bg-cyan-50 px-4 py-3 text-sm text-cyan-900">
            {message}
          </p>
        ) : null}

        {error ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </p>
        ) : null}

        <section className="grid items-start gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="self-start rounded-lg border border-black/10 bg-white p-6 shadow-sm">
            <h2 className="text-xl font-semibold">Transcript</h2>
            <div className="mt-4 grid max-h-[70vh] gap-3 overflow-y-auto pr-2">
              {transcriptSegments.length ? (
                transcriptSegments.map((segment: TranscriptSegment, index) => (
                  <div
                    key={`${segment.start}-${segment.end}-${index}`}
                    className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3"
                  >
                    <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      {formatSeconds(segment.start)} - {formatSeconds(segment.end)}
                    </p>
                    <p className="mt-2 text-sm font-semibold text-cyan-800">
                      {segment.speaker_name || segment.speaker_label || "Unassigned speaker"}
                    </p>
                    <p className="mt-2 text-sm leading-7 text-slate-800">
                      {segment.text}
                    </p>
                  </div>
                ))
              ) : (
                <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-600">
                  No transcript yet. Run transcription first.
                </p>
              )}
            </div>
          </div>

          <div className="grid self-start gap-6">
            <section className="rounded-lg border border-black/10 bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-xl font-semibold">Speakers</h2>
                <button
                  onClick={() => void handleSaveSpeakers()}
                  disabled={working !== null || !speakers.length}
                  className="rounded-md border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
                >
                  {working === "saveSpeakers" ? "Saving..." : "Save speaker names"}
                </button>
              </div>
              <div className="mt-4 grid max-h-72 gap-3 overflow-y-auto pr-2">
                {speakers.length ? (
                  speakers.map((speaker) => (
                    <label
                      key={speaker.speaker_label}
                      className="grid gap-2 rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm"
                    >
                      <span className="font-medium text-slate-700">{speaker.speaker_label}</span>
                      <input
                        value={speakerInputs[speaker.speaker_label] ?? speaker.display_name}
                        onChange={(event) =>
                          setSpeakerInputs((current) => ({
                            ...current,
                            [speaker.speaker_label]: event.target.value,
                          }))
                        }
                        className="rounded-md border border-slate-300 bg-white px-3 py-2 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-200"
                      />
                    </label>
                  ))
                ) : (
                  <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-600">
                    No speakers detected yet. Run diarization after transcription.
                  </p>
                )}
              </div>
            </section>

            <section className="rounded-lg border border-black/10 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Summary</h2>
              <div className="mt-4 grid max-h-80 gap-3 overflow-y-auto pr-2">
                {summarySections.length ? (
                  summarySections.map((section, index) => (
                    <div
                      key={`${section.title}-${index}`}
                      className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3"
                    >
                      <p className="text-sm font-semibold text-slate-900">{section.title}</p>
                      <p className="mt-2 whitespace-pre-line text-sm leading-7 text-slate-700">
                        {section.body || section.title}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-600">
                    No summary yet. Generate insights to fill this in.
                  </p>
                )}
              </div>
            </section>

            <section className="rounded-lg border border-black/10 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Decisions</h2>
              <div className="mt-4 grid max-h-72 gap-3 overflow-y-auto pr-2">
                {decisions.length ? (
                  decisions.map((decision: Decision, index) => (
                    <div
                      key={`${decision.text}-${index}`}
                      className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3"
                    >
                      <p className="text-sm font-medium text-slate-900">{decision.text}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {decision.timestamp || "No timestamp"}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-600">
                    No saved decisions yet.
                  </p>
                )}
              </div>
            </section>

            <section className="rounded-lg border border-black/10 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold">Action items</h2>
              <div className="mt-4 max-h-[32rem] overflow-auto pr-2">
                {actionItems.length ? (
                  <table className="min-w-full table-fixed border-collapse text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-slate-500">
                        <th className="pb-3 pr-4 font-medium">Task</th>
                        <th className="pb-3 pr-4 font-medium">Owner</th>
                        <th className="pb-3 pr-4 font-medium">Due</th>
                        <th className="pb-3 pr-4 font-medium">Mentioned</th>
                        <th className="pb-3 font-medium">Priority</th>
                      </tr>
                    </thead>
                    <tbody>
                      {actionItems.map((item: ActionItem, index) => (
                        <tr key={`${item.task}-${index}`} className="border-b border-slate-100 align-top">
                          <td className="py-3 pr-4">
                            <p className="font-medium text-slate-900">{item.task}</p>
                            <p className="mt-1 text-xs leading-5 text-slate-500">
                              {item.evidence_quote}
                            </p>
                          </td>
                          <td className="py-3 pr-4 text-slate-700">{item.owner || "-"}</td>
                          <td className="py-3 pr-4 text-slate-700">
                            {item.due_date_iso || "-"}
                          </td>
                          <td className="py-3 pr-4 text-slate-700">{item.timestamp || "-"}</td>
                          <td className="py-3 text-slate-700">{item.priority || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-600">
                    No action items saved yet.
                  </p>
                )}
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
