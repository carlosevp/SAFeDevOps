import { useState } from "react";

type Props = {
  readonly onStart: (body: {
    name: string;
    email: string;
    team_name: string;
    ai_review_consent: boolean;
    data_restrictions_ack: boolean;
  }) => Promise<void>;
};

export function IdentityStep({ onStart }: Readonly<Props>) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [teamName, setTeamName] = useState("");
  const [aiReviewConsent, setAiReviewConsent] = useState(false);
  const [dataRestrictionsAck, setDataRestrictionsAck] = useState(false);
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
    if (!dataRestrictionsAck) {
      setError("Please confirm the restricted data attestation before starting.");
      return;
    }
    setBusy(true);
    try {
      await onStart({
        name: name.trim(),
        email: email.trim(),
        team_name: teamName.trim(),
        ai_review_consent: aiReviewConsent,
        data_restrictions_ack: dataRestrictionsAck,
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
      <p className="subtle">Complete your details and confirm consent before starting.</p>
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
        <fieldset className="consent-panel">
          <legend className="consent-panel-title">AI Review Consent & Data Restrictions</legend>
          <ul className="consent-list subtle">
            <li>Only provide delivery/process details relevant to this assessment.</li>
            <li>Do not type or upload PII, PHI, secrets, credentials, or regulated customer data.</li>
            <li>If sensitive content is unavoidable, redact or anonymize it before submitting.</li>
          </ul>
          <label htmlFor="ai-consent" className="consent-check">
            <input
              id="ai-consent"
              type="checkbox"
              checked={aiReviewConsent}
              onChange={(e) => setAiReviewConsent(e.target.checked)}
              required
            />
            <span>I consent to AI-assisted review of this session’s responses and uploaded evidence.</span>
          </label>
          <label htmlFor="data-restrictions-ack" className="consent-check">
            <input
              id="data-restrictions-ack"
              type="checkbox"
              checked={dataRestrictionsAck}
              onChange={(e) => setDataRestrictionsAck(e.target.checked)}
              required
            />
            <span>
              I confirm that I will not submit restricted information (including PII, PHI, secrets, or similar
              protected data).
            </span>
          </label>
        </fieldset>
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
