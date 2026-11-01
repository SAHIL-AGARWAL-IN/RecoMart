"""ML engine tests on a small deterministic catalog (no database needed)."""
import shutil
import tempfile
from pathlib import Path

import numpy as np
from django.test import SimpleTestCase

from recommender import engine, features

from .fixtures import PER_GROUP, toy_frame


class FeatureTests(SimpleTestCase):
    def setUp(self):
        self.frame = toy_frame()
        self.pipeline = features.build_pipeline()
        self.matrix = features.to_matrix(self.pipeline.fit_transform(self.frame))

    def test_one_row_per_product_and_no_missing_values(self):
        self.assertEqual(self.matrix.shape[0], len(self.frame))
        self.assertGreater(self.matrix.shape[1], 10)
        self.assertFalse(np.isnan(self.matrix).any())

    def test_rows_are_unit_length_so_dot_product_is_cosine_similarity(self):
        np.testing.assert_allclose(np.linalg.norm(self.matrix, axis=1), 1.0, rtol=1e-6)

    def test_missing_report(self):
        frame = self.frame.copy()
        frame.loc[0, "brand"] = None
        report = features.missing_values(frame)
        self.assertEqual(report["brand"], 1)
        self.assertEqual(report["name"], 0)


class TrainingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bundle = engine.train(toy_frame(), k_min=2, k_max=6, random_state=42)

    def test_k_is_chosen_by_best_silhouette(self):
        scores = self.bundle["k_scores"]
        self.assertEqual([row["k"] for row in scores], [2, 3, 4, 5, 6])
        best = max(scores, key=lambda row: row["silhouette"])
        self.assertEqual(self.bundle["k"], best["k"])
        self.assertEqual(self.bundle["k"], 3)  # three obvious groups in the fixture

    def test_forced_k_is_respected(self):
        bundle = engine.train(toy_frame(), k=4, random_state=42)
        self.assertEqual(bundle["k"], 4)

    def test_clusters_match_the_three_groups(self):
        labels = self.bundle["labels"]
        for group in range(3):
            members = labels[group * PER_GROUP:(group + 1) * PER_GROUP]
            self.assertEqual(len(set(members)), 1, "each group should be one cluster")

    def test_no_product_recommends_itself(self):
        for product_id, similar in zip(self.bundle["product_ids"], self.bundle["top_ids"]):
            self.assertNotIn(product_id, similar)

    def test_top_match_shares_the_category(self):
        frame = toy_frame().set_index("id")
        for product_id, similar in zip(self.bundle["product_ids"], self.bundle["top_ids"]):
            self.assertEqual(frame.loc[product_id, "category"], frame.loc[similar[0], "category"])

    def test_lists_are_filled_from_other_clusters_and_sorted(self):
        top_n = self.bundle["top_n"]
        for similar, scores in zip(self.bundle["top_ids"], self.bundle["top_scores"]):
            self.assertEqual(len(similar), min(top_n, len(self.bundle["product_ids"]) - 1))
            own_cluster = scores[:PER_GROUP - 1]
            self.assertEqual(own_cluster, sorted(own_cluster, reverse=True))

    def test_pca_gives_two_coordinates_per_product(self):
        self.assertEqual(np.asarray(self.bundle["pca_2d"]).shape, (len(self.bundle["product_ids"]), 2))


class PersistenceTests(SimpleTestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def test_versions_increase_and_reload_gives_identical_output(self):
        bundle = engine.train(toy_frame(), k=3, random_state=42)
        first = engine.save(bundle, self.folder)
        second = engine.save(engine.train(toy_frame(), k=3, random_state=42), self.folder)
        self.assertEqual((first.name, second.name), ("recomart_v1.joblib", "recomart_v2.joblib"))

        loaded = engine.load_latest(self.folder)
        self.assertEqual(loaded["version"], 2)
        np.testing.assert_allclose(loaded["matrix"], bundle["matrix"])
        self.assertEqual(loaded["top_ids"], bundle["top_ids"])

        recommender = engine.Recommender(loaded)
        product_id = bundle["product_ids"][0]
        self.assertEqual(recommender.similar(product_id, 5), list(zip(bundle["top_ids"][0], bundle["top_scores"][0]))[:5])

    def test_load_latest_returns_none_when_no_model(self):
        self.assertIsNone(engine.load_latest(self.folder))
