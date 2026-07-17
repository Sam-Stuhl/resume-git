import { GOOGLE_LOGIN_URL } from "../api";

/** Public landing page: shown to signed-out visitors at "/". Every CTA points
 * at Google sign-in; the only in-page navigation is the "How it works" anchor. */
export function Landing(): JSX.Element {
  return (
    <div className="landing-page">
      <nav className="nav">
        <span className="wordmark">
          <WordmarkIcon className="mk" />
          resume-git
        </span>
        <span className="spacer" />
        <a className="navlink" href="#how">How it works</a>
        <a className="btn accent" href={GOOGLE_LOGIN_URL}>Continue with Google</a>
      </nav>

      <header className="hero">
        <div className="wrap hero-grid">
          <div>
            <h1>AI edits your r&eacute;sum&eacute;. <span className="g">You keep every version.</span></h1>
            <p className="sub">Ask for changes in plain English, see exactly what changed, and compile a clean PDF. Your original is never overwritten.</p>
            <div className="cta-row">
              <a className="btn accent lg" href={GOOGLE_LOGIN_URL}>Continue with Google</a>
              <a className="btn lg" href="#how">How it works</a>
            </div>
            <p className="fine">Works with any AI chat. No key required.</p>
          </div>

          <div className="reveal d2">
            <div className="assist">
              <div className="ahead">
                <StarIcon />
                {" "}assistant
                <span className="pill"><PillIcon />tailored: acme</span>
              </div>
              <div className="abody">
                <div className="user-bubble">Tailor my r&eacute;sum&eacute; for a backend role at Acme.</div>
                <p className="a-prose">Made a tailored copy of your r&eacute;sum&eacute; with 3 changes:</p>
                <div className="prop">
                  <div className="prow"><span className="lab mod">Modified</span><span className="sect">Summary</span></div>
                  <div className="prow"><span className="lab mod">Modified</span><span className="sect">Experience</span></div>
                  <div className="prow"><span className="lab add">Added</span><span className="sect">Skills</span></div>
                </div>
                <div className="diff">
                  <div className="l del">Built internal tools with Python and Flask</div>
                  <div className="l add">Shipped distributed data pipelines in Go and Kafka</div>
                </div>
                <div className="a-actions">
                  <button type="button" className="btn green sm">Approve</button>
                  <button type="button" className="btn sm">Discard</button>
                  <span className="note">Nothing is saved until you approve.</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="section" id="how">
        <div className="wrap">
          <span className="kicker">How it works</span>
          <h2>You ask, it edits, you keep every version.</h2>
          <p className="one">Under the hood your r&eacute;sum&eacute; is <b style={{ color: "var(--text)" }}>structured data (JSON)</b>, so the assistant edits it precisely, field by field, instead of handing you text to copy-paste back. Every change is easy to review.</p>

          <div className="steps">
            <div className="step s1">
              <div className="srail"><span className="node" /></div>
              <div className="meta">
                <div className="ref">01 &middot; ask</div>
                <h3>Ask in plain English</h3>
                <p>Tell the assistant what to change. It reads your history and edits the r&eacute;sum&eacute; for you.</p>
              </div>
              <div className="shot">
                <div className="frame">
                  <div className="chrome"><span className="dots"><i /><i /><i /></span><span className="addr">resume-git &middot; assistant</span></div>
                  <img src="/landing/assistant.png" alt="The assistant proposing changes." />
                </div>
              </div>
            </div>

            <div className="step s2">
              <div className="srail"><span className="node" /></div>
              <div className="meta">
                <div className="ref">02 &middot; review</div>
                <h3>Review the changes, approve them</h3>
                <p>Edits come back as a clear before-and-after against your current version. Approve or discard. It never invents experience.</p>
              </div>
              <div className="shot">
                <div className="frame">
                  <div className="chrome"><span className="dots"><i /><i /><i /></span><span className="addr">resume-git &middot; compare</span></div>
                  <img src="/landing/compare.png" alt="A before-and-after comparison of the proposed changes." />
                </div>
              </div>
            </div>

            <div className="step s3">
              <div className="srail"><span className="node" /></div>
              <div className="meta">
                <div className="ref">03 &middot; keep</div>
                <h3>Save it, get the PDF</h3>
                <p>Approved changes are saved as a new version, and a one-page PDF compiles as you go.</p>
              </div>
              <div className="shot">
                <div className="frame">
                  <div className="chrome"><span className="dots"><i /><i /><i /></span><span className="addr">resume-git &middot; edit</span></div>
                  <img src="/landing/app.webp" alt="The editor with a live PDF preview." />
                </div>
              </div>
            </div>
          </div>

          <div className="grid4">
            <div className="hl"><div className="t"><span className="d" style={{ background: "var(--accent)" }} />Structured data (JSON)</div><p>Your r&eacute;sum&eacute; is real data, not a document, so the AI edits it precisely and every change is reviewable.</p></div>
            <div className="hl"><div className="t"><span className="d" style={{ background: "var(--accent)" }} />Bring your own AI</div><p>Any AI chat with no key, or connect a Claude API key or OAuth token to use the assistant in the app.</p></div>
            <div className="hl"><div className="t"><span className="d" style={{ background: "var(--accent)" }} />You approve everything</div><p>Changes come as a clear comparison. Nothing is saved without your yes.</p></div>
            <div className="hl"><div className="t"><span className="d" style={{ background: "var(--commit)" }} />Live PDF</div><p>A clean, single-page, ATS-friendly PDF, always current.</p></div>
            <div className="hl"><div className="t"><span className="d" style={{ background: "var(--commit)" }} />Full history</div><p>Every change is a saved version. Restore anything, anytime.</p></div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="wrap who">
          <span className="kicker">Who it's for</span>
          <h2>CS students first. Anyone, really.</h2>
          <p>It builds the clean, single-page LaTeX r&eacute;sum&eacute; that's become the default for CS and software roles. You get the ATS-friendly PDF recruiters expect, with no LaTeX to write.</p>
          <p>Every edit becomes its own saved version, so you can spin off a tailored copy for each job, compare it against your original, and roll back anytime. You never lose a thing.</p>
        </div>
      </section>

      <section className="cta">
        <div className="wrap">
          <h2>Get started.</h2>
          <p>Bring your current r&eacute;sum&eacute; or start from scratch.</p>
          <div className="cta-row"><a className="btn accent lg" href={GOOGLE_LOGIN_URL}>Continue with Google</a></div>
          <p className="fine">We only use your Google account to sign you in. Your r&eacute;sum&eacute; stays private to your account.</p>
        </div>
      </section>

      <footer className="foot">
        <div className="wrap">
          <span className="wordmark" style={{ fontSize: 14 }}>
            <WordmarkIcon className="mk" size={14} />
            resume-git
          </span>
          <span className="spacer" />
          <a href="#">GitHub</a>
          <span>AI edits every version of your r&eacute;sum&eacute;.</span>
        </div>
      </footer>
    </div>
  );
}

function WordmarkIcon({ className, size = 17 }: { className?: string; size?: number }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="4" cy="3.5" r="1.8" />
      <circle cx="4" cy="12.5" r="1.8" />
      <circle cx="12" cy="6.5" r="1.8" />
      <path d="M4 5.3v5.4" />
      <path d="M12 8.3c0 2.4-2 2.9-4 3.2" />
    </svg>
  );
}

function StarIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 1.6 9.5 5l3.6.3-2.7 2.4.8 3.5L8 9.4 4.8 11.2l.8-3.5L2.9 5.3 6.5 5 8 1.6Z" />
    </svg>
  );
}

function PillIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" aria-hidden="true">
      <circle cx="4" cy="4" r="1.6" />
      <circle cx="4" cy="12" r="1.6" />
      <circle cx="12" cy="7" r="1.6" />
      <path d="M4 5.6v4.8" />
      <path d="M12 8.6c0 2-2 2.4-3.4 2.6" />
    </svg>
  );
}
