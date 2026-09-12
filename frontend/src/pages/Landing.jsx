import "./Landing.css";

function Landing({ username, setUsername, loading, error, analyzeUsername }) {
  return (
    <main className="landing-page">
      {/* NAVBAR */}
      <nav className="landing-navbar">
        <div className="landing-logo">CODE//ASSESS</div>

        <div className="landing-nav-links">
          <span>ABOUT</span>
          <span>PROCESS</span>
          <span>GITHUB</span>
        </div>

        <div className="landing-version">v1.0.0</div>
      </nav>

      {/* HERO */}
      <section className="landing-hero">
        {/* LEFT */}
        <div className="landing-content">
          <div className="landing-eyebrow">[ GITHUB CANDIDATE ASSESSMENT ]</div>

          <h1 className="landing-title">
            REAL CODE.
            <br />
            REAL SKILLS.
            <br />
            <span>CLEARER HIRING.</span>
          </h1>

          <p className="landing-description">
            Analyze real GitHub projects.
            <br />
            Understand how developers build.
          </p>

          {/* USERNAME INPUT */}
          <div className="username-box">
            <div className="input-label">&gt; ENTER_GITHUB_USERNAME</div>

            <div className="input-row">
              <input
                type="text"
                placeholder="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    analyzeUsername();
                  }
                }}
              />

              <button onClick={analyzeUsername}>{loading ? "..." : "→"}</button>
            </div>
          </div>

          {/* ERROR */}
          {error && <div className="landing-error">ERROR: {error}</div>}
        </div>

        {/* RIGHT VISUAL */}
        <div className="landing-visual">
          <div className="ascii-art">
            <pre>{`
             .-=========-.
          .-'             '-.
        .'    ANALYZE       '.
       /                     \\
      ;       ┌───────┐       ;
      |       │ CODE  │       |
      ;       └───────┘       ;
       \\        ↓ ↓ ↓        /
        '.    ANALYSIS     .'
          '-.           .-'
             '-=======-'

        [ 01 ] [ 02 ] [ 03 ]

           CODE / SKILLS
            / POTENTIAL
            `}</pre>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="landing-footer">
        <span>01 / CODE ANALYSIS</span>

        <span>02 / REAL PROJECTS</span>

        <span>03 / CANDIDATE INSIGHTS</span>
      </footer>
    </main>
  );
}

export default Landing;
