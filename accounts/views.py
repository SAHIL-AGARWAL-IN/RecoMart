from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, ProfileForm, RegisterForm


class RecoMartLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Welcome back, {form.get_user().first_name or form.get_user().username}.")
        return super().form_valid(form)


def register(request):
    if request.user.is_authenticated:
        return redirect("store:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)  # passwords are hashed by UserCreationForm.save()
        messages.success(request, f"Account created. Welcome to RecoMart, {user.first_name}.")
        next_url = request.POST.get("next", "")
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("store:home")
    return render(request, "accounts/register.html", {"form": form, "next": request.GET.get("next", "")})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile saved.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {
        "form": form,
        "order_count": request.user.orders.count(),
        "review_count": request.user.reviews.count(),
        "wishlist_count": request.user.wishlist_items.count(),
    })
