# django-voter
Django实现的通用赞踩系统

# django-voter
Django实现的通用赞踩系统

Add django-voter

```python
INSTALLED_APPS = (
  ...
  'voter',
)
```

Mix `MixinVote` in your model, example:

```python
from django.db import models
from voter.models import VoteMixin

class Post(VoteMixin, models.Model): 

    title = models.CharField(max_length=20)

    def __str__(self):
        return self.title
```

Run migrate

```python
manage.py makemigrations
manage.py migrate
```

API Reference 

```python

post = Post.objects.create(title='hello')
user = User.objects.get(username='nyanpasi')

# upvote/downvote/neutralvote(cancel voted) the post by user
# return True if success
# return False if already voted the same or 
# try to cancel an unexisted vote

post.upvote(user)
post.downvote(user)
post.neutralvote(user)

# bulk upvote/downvote/neutralvote(cancel vote) the post by users 
# unvalid user id will be ignored
# return the number of valid user ids
# never return False

post.bulk_upvote(1, 2, 3, 7, 9)
post.bulk_downvote(1, 2, 3, 7, 9)
post.bulk_neutralvote(1, 2, 3, 7, 9)

# check if the post upvoted/downvoted or just voted by user
# return a Boolean

post.is_upvoted(user)
post.is_downvoted(user)
post.is_voted(user)

# get users upvoted/downvoted or just voeted the post
# return a QuerySet of users

post.get_upvoted_users()
post.get_downvoted_users()
post.get_voted_users()

# get all objs upvoted/downvoted or just voted by user
# return a QuerySet of posts or any other model instances

Post.voter.get_user_upvoted(user)
Post.voter.get_user_downvoted(user)
Post.voter.get_user_voted(user)

# all models mixed VoteMixin hava three extra fields

post.up_count
post.down_count
post.upvote_rate
```
