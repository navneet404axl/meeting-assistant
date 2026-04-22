"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { createMeeting } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileLabel = useMemo(() => {
    if (!file) {
      return "Choose an audio or video file";
    }

    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return `${file.name} (${sizeMb} MB)`;
  }, [file]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!file) {
      setError("Pick a meeting file before uploading.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    if (title.trim()) {
      formData.append("title", title.trim());
    }

    try {
      setSubmitting(true);
      const meeting = await createMeeting(formData);
      router.push(`/meetings/${meeting.meeting_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[rgb(246,248,251)] text-slate-950">
      <section className="relative overflow-hidden border-b border-black/10 bg-slate-950 text-white">
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-cover bg-center opacity-25"
          style={{
            backgroundImage:
              "url('https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1600&q=80')",
          }}
        />
        <div className="relative mx-auto flex max-w-6xl flex-col gap-3 px-6 py-10 sm:px-8">
          <p className="text-sm font-medium uppercase text-cyan-300">
            Meeting Assistant
          </p>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight">
            Turn recordings into transcript, summary, decisions, and action
            items.
          </h1>
          <p className="max-w-2xl text-base text-slate-200">
            Start with an audio or video file. The backend will save it, then
            you can run transcription and insight extraction from the meeting
            page.
          </p>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-10 px-6 py-10 sm:px-8 lg:grid-cols-[1.15fr_0.85fr]">
        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-6 rounded-lg border border-black/10 bg-white p-6 shadow-sm"
        >
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold">Upload a meeting</h2>
            <p className="text-sm text-slate-600">
              Supported formats: mp3, wav, m4a, mp4, webm.
            </p>
          </div>

          <label className="flex flex-col gap-2 text-sm font-medium">
            Meeting title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Weekly product sync"
              className="rounded-md border border-slate-300 px-4 py-3 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-200"
            />
          </label>

          <label className="flex cursor-pointer flex-col gap-3 rounded-md border border-dashed border-slate-300 bg-slate-50 p-5 transition hover:border-cyan-500 hover:bg-cyan-50/60">
            <span className="text-sm font-medium">Meeting file</span>
            <span className="text-sm text-slate-600">{fileLabel}</span>
            <input
              type="file"
              accept=".mp3,.wav,.m4a,.mp4,.webm,audio/*,video/*"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="hidden"
            />
          </label>

          {error ? (
            <p className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={submitting}
            className="inline-flex min-h-12 items-center justify-center rounded-md bg-cyan-600 px-5 py-3 font-medium text-white transition hover:bg-cyan-700 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {submitting ? "Uploading..." : "Upload and open meeting"}
          </button>
        </form>

        <div className="grid gap-4 self-start">
          <div className="rounded-lg border border-black/10 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold">Workflow</h3>
            <ol className="mt-4 grid gap-3 text-sm text-slate-700">
              <li>1. Upload the recording here.</li>
              <li>2. Run transcription on the meeting page.</li>
              <li>3. Generate insights with your local Ollama model.</li>
              <li>4. Review transcript, summary, decisions, and actions.</li>
            </ol>
          </div>

          <div className="rounded-lg border border-black/10 bg-white p-6 shadow-sm">
            <h3 className="text-lg font-semibold">Backend endpoints in use</h3>
            <ul className="mt-4 grid gap-2 text-sm text-slate-700">
              <li>
                <code>POST /api/meetings</code>
              </li>
              <li>
                <code>POST /api/meetings/{`{id}`}/transcribe</code>
              </li>
              <li>
                <code>POST /api/meetings/{`{id}`}/extract</code>
              </li>
              <li>
                <code>GET /api/meetings/{`{id}`}/result</code>
              </li>
              <li>
                <code>GET /api/meetings/{`{id}`}/insights</code>
              </li>
            </ul>
          </div>
        </div>
      </section>
    </main>
  );
}
