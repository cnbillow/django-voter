from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import F
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey, ContentType

# Create your models here.

class VoteReference(models.Model):
    """
    赞踩记录模型, 包含对所有模型实例的赞踩记录
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created = models.DateTimeField(default=timezone.now)
    upvote = models.BooleanField()

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-created',]
        verbose_name = "VotedItemRecord"
        verbose_name_plural = "VoteReference"

    def __str__(self):
        if self.upvote:
            return self.user.username + " upvoted " + str(self.content_object)
        else:
            return self.user.username + " downvoted " + str(self.content_object)

class VoteManager(models.Manager):
    """
    提供表级别的赞踩相关操作, 例如获得指定user赞/踩过的该类实例
    """
    def _get_user_voted(self, user, upvote=None):
        self_type = ContentType.objects.get_for_model(self.model)
        qs = VoteReference.objects.filter(user=user, content_type__pk=self_type.id)
        if upvote is None:
            vote_qs = qs
        else:
            vote_qs = qs.filter(upvote=upvote)
        ids = [r.get('object_id') for r in vote_qs.values('object_id')]
        return self.get_queryset().filter(id__in=ids)

    def get_user_voted(self, user):
        return self._get_user_voted(user=user)

    def get_user_upvoted(self, user):
        return self._get_user_voted(user=user, upvote=True)

    def get_user_downvoted(self, user):
        return self._get_user_voted(user=user, upvote=False)

    def get_popular(self, min_upvote_rate=0.7, min_up_count=10, limit=20):
        qs = self.get_queryset().filter(
            upvote_rate__gte=min_upvote_rate, 
            up_count__gte=min_up_count
        ).order_by('-up_count')
        return qs[:limit] if limit else qs


class VoteMixin(models.Model):
    """
    mixin , provides filelds and methods
    """
    up_count = models.PositiveIntegerField(default=0)
    down_count = models.PositiveIntegerField(default=0)
    upvote_rate = models.FloatField(default=0)
    vote_reference = GenericRelation(VoteReference)
    voter = VoteManager()
    objects = models.Manager()

    class Meta:
        abstract = True

    def _vote(self, user, upvote):
        r = self.vote_reference.filter(user=user).first()
        if not r:
            self.vote_reference.create(upvote=upvote, user=user)
            if upvote:
                self.up_count += 1
                self.upvote_rate = self.get_upvote_rate()
                self.__class__.objects.filter(id=self.id).update(
                    up_count=F('up_count')+1, 
                    upvote_rate=self.upvote_rate
                )
            else:
                self.down_count += 1
                self.upvote_rate = self.get_upvote_rate()
                self.__class__.objects.filter(id=self.id).update(
                    down_count=F('down_count')+1, 
                    upvote_rate=self.upvote_rate
                )
            return True
        else:
            if upvote != r.upvote:
                if upvote:
                    self.up_count += 1
                    self.down_count -= 1
                    self.upvote_rate = self.get_upvote_rate()
                    self.__class__.objects.filter(id=self.id).update(
                        down_count=F('down_count')-1, 
                        up_count=F('up_count')+1, 
                        upvote_rate=self.upvote_rate
                    )
                    self.vote_reference.filter(id=r.id).update(upvote=True)
                else:
                    self.up_count -= 1
                    self.down_count += 1
                    self.upvote_rate = self.get_upvote_rate()
                    self.__class__.objects.filter(id=self.id).update(
                        down_count=F('down_count')+1, 
                        up_count=F('up_count')-1, 
                        upvote_rate=self.upvote_rate
                    )
                    self.vote_reference.filter(id=r.id).update(upvote=False)
                return True
            else:
                return False

    def upvote(self, user):
        return self._vote(user, upvote=True)

    def downvote(self, user):
        return self._vote(user, upvote=False)

    def neutralvote(self, user):
        """ cancel vote """
        r = self.vote_reference.filter(user=user).first()
        if r:
            r.delete()
            if r.upvote:
                self.up_count -= 1 
                self.upvote_rate = self.get_upvote_rate()
                self.__class__.objects.filter(id=self.id).update(
                    up_count=F('up_count')-1, 
                    upvote_rate=self.upvote_rate
                )
            else:
                self.down_count -= 1
                self.upvote_rate = self.get_upvote_rate()
                self.__class__.objects.filter(id=self.id).update(
                    down_count=F('down_count')-1, 
                    upvote_rate=self.upvote_rate
                )
            return True
        else:
            return False

    def get_upvote_rate(self):
        return self._calc_upvote_rate(self.up_count, self.down_count)

    @staticmethod
    def _calc_upvote_rate(up_count, down_count):
        total_vote_count = up_count + down_count
        base = total_vote_count if total_vote_count else 1
        upvote_rate = round((up_count/base), 2)
        return upvote_rate

    def _get_voted_users(self, upvote=None):
        qs = self.vote_reference.all()
        if upvote is None:
            vote_qs = qs
        else:
            vote_qs = qs.filter(upvote=upvote)
        user_ids = [r.get('user') for r in vote_qs.values('user')]
        return get_user_model().objects.filter(id__in=user_ids)

    def get_upvoted_users(self):
        return self._get_voted_users(upvote=True)

    def get_downvoted_users(self):
        return self._get_voted_users(upvote=False)

    def get_voted_users(self):
        return self._get_voted_users(upvote=None)

    def is_upvoted(self, user):
        return self.vote_reference.filter(user=user, upvote=True).exists()

    def is_downvoted(self, user):
        return self.vote_reference.filter(user=user, upvote=False).exists()

    def is_voted(self, user):
        return self.vote_reference.filter(user=user).exists()

    def _bulk_vote(self, user_ids, upvote):
        """
        批量操作, 会在常数次查询内完成
        """
        self._bulk_neutralvote(user_ids)

        users = get_user_model().objects.filter(id__in=user_ids)
        self_type = ContentType.objects.get_for_model(self.__class__)
        ready_records = [VoteReference(
            content_type=self_type, 
            object_id=self.id, 
            user=user, 
            upvote=upvote
        ) for user in users]
        VoteReference.objects.bulk_create(ready_records)
        if upvote:
            self.up_count +=  len(users)
            self.upvote_rate = self.get_upvote_rate()
            self.__class__.objects.filter(id=self.id).update(
                up_count=F('up_count')+len(users),
                upvote_rate=self.upvote_rate
            )
        else:
            self.down_count += len(users)
            self.upvote_rate = self.get_upvote_rate()
            self.__class__.objects.filter(id=self.id).update(
                down_count=F('down_count')+len(users),
                upvote_rate=self.upvote_rate
            )
        return len(users)

    def bulk_upvote(self, *user_ids):
        print(user_ids)
        return self._bulk_vote(user_ids, upvote=True)

    def bulk_downvote(self, *user_ids):
        return self._bulk_vote(user_ids, upvote=False)

    def _bulk_neutralvote(self, user_ids):
        upvoted_record_count = self.vote_reference.filter(user__id__in=user_ids, upvote=True).count()
        downvoted_record_count = self.vote_reference.filter(user__id__in=user_ids, upvote=False).count()
        self.vote_reference.filter(user__id__in=user_ids).delete()
        self.up_count -= upvoted_record_count
        self.down_count -= downvoted_record_count
        self.upvote_rate = self.get_upvote_rate()
        self.__class__.objects.filter(id=self.id).update(
            up_count=F('up_count')-upvoted_record_count,
            down_count=F('down_count')-downvoted_record_count,
            upvote_rate=self.upvote_rate
        )
        return upvoted_record_count + downvoted_record_count

    def bulk_neutralvote(self, *user_ids):
        return self._bulk_neutralvote(user_ids)

