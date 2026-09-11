import asyncio
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import job_manager


class JobManagerPipelineTests(unittest.TestCase):
    def test_pipeline_runs_existing_analyzer_on_cloned_python_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)

            async def fake_fetch_github_data(username):
                return {
                    "login": username,
                    "contributionsCollection": {"contributionCalendar": {"totalContributions": 0}},
                    "repositories": {"nodes": [
                        {"name": "python-project", "primaryLanguage": {"name": "Python"}},
                    ]},
                }

            def fake_clone_repositories(username, repo_names, max_repos):
                path = temporary_path / "python-project"
                path.mkdir()
                (path / "sample.py").write_text("def add(left, right):\n    return left + right\n", encoding="utf-8")
                return {"python-project": str(path)}

            with patch.object(job_manager, "fetch_github_data", fake_fetch_github_data), \
                    patch.object(job_manager, "clone_repositories", fake_clone_repositories), \
                    patch.object(job_manager, "cleanup_cloned_repos", lambda cloned: [
                        shutil.rmtree(path) for path in cloned.values()
                    ]):
                job_manager.JOBS_DB["real-analyzer-task"] = {}
                asyncio.run(job_manager.run_assessment_pipeline("real-analyzer-task", "example", None))

            repository = job_manager.JOBS_DB["real-analyzer-task"]["report"]["repositories"][0]
            self.assertEqual(repository["status"], "analyzed")
            self.assertEqual(repository["analysis"]["files_analyzed"], 1)
            self.assertIn("total_score", repository["static_score"])

    def test_pipeline_analyzes_clones_aggregates_scores_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            clone_paths = {}

            async def fake_fetch_github_data(username):
                return {
                    "login": username,
                    "avatarUrl": None,
                    "contributionsCollection": {
                        "contributionCalendar": {"totalContributions": 4}
                    },
                    "repositories": {
                        "nodes": [
                            {"name": "large", "url": "https://github.com/example/large", "primaryLanguage": {"name": "Python"}},
                            {"name": "small", "url": "https://github.com/example/small", "primaryLanguage": {"name": "Python"}},
                            {"name": "fork", "isFork": True, "primaryLanguage": {"name": "Python"}},
                        ]
                    },
                }

            def fake_clone_repositories(username, repo_names, max_repos):
                for name in repo_names:
                    path = temporary_path / name
                    path.mkdir()
                    (path / "sample.py").write_text("value = 1\n", encoding="utf-8")
                    clone_paths[name] = str(path)
                return clone_paths

            def fake_analyze_repository(repo_path):
                self.assertTrue(Path(repo_path).is_dir())
                lines = 100 if Path(repo_path).name == "large" else 10
                score = 80 if lines == 100 else 100
                return {
                    "repository": repo_path,
                    "files_analyzed": 1,
                    "total_code_lines": lines,
                    "static_score": {"total_score": score, "breakdown": {}},
                }

            def fake_cleanup(paths):
                for path in paths.values():
                    shutil.rmtree(path)

            with patch.object(job_manager, "fetch_github_data", fake_fetch_github_data), \
                    patch.object(job_manager, "clone_repositories", fake_clone_repositories), \
                    patch.object(job_manager, "analyze_repository", fake_analyze_repository), \
                    patch.object(job_manager, "cleanup_cloned_repos", fake_cleanup):
                job_manager.JOBS_DB["test-task"] = {}
                asyncio.run(job_manager.run_assessment_pipeline("test-task", "example", None))

            report = job_manager.JOBS_DB["test-task"]["report"]
            self.assertEqual(job_manager.JOBS_DB["test-task"]["status"], "COMPLETED")
            self.assertEqual(report["repositories_analyzed"], 2)
            self.assertEqual(report["overall_static_score"], 82)
            self.assertEqual([item["name"] for item in report["repositories"]], ["large", "small"])
            self.assertTrue(all(item["status"] == "analyzed" for item in report["repositories"]))
            self.assertTrue(all(not Path(path).exists() for path in clone_paths.values()))

    def test_pipeline_continues_after_repository_analysis_failure(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            paths = {}

            async def fake_fetch_github_data(username):
                return {
                    "login": username,
                    "contributionsCollection": {"contributionCalendar": {"totalContributions": 0}},
                    "repositories": {"nodes": [
                        {"name": "broken", "primaryLanguage": {"name": "Python"}},
                        {"name": "healthy", "primaryLanguage": {"name": "Python"}},
                    ]},
                }

            def fake_clone_repositories(username, repo_names, max_repos):
                for name in repo_names:
                    path = temporary_path / name
                    path.mkdir()
                    paths[name] = str(path)
                return paths

            def fake_analyze_repository(repo_path):
                if Path(repo_path).name == "broken":
                    raise ValueError("invalid Python files")
                return {
                    "files_analyzed": 1,
                    "total_code_lines": 5,
                    "static_score": {"total_score": 70, "breakdown": {}},
                }

            with patch.object(job_manager, "fetch_github_data", fake_fetch_github_data), \
                    patch.object(job_manager, "clone_repositories", fake_clone_repositories), \
                    patch.object(job_manager, "analyze_repository", fake_analyze_repository), \
                    patch.object(job_manager, "cleanup_cloned_repos", lambda cloned: [
                        shutil.rmtree(path) for path in cloned.values()
                    ]):
                job_manager.JOBS_DB["failed-repo-task"] = {}
                asyncio.run(job_manager.run_assessment_pipeline("failed-repo-task", "example", None))

            report = job_manager.JOBS_DB["failed-repo-task"]["report"]
            self.assertEqual(job_manager.JOBS_DB["failed-repo-task"]["status"], "COMPLETED")
            self.assertEqual(report["repositories"][0]["status"], "analysis_failed")
            self.assertEqual(report["repositories"][1]["status"], "analyzed")
            self.assertEqual(report["overall_static_score"], 70)


if __name__ == "__main__":
    unittest.main()
