from .forms import LoginForm, RegistrationForm


def auth_forms(request):
    """Provide login/register forms globally for templates (e.g., base.html header modals)."""
    if request.user.is_authenticated:
        return {"login_form": None, "register_form": None}

    return {
        "login_form": LoginForm(),
        "register_form": RegistrationForm(),
    }