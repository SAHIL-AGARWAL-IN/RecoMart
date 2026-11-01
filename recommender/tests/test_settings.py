from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ArtifactsDirTests(SimpleTestCase):
    """Trained models are saved to recommender/artifacts/ and kept out of git."""

    def test_artifacts_dir_location(self):
        artifacts = Path(settings.RECOMMENDER["ARTIFACTS_DIR"])
        self.assertEqual(artifacts, Path(settings.BASE_DIR) / "recommender" / "artifacts")
        self.assertTrue(artifacts.is_dir())

    def test_joblib_files_are_git_ignored(self):
        gitignore = (Path(settings.BASE_DIR) / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("recommender/artifacts/*.joblib", gitignore)
