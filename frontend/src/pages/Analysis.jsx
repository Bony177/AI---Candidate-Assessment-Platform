import { useEffect, useState } from "react";
import "./Analysis.css";

function Analysis({ candidate, selectedRepositories, taskId }) {
  const [status, setStatus] = useState("QUEUED");
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  // ==========================================
  // QUESTION GENERATOR STATE
  // ==========================================

  const [selectedCategories, setSelectedCategories] = useState([
    "Repository-Based",
    "Code Understanding",
    "Improvement",
  ]);

  const [questionRepository, setQuestionRepository] = useState(
    selectedRepositories?.[0] || "",
  );

  const [questions, setQuestions] = useState([]);
  const [generatingQuestions, setGeneratingQuestions] = useState(false);
  const [questionError, setQuestionError] = useState("");

  // ==========================================
  // ANALYSIS STATUS + REPORT
  // ==========================================

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
  // QUESTION CATEGORY TOGGLE
  // ==========================================

  const toggleCategory = (category) => {
    setSelectedCategories((current) =>
      current.includes(category)
        ? current.filter((item) => item !== category)
        : [...current, category],
    );
  };

  // ==========================================
  // GENERATE INTERVIEW QUESTIONS
  // ==========================================

  const generateInterviewQuestions = async () => {
    if (!questionRepository) {
      setQuestionError("Please select a repository.");
      return;
    }

    if (selectedCategories.length === 0) {
      setQuestionError("Please select at least one question category.");
      return;
    }

    try {
      setGeneratingQuestions(true);
      setQuestionError("");
      setQuestions([]);

      const response = await fetch(
        "http://127.0.0.1:8000/api/v1/generate-questions",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            task_id: taskId,
            repository: questionRepository,
            selected_categories: selectedCategories,
          }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to generate interview questions.",
        );
      }

      console.log("GENERATED QUESTIONS:", data);

      setQuestions(data.questions || []);
    } catch (err) {
      console.error("QUESTION GENERATION ERROR:", err);
      setQuestionError(err.message);
    } finally {
      setGeneratingQuestions(false);
    }
  };

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

      {/* ==========================================
          REPORT HEADER
          ========================================== */}

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

      {/* ==========================================
          REPORT + QUESTION GENERATOR
          ========================================== */}

      <div className="analysis-content-grid">
        {/* ==========================================
            LEFT — REPOSITORIES
            ========================================== */}

        <section className="report-repositories">
          {report.repositories?.map((repo) => {
            const analysis = repo.analysis;

            if (!analysis) {
              return (
                <article className="report-repository" key={repo.name}>
                  <h2>{repo.name}</h2>

                  <p>Repository status: {repo.status}</p>
                  <AnalysisCoverage coverage={repo.analysis_coverage || {}} />
                  {repo.security_scan && (
                    <p className="security-scan-status is-incomplete">
                      Gitleaks {repo.security_scan.status}; Security score
                      0/20 ({repo.security_scan.error_code}).
                    </p>
                  )}
                </article>
              );
            }

            const score = analysis.static_score || {};
            const hasStaticScore =
              repo.status !== "unsupported_for_static_analysis" &&
              typeof score.total_score === "number" &&
              Number.isFinite(score.total_score);
            const securityScan = analysis.security_scan;
            const securityFindings = Array.isArray(securityScan?.findings)
              ? securityScan.findings
              : [];
            const warningDensity = analysis.warning_density_per_1000_loc;
            const hasWarningDensity =
              typeof warningDensity === "number" &&
              Number.isFinite(warningDensity);

            return (
              <article className="report-repository" key={repo.name}>
                <div className="repository-heading">
                  <div>
                    <span>REPOSITORY</span>

                    <h2>{repo.name}</h2>
                  </div>

                  <div className="repository-score">
                    {hasStaticScore ? score.total_score : "N/A"}

                    {hasStaticScore && <small>/100</small>}
                  </div>
                </div>

                {/* SCORE BARS */}

                <div className="score-section">
                  <ScoreBar
                    label="COMPLEXITY"
                    value={
                      hasStaticScore
                        ? score.breakdown?.complexity ?? null
                        : null
                    }
                    max={25}
                  />

                  <ScoreBar
                    label="STRUCTURE"
                    value={
                      hasStaticScore
                        ? score.breakdown?.structure ?? null
                        : null
                    }
                    max={20}
                  />

                  <ScoreBar
                    label="TESTING"
                    value={
                      hasStaticScore
                        ? score.breakdown?.testing ?? null
                        : null
                    }
                    max={20}
                  />

                  <ScoreBar
                    label="SECURITY"
                    value={
                      securityScan
                        ? hasStaticScore
                          ? score.breakdown?.security
                          : null
                        : null
                    }
                    max={20}
                  />

                  <ScoreBar
                    label="CODE SMELLS"
                    value={
                      hasStaticScore
                        ? score.breakdown?.code_smells ?? null
                        : null
                    }
                    max={15}
                  />
                </div>

                <AnalysisCoverage coverage={analysis.analysis_coverage || {}} />

                <section className="security-report">
                  <div className="security-report-header">
                    <h3>GITLEAKS SECURITY SCAN</h3>
                    <strong>
                      {securityScan?.finding_count ?? "—"} UNIQUE FINDINGS
                    </strong>
                  </div>

                  {securityScan?.status === "complete" ? (
                    securityFindings.length === 0 ? (
                      <p className="security-scan-status is-complete">
                        Scan complete; no findings detected. This does not
                        prove the repository is entirely secure.
                      </p>
                    ) : (
                      <p className="security-scan-status is-complete">
                        Scan complete. Findings are potential and have not
                        been verified.
                      </p>
                    )
                  ) : (
                    <p className="security-scan-status is-incomplete">
                      {securityScan?.status === "partial"
                        ? "Scan incomplete; Git history coverage is limited."
                        : "Scan failed or unavailable; Security score is fail-closed."}
                      {securityScan?.error_code
                        ? ` (${securityScan.error_code})`
                        : ""}
                    </p>
                  )}
                  <p className="security-scan-policy">
                    Scan scope:{" "}
                    {securityScan?.scan_mode === "git"
                      ? "Git history"
                      : securityScan?.scan_mode === "dir"
                        ? "working tree only"
                        : "unavailable"}
                    . Gitleaks allowlists are honored; suppressed matches are
                    excluded from the finding count.
                  </p>

                  {securityFindings.length > 0 && (
                    <ul className="security-findings">
                      {securityFindings.map((finding, index) => (
                        <li
                          key={`${finding.rule_id}-${finding.file}-${finding.line}-${index}`}
                        >
                          <div className="security-finding-heading">
                            <strong>{finding.rule_id}</strong>
                            <span
                              title={
                                finding.severity_source ===
                                "application_rule_map"
                                  ? "Severity assigned by application rule-ID policy"
                                  : "Gitleaks does not provide severity for this rule"
                              }
                            >
                              {finding.severity}
                            </span>
                          </div>
                          <p>{finding.description}</p>
                          <small>
                            {finding.file || "File unavailable"}
                            {finding.line ? `:${finding.line}` : ""}
                          </small>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

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

                  <div
                    title={
                      analysis.loc_status && analysis.loc_status !== "ok"
                        ? analysis.loc_status
                        : "Warnings per 1,000 lines of code"
                    }
                  >
                    <span>WARNINGS / 1K LOC</span>

                    <strong
                      title={
                        hasWarningDensity
                          ? undefined
                          : "Warning density is unavailable in the report"
                      }
                    >
                      {hasWarningDensity
                        ? warningDensity.toFixed(2)
                        : "N/A"}
                      {analysis.loc_status &&
                        analysis.loc_status !== "ok" &&
                        " *"}
                    </strong>
                  </div>
                </div>
              </article>
            );
          })}
        </section>

        {/* ==========================================
            RIGHT — AI QUESTION GENERATOR
            ========================================== */}

        <aside className="question-generator">
          <div className="question-generator-header">
            <span>[ AI INTERVIEW MODULE ]</span>

            <h2>
              INTERVIEW
              <br />
              QUESTIONS
            </h2>

            <p>Generate repository-specific questions for the interviewer.</p>
          </div>

          {/* ==========================================
              REPOSITORY SELECTOR
              ========================================== */}

          <div className="question-control">
            <label>REPOSITORY</label>

            <select
              value={questionRepository}
              onChange={(e) => setQuestionRepository(e.target.value)}
            >
              {selectedRepositories.map((repo) => (
                <option key={repo} value={repo}>
                  {repo}
                </option>
              ))}
            </select>
          </div>

          {/* ==========================================
              QUESTION CATEGORIES
              ========================================== */}

          <div className="question-control">
            <label>QUESTION TYPES</label>

            <div className="category-list">
              {[
                "Repository-Based",
                "Code Understanding",
                "Technical Concepts",
                "Problem Solving",
                "Improvement",
                "Job Role",
              ].map((category) => (
                <label
                  className={`category-option ${
                    selectedCategories.includes(category) ? "selected" : ""
                  }`}
                  key={category}
                >
                  <input
                    type="checkbox"
                    checked={selectedCategories.includes(category)}
                    onChange={() => toggleCategory(category)}
                  />

                  <span>{category}</span>
                </label>
              ))}
            </div>
          </div>

          {/* ==========================================
              GENERATE BUTTON
              ========================================== */}

          <button
            className="generate-questions-button"
            onClick={generateInterviewQuestions}
            disabled={generatingQuestions}
          >
            {generatingQuestions ? "GENERATING..." : "GENERATE QUESTIONS →"}
          </button>

          {/* ==========================================
              QUESTION ERROR
              ========================================== */}

          {questionError && (
            <div className="question-error">{questionError}</div>
          )}

          {/* ==========================================
              GENERATED QUESTION BANK
              ========================================== */}

          {questions.length > 0 && (
            <div className="generated-questions">
              <div className="generated-header">
                <span>QUESTION BANK</span>

                <strong>{questions.length} QUESTIONS</strong>
              </div>

              {questions.map((item, index) => (
                <article
                  className="question-card"
                  key={`${item.category}-${index}`}
                >
                  <div className="question-category">{item.category}</div>

                  <h3>
                    {index + 1}. {item.question}
                  </h3>

                  <p>
                    <strong>WHY:</strong> {item.reason}
                  </p>
                </article>
              ))}
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}

/* ==========================================
   SCORE BAR COMPONENT
   ========================================== */

function ScoreBar({ label, value, max }) {
  const hasScore = typeof value === "number" && Number.isFinite(value);
  const percentage = hasScore
    ? Math.min((value / max) * 100, 100)
    : 0;

  return (
    <div className="score-bar">
      <div className="score-bar-header">
        <span>{label}</span>

        <strong>
          {hasScore ? `${value}/${max}` : `N/A/${max}`}
        </strong>
      </div>

      <div className="score-track">
        <div className="score-fill" style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

export function AnalysisCoverage({ coverage }) {
  const percentage = coverage.coverage_percentage;
  const hasPercentage =
    typeof percentage === "number" && Number.isFinite(percentage);
  const fileDetails = Array.isArray(coverage.file_details)
    ? coverage.file_details
    : [];
  const incompleteFiles = fileDetails.filter(
    (file) => file.status === "skipped" || file.status === "failed",
  );
  const status = coverage.status || "unavailable";
  const isIncomplete = status === "partial" || status === "failed";
  const reason =
    coverage.reason ||
    (typeof coverage.files_failed === "number" &&
    typeof coverage.files_skipped === "number"
      ? `${coverage.files_failed} file(s) failed and ${coverage.files_skipped} file(s) were skipped.`
      : "Some file outcomes are incomplete.");

  return (
    <section
      className={`analysis-coverage status-${status}`}
      aria-label="Analysis Coverage and Confidence"
    >
      <div className="analysis-coverage-header">
        <div>
          <span>[ SOURCE-FILE ANALYSIS ]</span>
          <h3>Analysis Coverage &amp; Confidence</h3>
        </div>
        <strong className={`coverage-status status-${status}`}>
          {status.replaceAll("_", " ")}
        </strong>
      </div>

      {isIncomplete && (
        <p className="coverage-warning" role="status">
          Analysis is incomplete. {reason}
        </p>
      )}

      {status === "no_supported_files" && (
        <p className="coverage-empty">
          No supported source files were discovered for analysis.
        </p>
      )}

      {status === "unavailable" && (
        <p className="coverage-empty">
          Coverage details are unavailable in this report.
        </p>
      )}

      {hasPercentage ? (
        <div className="coverage-meter">
          <div className="coverage-meter-label">
            <span>FILE-ANALYSIS COVERAGE</span>
            <strong>{percentage.toFixed(1)}%</strong>
          </div>
          <div
            className="coverage-track"
            role="progressbar"
            aria-label="Source-file analysis coverage"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow={Math.min(Math.max(percentage, 0), 100)}
          >
            <div
              className="coverage-fill"
              style={{ width: `${Math.min(Math.max(percentage, 0), 100)}%` }}
            />
          </div>
        </div>
      ) : (
        <p className="coverage-unavailable">Coverage percentage: unavailable</p>
      )}

      <dl className="coverage-counts">
        {[
          ["Discovered", coverage.supported_files_discovered],
          ["Analyzed", coverage.files_analyzed],
          ["Skipped", coverage.files_skipped],
          ["Failed", coverage.files_failed],
        ].map(([label, count]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{typeof count === "number" ? count : "—"}</dd>
          </div>
        ))}
      </dl>

      {incompleteFiles.length > 0 && (
        <details className="coverage-file-details">
          <summary>
            View skipped or failed files ({incompleteFiles.length})
          </summary>
          <ul>
            {incompleteFiles.map((file, index) => (
              <li key={`${file.path || "file"}-${index}`}>
                <div>
                  <strong>{file.path || "Path unavailable"}</strong>
                  <span>{file.status}</span>
                </div>
                {file.reason && <p>{file.reason}</p>}
                {file.stage && <small>Stage: {file.stage}</small>}
              </li>
            ))}
          </ul>
        </details>
      )}

      {fileDetails.length === 0 &&
        (coverage.files_skipped > 0 || coverage.files_failed > 0) && (
          <p className="coverage-empty">
            Per-file outcome details are unavailable.
          </p>
        )}

      <p className="coverage-disclaimer">
        Analysis coverage indicates the proportion of discovered supported
        source files successfully processed by CODE//ASSESS. It does not measure
        unit-test coverage or guarantee that all defects have been detected.
        The status is an analysis-completeness indicator, not a confidence
        score.
      </p>
    </section>
  );
}

export default Analysis;
