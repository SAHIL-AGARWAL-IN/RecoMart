"""python manage.py train_recommender [--k N] [--k-min 3] [--k-max 12]

Trains the recommendation model offline and prints every step, so the results can be
checked (and explained in the viva): data quality, feature matrix, choice of K, clusters
and a few sample recommendations.
"""
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from recommender import features, services
from store.models import Product


class Command(BaseCommand):
    help = "Train the K-Means + cosine-similarity recommender and save it with Joblib."

    def add_arguments(self, parser):
        parser.add_argument("--k", type=int, help="Use this many clusters instead of the best-silhouette K.")
        parser.add_argument("--k-min", type=int, default=settings.RECOMMENDER["K_MIN"])
        parser.add_argument("--k-max", type=int, default=settings.RECOMMENDER["K_MAX"])

    def handle(self, *args, **options):
        frame = features.load_product_frame()
        if len(frame) < 4:
            raise CommandError("Need at least 4 active products to train. Run: python manage.py seed_data")

        self.section("1. Dataset")
        self.stdout.write(f"  Dataset size: {len(frame)} products, {frame['category'].nunique()} categories, "
                          f"{frame['brand'].nunique()} brands")
        self.stdout.write("  Missing values: " + ", ".join(f"{col}={n}" for col, n in features.missing_values(frame).items()))
        activity = frame[features.ACTIVITY_COLUMNS].sum()
        self.stdout.write("  Shopper activity (last 90 days, simulated by seed_data): "
                          + ", ".join(f"{col}={int(n)}" for col, n in activity.items()))

        bundle, path, _ = services.train_and_save(k=options["k"], k_min=options["k_min"], k_max=options["k_max"])
        matrix = bundle["matrix"]

        self.section("2. Feature matrix")
        self.stdout.write(f"  Feature matrix shape: {matrix.shape[0]} products x {matrix.shape[1]} features")
        self.stdout.write(f"  NaN values: {int(np.isnan(matrix).sum())}")
        norms = np.linalg.norm(matrix, axis=1)
        self.stdout.write(f"  Row lengths (L2 norm): min {norms.min():.4f}, max {norms.max():.4f}")

        self.section("3. Choosing K (K-Means)")
        self.stdout.write(f"  {'K':>3}  {'inertia':>10}  {'silhouette':>10}")
        for row in bundle["k_scores"]:
            marks = []
            if row["k"] == bundle["best_k"]:
                marks.append("best silhouette")
            if row["k"] == bundle["elbow_k"]:
                marks.append("elbow")
            note = f"  <- {', '.join(marks)}" if marks else ""
            self.stdout.write(f"  {row['k']:>3}  {row['inertia']:>10.3f}  {row['silhouette']:>10.4f}{note}")
        how = "forced with --k" if options["k"] else "best silhouette score"
        self.stdout.write(self.style.SUCCESS(f"  Chosen K = {bundle['k']} ({how}), silhouette = {bundle['silhouette']:.4f}"))

        self.section("4. Cluster sizes")
        names = dict(Product.objects.filter(id__in=bundle["product_ids"]).values_list("id", "name"))
        categories = dict(zip(frame["id"], frame["category"]))
        for cluster, size in sorted(bundle["cluster_sizes"].items()):
            member_categories = [categories[pid] for pid, label in zip(bundle["product_ids"], bundle["labels"])
                                 if label == cluster]
            top = max(set(member_categories), key=member_categories.count)
            share = member_categories.count(top) / size
            self.stdout.write(f"  Cluster {cluster:>2}: {size:>3} products (mostly {top}, {share:.0%})")

        self.section("5. Sample recommendations")
        for row in np.linspace(0, len(bundle["product_ids"]) - 1, 3).astype(int):
            product_id = bundle["product_ids"][row]
            self.stdout.write(f"  {names[product_id]}")
            for pid, score in zip(bundle["top_ids"][row][:4], bundle["top_scores"][row][:4]):
                self.stdout.write(f"      {score:.3f}  {names[pid]}")


        self.section("6. Saved")
        self.stdout.write(self.style.SUCCESS(
            f"  Saved model v{bundle['version']} to {path} ({path.stat().st_size / 1024:.0f} KB) "
            f"in {bundle['duration_seconds']}s"))

    def section(self, title):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{title}"))
