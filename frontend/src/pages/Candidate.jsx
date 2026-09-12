import "./Candidate.css";

function Candidate({
  candidate,
  repositories,
  selectedRepositories,
  setSelectedRepositories,
  onAnalyze,
}) {
  const toggleRepository = (repoName) => {
    setSelectedRepositories((current) => {
      if (current.includes(repoName)) {
        return current.filter((name) => name !== repoName);
      }

      if (current.length >= 3) {
        return current;
      }

      return [...current, repoName];
    });
  };

  return (
    <main className="candidate-page">
      {/* NAVBAR */}
      <nav className="candidate-navbar">
        <div className="candidate-logo">CODE//ASSESS</div>

        <div className="candidate-nav-title">CANDIDATE / 01</div>

        <div className="candidate-version">v1.0.0</div>
      </nav>

      {/* CANDIDATE HEADER */}
      <section className="candidate-header">
        <div className="candidate-identity">
          <img
            src={candidate.avatar_url}
            alt={candidate.username}
            className="candidate-avatar"
          />

          <div>
            <div className="candidate-label">[ GITHUB CANDIDATE ]</div>

            <h1>{candidate.name || candidate.username}</h1>

            <div className="candidate-username">@{candidate.username}</div>

            {candidate.bio && <p className="candidate-bio">{candidate.bio}</p>}
          </div>
        </div>

        <a
          href={`https://github.com/${candidate.username}`}
          target="_blank"
          rel="noreferrer"
          className="github-profile"
        >
          VIEW GITHUB ↗
        </a>
      </section>

      {/* STATS */}
      <section className="candidate-stats">
        <div className="stat">
          <span>CONTRIBUTIONS</span>
          <strong>{candidate.total_contributions}</strong>
        </div>

        <div className="stat">
          <span>ACTIVE DAYS</span>
          <strong>{candidate.active_days}</strong>
        </div>

        <div className="stat">
          <span>FOLLOWERS</span>
          <strong>{candidate.followers}</strong>
        </div>

        <div className="stat">
          <span>REPOSITORIES</span>
          <strong>{repositories.length}</strong>
        </div>
      </section>

      {/* REPOSITORY SELECTION */}
      <section className="repository-section">
        <div className="section-heading">
          <div>
            <div className="section-label">[ PROJECT SELECTION ]</div>

            <h2>SELECT PROJECTS</h2>

            <p>Choose up to 3 repositories to analyze.</p>
          </div>

          <div className="selection-count">
            {selectedRepositories.length} / 3 SELECTED
          </div>
        </div>

        <div className="repository-grid">
          {repositories.map((repo) => {
            const selected = selectedRepositories.includes(repo.name);

            return (
              <article
                key={repo.name}
                className={`repository-card ${selected ? "selected" : ""}`}
                onClick={() => toggleRepository(repo.name)}
              >
                <div className="repo-top">
                  <div className="repo-index">
                    {String(repositories.indexOf(repo) + 1).padStart(2, "0")}
                  </div>

                  <div className={`repo-checkbox ${selected ? "checked" : ""}`}>
                    {selected ? "✓" : ""}
                  </div>
                </div>

                <h3>{repo.name}</h3>

                <p className="repo-description">
                  {repo.description || "No description provided."}
                </p>

                <div className="repo-meta">
                  <span>{repo.primary_language || "UNKNOWN"}</span>

                  <span>★ {repo.stars}</span>

                  <span>⑂ {repo.forks}</span>
                </div>

                <div className="repo-languages">
                  {repo.languages?.map((language) => (
                    <span key={language}>{language}</span>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* ACTION */}
      <div className="candidate-action">
        <button
          className="analyze-button"
          disabled={selectedRepositories.length === 0}
          onClick={onAnalyze}
        >
          ANALYZE SELECTED
          <span>→</span>
        </button>
      </div>
    </main>
  );
}

export default Candidate;
