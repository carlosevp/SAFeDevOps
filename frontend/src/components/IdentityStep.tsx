import { useState } from "react";

type Props = {
  readonly onStart: (body: {
    name: string;
    email: string;
    team_name: string;
    ai_review_consent: boolean;
  }) => Promise<void>;
};

export function IdentityStep({ onStart }: Readonly<Props>) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [teamName, setTeamName] = useState("");
  const [aiReviewConsent, setAiReviewConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim() || !email.trim() || !teamName.trim()) {
      setError("Name, email, and team name are required.");
      return;
    }
    if (!aiReviewConsent) {
      setError("Please confirm AI review consent before starting.");
      return;
    }
    setBusy(true);
    try {
      await onStart({
        name: name.trim(),
        email: email.trim(),
        team_name: teamName.trim(),
        ai_review_consent: aiReviewConsent,
      });
      /* onCreated set by parent from response */
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start session.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card identity-card">
      <h2 style={{ marginTop: 0, fontSize: "1.25rem" }}>Your details</h2>
      <p className="subtle">
        One practice at a time, AI sufficiency review, optional evidence, export when you are done. Scores stay hidden
        until the final summary.
      </p>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="name">Name</label>
          <input id="name" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" required />
        </div>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="team">Team name</label>
          <input id="team" value={teamName} onChange={(e) => setTeamName(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="ai-consent" style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem" }}>
            <input
              id="ai-consent"
              type="checkbox"
              checked={aiReviewConsent}
              onChange={(e) => setAiReviewConsent(e.target.checked)}
              required
              style={{ marginTop: "0.2rem" }}
            />
            <span>
              I consent to AI being used to review my assessment responses and uploaded evidence for this session.
            </span>
          </label>
        </div>
        {error ? <div className="error-text">{error}</div> : null}
        <div className="row" style={{ marginTop: "1rem" }}>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Starting…" : "Begin assessment"}
          </button>
        </div>
      </form>
    </div>
  );
}
