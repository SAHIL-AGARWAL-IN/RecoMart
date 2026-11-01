"""The recommendation engine: training, similarity ranking, saving/loading, and serving.

Pipeline (run by `python manage.py train_recommender`):
  1. features.build_pipeline() turns products into unit-length vectors
  2. K-Means groups the vectors into K clusters; K is chosen by the best silhouette score
     (the elbow of the inertia curve is reported too)
  3. For each product: rank the other products in its own cluster by cosine similarity,
     then fill up from the nearest other clusters
  4. Everything is saved with Joblib as artifacts/recomart_v{N}.joblib
"""
import re
import threading
import time
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from django.utils import timezone
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from . import features

FILE_PATTERN = re.compile(r"^recomart_v(\d+)\.joblib$")


# ----------------------------------------------------------------- choosing K
def score_k_values(matrix, k_min, k_max, random_state):
    """Fit K-Means for every K in the range; return inertia and silhouette for each."""
    k_max = min(k_max, len(matrix) - 1)  # silhouette needs fewer clusters than products
    scores = []
    for k in range(k_min, k_max + 1):
        model = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit(matrix)
        scores.append({
            "k": k,
            "inertia": round(float(model.inertia_), 4),
            "silhouette": round(float(silhouette_score(matrix, model.labels_)), 4),
        })
    return scores


def elbow_k(scores):
    """The 'knee' of the inertia curve: the point farthest from the straight line joining its ends."""
    if len(scores) < 3:
        return scores[0]["k"]
    ks = np.array([row["k"] for row in scores], dtype=float)
    inertia = np.array([row["inertia"] for row in scores], dtype=float)
    x = (ks - ks.min()) / (ks.max() - ks.min())
    y = (inertia - inertia.min()) / ((inertia.max() - inertia.min()) or 1)
    distance = np.abs(x + y - 1) / np.sqrt(2)  # distance to the line from (0, 1) to (1, 0)
    return int(ks[int(np.argmax(distance))])


# ----------------------------------------------------------------- ranking
def rank_similar(matrix, labels, centers, top_n):
    """For each product: same-cluster products by cosine similarity, then the nearest clusters.

    Rows are unit length, so matrix @ matrix.T is the cosine similarity of every pair.
    A product is never in its own list.
    """
    similarity = matrix @ matrix.T
    members = {cluster: np.flatnonzero(labels == cluster) for cluster in np.unique(labels)}
    top_ids, top_scores = [], []
    for i, vector in enumerate(matrix):
        cluster_order = np.argsort(np.linalg.norm(centers - vector, axis=1))  # own cluster first
        ranked = []
        for cluster in cluster_order:
            candidates = [j for j in members[cluster] if j != i]
            ranked.extend(sorted(candidates, key=lambda j: -similarity[i, j]))
            if len(ranked) >= top_n:
                break
        chosen = ranked[:top_n]
        top_ids.append(chosen)
        top_scores.append([round(float(similarity[i, j]), 4) for j in chosen])
    return top_ids, top_scores


# ----------------------------------------------------------------- training
def train(frame, k=None, k_min=None, k_max=None, random_state=None, top_n=None):
    """Train on a product DataFrame and return a 'bundle' dict with everything needed to serve."""
    config = settings.RECOMMENDER
    k_min = k_min or config["K_MIN"]
    k_max = k_max or config["K_MAX"]
    random_state = config["RANDOM_STATE"] if random_state is None else random_state
    top_n = top_n or config["CACHE_TOP_N"]
    started = time.perf_counter()

    pipeline = features.build_pipeline()
    matrix = features.to_matrix(pipeline.fit_transform(frame))

    k_scores = score_k_values(matrix, k_min, k_max, random_state)
    best_k = max(k_scores, key=lambda row: row["silhouette"])["k"]
    chosen_k = k or best_k
    model = KMeans(n_clusters=chosen_k, n_init=10, random_state=random_state).fit(matrix)

    product_ids = [int(i) for i in frame["id"]]
    rows, top_scores = rank_similar(matrix, model.labels_, model.cluster_centers_, top_n)
    labels, counts = np.unique(model.labels_, return_counts=True)

    return {
        "version": None,  # set by save()
        "trained_at": timezone.now(),
        "pipeline": pipeline,
        "kmeans": model,
        "product_ids": product_ids,
        "matrix": matrix,
        "labels": [int(label) for label in model.labels_],
        "k": chosen_k,
        "best_k": best_k,
        "elbow_k": elbow_k(k_scores),
        "k_scores": k_scores,
        "silhouette": round(float(silhouette_score(matrix, model.labels_)), 4),
        "cluster_sizes": {int(c): int(n) for c, n in zip(labels, counts)},
        "top_n": top_n,
        "top_ids": [[product_ids[j] for j in row] for row in rows],
        "top_scores": top_scores,
        "pca_2d": PCA(n_components=2, random_state=random_state).fit_transform(matrix).round(4),
        "duration_seconds": round(time.perf_counter() - started, 2),
    }


# ----------------------------------------------------------------- saving and loading
def _versions(folder):
    found = []
    for path in Path(folder).glob("recomart_v*.joblib"):
        match = FILE_PATTERN.match(path.name)
        if match:
            found.append((int(match.group(1)), path))
    return sorted(found)


def save(bundle, folder=None):
    """Save the bundle as the next version, e.g. artifacts/recomart_v3.joblib. Returns the path."""
    folder = Path(folder or settings.RECOMMENDER["ARTIFACTS_DIR"])
    folder.mkdir(parents=True, exist_ok=True)
    versions = _versions(folder)
    bundle["version"] = versions[-1][0] + 1 if versions else 1
    path = folder / f"recomart_v{bundle['version']}.joblib"
    joblib.dump(bundle, path, compress=3)
    return path


def load_latest(folder=None):
    """The newest saved bundle, or None if the model has never been trained.

    Security: joblib files are pickles and can run code when loaded, so we only ever load files
    that our own train_recommender command wrote into ARTIFACTS_DIR. Never load uploaded files.
    """
    versions = _versions(folder or settings.RECOMMENDER["ARTIFACTS_DIR"])
    return joblib.load(versions[-1][1]) if versions else None


# ----------------------------------------------------------------- serving
class Recommender:
    """A trained model, ready to answer 'what is similar to product X?' instantly."""

    def __init__(self, bundle):
        self.bundle = bundle
        self.version = bundle["version"]
        self._row = {product_id: row for row, product_id in enumerate(bundle["product_ids"])}

    def __contains__(self, product_id):
        return product_id in self._row

    def similar(self, product_id, n):
        """[(product_id, cosine similarity), ...], most similar first."""
        row = self._row[product_id]
        return list(zip(self.bundle["top_ids"][row], self.bundle["top_scores"][row]))[:n]

    def vector(self, product_id):
        return self.bundle["matrix"][self._row[product_id]]

    def cluster_of(self, product_id):
        return self.bundle["labels"][self._row[product_id]]


_cache = {"recommender": None, "loaded": False}
_lock = threading.Lock()


def get_recommender():
    """Load the newest model once per process and keep it in memory (None if not trained yet)."""
    if not _cache["loaded"]:
        with _lock:
            if not _cache["loaded"]:
                bundle = load_latest()
                _cache["recommender"] = Recommender(bundle) if bundle else None
                _cache["loaded"] = True
    return _cache["recommender"]


def reset_cache():
    """Forget the loaded model, so the next request loads the newest version (called after retraining)."""
    with _lock:
        _cache.update(recommender=None, loaded=False)
