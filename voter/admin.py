from django.contrib import admin
from .models import VoteReference

# Register your models here.

@admin.register(VoteReference)
class VoteReferenceAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user', 
        'upvote', 
        'created', 
        'content_type', 
        'object_id', 
        'content_object'
        )