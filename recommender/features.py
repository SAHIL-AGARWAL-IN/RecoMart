"""Turn every product into a vector of numbers (its "feature vector").

The vector combines:
  * TF-IDF of the product's words (name, brand, category, description): what it is
  * one-hot category and brand: where it belongs
  * scaled price, rating and recent shopper activity: how it sells

Each row is finally scaled to length 1 (L2 normalisation), so the dot product of two
rows equals their cosine similarity.
"""
from datetime import timedelta

import numpy as np
import pandas as pd
from django.db.models import Count, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, MinMaxScaler, Normalizer, OneHotEncoder

ACTIVITY_DAYS = 90
ACTIVITY_COLUMNS = ["views", "carts", "wishlists", "purchases"]
COLUMNS = ["id", "name", "brand", "category", "description", "price", "rating_avg", *ACTIVITY_COLUMNS, "stock"]

# How much each block of features counts. Words and category matter most; price and
# popularity only nudge the result, so a cheap phone still matches an expensive phone.
BLOCK_WEIGHTS = {"text": 1.0, "category": 1.0, "brand": 0.4, "numbers": 0.3, "rating": 0.2}


# ----------------------------------------------------------------- data
def load_product_frame():
    """Active products from the database as a Pandas DataFrame, with 90-day activity counts."""
    from store.models import Product  # imported here so this module can be used without Django apps loaded

    since = timezone.now() - timedelta(days=ACTIVITY_DAYS)

    def activity(kind):
        return Count("interactions", filter=Q(interactions__interaction_type=kind,
                                              interactions__timestamp__gte=since))

    rows = (Product.objects.filter(is_active=True)
            .annotate(effective=Coalesce("discount_price", "price"),
                      views=activity("view"), carts=activity("cart"),
                      wishlists=activity("wishlist"), purchases=activity("purchase"))
            .order_by("id")
            .values("id", "name", "brand", "category__name", "description", "effective", "rating_avg",
                    *ACTIVITY_COLUMNS, "stock"))
    frame = pd.DataFrame.from_records(rows)
    if frame.empty:
        return pd.DataFrame(columns=COLUMNS)
    frame = frame.rename(columns={"category__name": "category", "effective": "price"})
    frame["price"] = frame["price"].astype(float)
    frame["rating_avg"] = frame["rating_avg"].astype(float)
    return frame[COLUMNS]


def missing_values(frame):
    """{column: number of empty values}. Printed by train_recommender as a data-quality check."""
    blanks = frame.replace("", np.nan)
    return {column: int(blanks[column].isna().sum()) for column in frame.columns}


# ------------------------------------------------------------- pipeline
def prepare(frame):
    """Clean the raw columns and add one combined 'text' column for TF-IDF."""
    frame = frame.copy()
    for column in ("name", "brand", "category", "description"):
        frame[column] = frame[column].fillna("").astype(str)
    for column in ("price", "rating_avg", *ACTIVITY_COLUMNS):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    frame["text"] = frame["name"] + " " + frame["brand"] + " " + frame["category"] + " " + frame["description"]
    return frame


def build_pipeline():
    """The scikit-learn Pipeline that turns a product DataFrame into normalised vectors."""
    log_then_scale = Pipeline([
        ("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),  # tames huge prices like a Rolex
        ("scale", MinMaxScaler()),
    ])
    columns = ColumnTransformer(
        transformers=[
            ("text", TfidfVectorizer(max_features=300, stop_words="english", sublinear_tf=True,
                                     token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b"), "text"),
            ("category", OneHotEncoder(handle_unknown="ignore"), ["category"]),
            ("brand", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=2), ["brand"]),
            ("numbers", log_then_scale, ["price", *ACTIVITY_COLUMNS]),
            ("rating", MinMaxScaler(), ["rating_avg"]),
        ],
        transformer_weights=BLOCK_WEIGHTS,
    )
    return Pipeline([
        ("prepare", FunctionTransformer(prepare)),
        ("columns", columns),
        ("l2", Normalizer(norm="l2")),
    ])


def to_matrix(result):
    """A plain dense NumPy array (the catalog is small, so dense is simplest)."""
    return result.toarray() if sparse.issparse(result) else np.asarray(result, dtype=float)
