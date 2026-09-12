import { useState } from "react";

import Landing from "./pages/Landing";
import Candidate from "./pages/Candidate";
import Analysis from "./pages/Analysis";

function App() {
  const [page, setPage] = useState("landing");

  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [candidate, setCandidate] = useState(null);
  const [repositories, setRepositories] = useState([]);

  const [selectedRepositories, setSelectedRepositories] = useState([]);

  const [taskId, setTaskId] = useState(null);

  // ==========================================
  // STEP 1 — FETCH GITHUB PROFILE
  // ==========================================

  const analyzeUsername = async () => {
    if (!username.trim()) return;

    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/v1/repositories/${username.trim()}`,
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to fetch GitHub data");
      }

      console.log("GITHUB DATA:", data);

      setCandidate(data.candidate);
      setRepositories(data.repositories || []);
      setSelectedRepositories([]);

      setPage("candidate");
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // STEP 2 — START ACTUAL ANALYSIS
  // ==========================================

  const startAnalysis = async () => {
    console.log("🔥 START ANALYSIS CLICKED", selectedRepositories);
    if (selectedRepositories.length === 0) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch("http://127.0.0.1:8000/api/v1/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          github_username: username,
          selected_repositories: selectedRepositories,
          job_description: null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to start analysis");
      }

      console.log("ANALYSIS STARTED:", data);

      setTaskId(data.task_id);

      // Move to analysis page
      setPage("analysis");
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // LANDING PAGE
  // ==========================================

  if (page === "landing") {
    return (
      <Landing
        username={username}
        setUsername={setUsername}
        loading={loading}
        error={error}
        analyzeUsername={analyzeUsername}
      />
    );
  }

  // ==========================================
  // CANDIDATE PAGE
  // ==========================================

  if (page === "candidate") {
    return (
      <Candidate
        candidate={candidate}
        repositories={repositories}
        selectedRepositories={selectedRepositories}
        setSelectedRepositories={setSelectedRepositories}
        onAnalyze={startAnalysis}
      />
    );
  }

  // ==========================================
  // ANALYSIS PAGE
  // ==========================================

  if (page === "analysis") {
    return (
      <Analysis
        candidate={candidate}
        repositories={repositories}
        selectedRepositories={selectedRepositories}
        taskId={taskId}
      />
    );
  }

  return null;
}

export default App;
