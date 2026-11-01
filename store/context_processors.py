from .models import Category


def store_nav(request):
    """Data every page needs for the navbar and footer."""
    return {"nav_categories": Category.objects.all()}
