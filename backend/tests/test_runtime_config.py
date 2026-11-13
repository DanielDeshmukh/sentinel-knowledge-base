import unittest
from unittest.mock import patch
from pathlib import Path

from pydantic import ValidationError

from core.config import Settings


class RuntimeConfigTests(unittest.TestCase):
    def test_default_similarity_threshold_admits_observed_dpdp_match(self):
        settings = Settings(_env_file=None)

        self.assertEqual(settings.SIMILARITY_THRESHOLD, 0.40)

    def test_default_chat_provider_uses_nvidia_free_endpoint(self):
        settings = Settings(_env_file=None)

        self.assertEqual(
            settings.CHAT_API_URL,
            "https://integrate.api.nvidia.com/v1/chat/completions",
        )
        self.assertEqual(settings.CHAT_MODEL, "nvidia/nemotron-3.5-bolt-e4b")
        self.assertEqual(
            settings.NVIDIA_EMBEDDING_API_URL,
            "https://integrate.api.nvidia.com/v1/embeddings",
        )
        self.assertEqual(
            settings.NVIDIA_EMBEDDING_MODEL,
            "nvidia/nemotron-3.5-embed-1b",
        )
        self.assertEqual(settings.EMBEDDING_DIMENSION, 384)

    def test_legacy_openai_environment_values_do_not_override_provider_defaults(self):
        with patch.dict(
            "os.environ",
            {
                "CHAT_API_URL": "https://api.openai.com/v1/chat/completions",
                "CHAT_MODEL": "gpt-4o-mini",
                "CHAT_API_KEY": "legacy-key",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)

        self.assertEqual(
            settings.CHAT_API_URL,
            "https://integrate.api.nvidia.com/v1/chat/completions",
        )
        self.assertEqual(settings.CHAT_MODEL, "nvidia/nemotron-3.5-bolt-e4b")
        self.assertEqual(settings.CHAT_API_KEY, "")

    def test_groq_provider_uses_its_own_environment_values(self):
        settings = Settings(
            _env_file=None,
            AI_PROVIDER="groq",
            GROQ_API_KEY="groq-test-key",
            GROQ_CHAT_API_URL="https://api.groq.com/openai/v1/chat/completions",
            GROQ_CHAT_MODEL="qwen/qwen3.8-27b",
        )

        self.assertEqual(settings.CHAT_API_URL, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(settings.CHAT_MODEL, "qwen/qwen3.8-27b")
        self.assertEqual(settings.CHAT_API_KEY, "groq-test-key")

    def test_groq_provider_requires_an_explicit_model(self):
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, AI_PROVIDER="groq", GROQ_API_KEY="groq-test-key")

    def test_runtime_requirements_exclude_torch_embedding_stack(self):
        requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
        names = {
            line.split("==", 1)[0].strip().lower()
            for line in requirements.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#") and not line.startswith("--")
        }

        self.assertNotIn("sentence-transformers", names)
        self.assertNotIn("torch", names)

    def test_passlib_bcrypt_dependency_is_pinned_to_compatible_release(self):
        requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
        lines = {
            line.strip().lower()
            for line in requirements.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertIn("bcrypt==4.0.1", lines)


if __name__ == "__main__":
    unittest.main()
