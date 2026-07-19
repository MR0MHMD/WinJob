from django.shortcuts import render, get_object_or_404
from .models import Post, PostComments, BlogCategory
from django.db.models import Count
from django.http import JsonResponse
from accounts.models import CustomUser


def post_list(request):
    hot_post = Post.published.first()
    latest_post = Post.published.all().order_by('-created_at').exclude(id=hot_post.id)[:4]
    Controversial_post = Post.published.annotate(comment_count=Count('comments')).order_by('-comment_count')[:5]
    categories = BlogCategory.objects.all()

    context = {
        "hot_post": hot_post,
        "latest_post": latest_post,
        "Controversial_post": Controversial_post,
        "categories": categories,
    }
    return render(request, 'blog/pages/post_list.html', context)


def post_detail(request, id, slug):
    post = get_object_or_404(Post, id=id, slug=slug)
    comments = post.comments.filter(parent_comment=None)
    latest_post = Post.published.all().order_by('-created_at').exclude(id=post.id)[:3]
    Controversial_post = Post.published.annotate(comment_count=Count('comments')).order_by('-comment_count').exclude(id=post.id)[:3]


    context = {
        "post": post,
        "comments": comments,
        "latest_post": latest_post,
        "Controversial_post": Controversial_post,
    }

    return render(request, 'blog/pages/post_detail.html', context)


def post_comment(request, id, slug, parent_id=None):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=id, slug=slug)

        parent_comment = None
        if parent_id:
            parent_comment = get_object_or_404(PostComments, id=parent_id)

        if request.user.is_authenticated:
            user = request.user
            name = None
        else:
            name = request.POST.get('name')
            user = None

        content = request.POST.get('content')

        # ساخت کامنت جدید
        comment = PostComments(
            post=post,
            user=user,
            name=name,
            content=content,
            parent_comment=parent_comment
        )

        comment.save()

        return JsonResponse({"message": "کامنت با موفقیت ارسال شد!"}, status=200)

    return JsonResponse({"message": "فقط درخواست‌های POST پذیرفته می‌شود!"}, status=400)


def person_posts(request, id):
    user = get_object_or_404(CustomUser, id=id)
    posts = user.posts.all()

    context = {
        "user": user,
        "posts": posts,
    }

    return render(request, 'blog/pages/person_posts.html', context)
