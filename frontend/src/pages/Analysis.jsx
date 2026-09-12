import { useEffect, useState } from "react";
import "./Analysis.css";

function Analysis({ candidate, selectedRepositories, taskId }) {
  const [status, setStatus] = useState("QUEUED");
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!taskId) return;

    let interval;

    const checkStatus = async () => {
      try {
        const response = await fetch(
          `http://127.0.0.1:8000/api/v1/status/${taskId}`,
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || "Failed to check analysis status");
        }

        console.log("ANALYSIS STATUS:", data);

        setStatus(data.status);

        if (data.status === "COMPLETED") {
          clearInterval(interval);

          const reportResponse = await fetch(
            `http://127.0.0.1:8000/api/v1/report/${taskId}`,
          );

          const reportData = await reportResponse.json();

          if (!reportResponse.ok) {
            throw new Error(reportData.detail || "Failed to fetch report");
          }

          console.log("FINAL REPORT:", reportData);

          setReport(reportData);
        }

        if (data.status === "FAILED") {
          clearInterval(interval);
          setError(data.error || "Analysis failed.");
        }
      } catch (err) {
        console.error(err);
        clearInterval(interval);
        setError(err.message);
      }
    };

    checkStatus();

    interval = setInterval(checkStatus, 1500);

    return () => clearInterval(interval);
  }, [taskId]);

  // ==========================================
  // ANALYSIS RUNNING
  // ==========================================

  if (!report && !error) {
    return (
      <main className="analysis-page">
        <nav className="analysis-navbar">
          <div>CODE//ASSESS</div>
          <div>ANALYSIS / {candidate?.username}</div>
          <div>{status}</div>
        </nav>

        <section className="analysis-loading">
          <div className="loading-label">[ STATIC ANALYSIS ENGINE ]</div>

          <h1>
            ANALYZING
            <br />
            SELECTED CODE
          </h1>

          <div className="loading-status">
            <span className="loading-dot">●</span>
            {status}
          </div>

          <div className="selected-list">
            {selectedRepositories.map((repo, index) => (
              <div key={repo}>
                <span>{String(index + 1).padStart(2, "0")}</span>

                {repo}
              </div>
            ))}
          </div>

          <p className="loading-message">
            Cloning repositories and running static analysis...
          </p>
        </section>
      </main>
    );
  }

  // ==========================================
  // ERROR
  // ==========================================

  if (error) {
    return (
      <main className="analysis-page">
        <nav className="analysis-navbar">
          <div>CODE//ASSESS</div>
          <div>ANALYSIS</div>
          <div>ERROR</div>
        </nav>

        <section className="analysis-error">
          <div>[ ANALYSIS FAILED ]</div>

          <h1>UNABLE TO COMPLETE</h1>

          <p>{error}</p>
        </section>
      </main>
    );
  }

  // ==========================================
  // FINAL REPORT
  // ==========================================

  return (
    <main className="analysis-page">
      <nav className="analysis-navbar">
        <div>CODE//ASSESS</div>

        <div>ANALYSIS / {candidate?.username}</div>

        <div>COMPLETED</div>
      </nav>

      {/* REPORT HEADER */}

      <section className="report-header">
        <div>
          <div className="report-label">[ FINAL ASSESSMENT ]</div>

          <h1>CODE ANALYSIS</h1>

          <p>Static analysis across selected repositories.</p>
        </div>

        <div className="overall-score">
          <span>OVERALL SCORE</span>

          <strong>{report.overall_static_score}</strong>

          <small>/ 100</small>
        </div>
      </section>

      {/* REPOSITORIES */}

      <section className="report-repositories">
        {report.repositories?.map((repo) => {
          const analysis = repo.analysis;

          if (!analysis) {
            return (
              <article className="report-repository" key={repo.name}>
                <h2>{repo.name}</h2>
                <p>Repository status: {repo.status}</p>
              </article>
            );
          }

          const score = analysis.static_score || {};

          return (
            <article className="report-repository" key={repo.name}>
              <div className="repository-heading">
                <div>
                  <span>REPOSITORY</span>

                  <h2>{repo.name}</h2>
                </div>

                <div className="repository-score">
                  {score.total_score}
                  <small>/100</small>
                </div>
              </div>

              {/* SCORE BARS */}

              <div className="score-section">
                <ScoreBar
                  label="COMPLEXITY"
                  value={score.breakdown?.complexity || 0}
                  max={25}
                />

                <ScoreBar
                  label="STRUCTURE"
                  value={score.breakdown?.structure || 0}
                  max={20}
                />

                <ScoreBar
                  label="TESTING"
                  value={score.breakdown?.testing || 0}
                  max={20}
                />

                <ScoreBar
                  label="SECURITY"
                  value={score.breakdown?.security || 0}
                  max={20}
                />

                <ScoreBar
                  label="CODE SMELLS"
                  value={score.breakdown?.code_smells || 0}
                  max={15}
                />
              </div>

              {/* CODE OVERVIEW */}

              <div className="code-overview">
                <div>
                  <span>FILES</span>
                  <strong>{analysis.files_analyzed ?? 0}</strong>
                </div>

                <div>
                  <span>CODE LINES</span>
                  <strong>{analysis.total_code_lines ?? 0}</strong>
                </div>

                <div>
                  <span>FUNCTIONS</span>
                  <strong>{analysis.total_functions ?? 0}</strong>
                </div>

                <div>
                  <span>COMPLEXITY</span>
                  <strong>{analysis.total_complexity ?? 0}</strong>
                </div>

                <div>
                  <span>SMELLS</span>
                  <strong>{analysis.total_smells ?? 0}</strong>
                </div>
              </div>
            </article>
          );
        })}
      </section>
    </main>
  );
}

/* SCORE BAR COMPONENT */

function ScoreBar({ label, value, max }) {
  const percentage = Math.min((value / max) * 100, 100);

  return (
    <div className="score-bar">
      <div className="score-bar-header">
        <span>{label}</span>

        <strong>
          {value}/{max}
        </strong>
      </div>

      <div className="score-track">
        <div className="score-fill" style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

export default Analysis;
