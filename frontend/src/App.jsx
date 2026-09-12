import { useState } from "react";

import Landing from "./pages/Landing";
import Candidate from "./pages/Candidate";

function App() {
  const [page, setPage] = useState("landing");

  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [candidate, setCandidate] = useState(null);
  const [repositories, setRepositories] = useState([]);

  const [selectedRepositories, setSelectedRepositories] = useState([]);

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

      // Store candidate information
      setCandidate(data.candidate);

      // Store repositories
      setRepositories(data.repositories || []);

      // Reset previous selections
      setSelectedRepositories([]);

      // Move to Candidate page
      setPage("candidate");
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // LANDING PAGE
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

  // CANDIDATE PAGE
  if (page === "candidate") {
    return (
      <Candidate
        candidate={candidate}
        repositories={repositories}
        selectedRepositories={selectedRepositories}
        setSelectedRepositories={setSelectedRepositories}
        onAnalyze={() => {
          console.log("SELECTED REPOSITORIES:", selectedRepositories);

          // Analysis page will be connected here next.
        }}
      />
    );
  }

  return null;
}

export default App;
