from django.shortcuts import render


def custom_404(request, exception=None):
    return render(request, 'core/errors/404.html', status=404)

def custom_502(request, exception=None):
    return render(request, 'core/errors/502.html', status=502)

def custom_500(request, exception=None):
    return render(request, 'core/errors/500.html', status=500)

def custom_403(request, exception=None):
    return render(request, 'core/errors/403.html', status=403)

def custom_401(request, exception=None):
    return render(request, 'core/errors/401.html', status=401)

def custom_429(request, exception=None):
    return render(request, 'core/errors/429.html', status=429)

def custom_503(request, exception=None):
    return render(request, 'core/errors/503.html', status=503)
