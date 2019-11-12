from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import F
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey, ContentType
from .managers import VoteManager

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
        return self.user.username +" voted to " + str(self.content_object)


class VoteManager(models.Manager):
    """
    提供表级别的赞踩相关操作
    """
    def get_upvoted(self, user):
        self_type = ContentType.objects.get_for_model(self.model)
        vote_qs = VoteReference.objects.filter(
            user=user, 
            upvote=True,
            content_type__pk=self_type.id
        )
        ids = [r.get('object_id') for r in vote_qs.values('object_id')]
        return self.get_queryset().filter(id__in=ids)

    def get_downvoted(self, user):
        self_type = ContentType.objects.get_for_model(self.model)
        vote_qs = VoteReference.objects.filter(
            user=user, 
            upvote=False,
            content_type__pk=self_type.id
        )
        ids = [r.get('object_id') for r in vote_qs.values('object_id')]
        return self.get_queryset().filter(id__in=vote_qs)

    def get_popular(self, min_upvote_rate=0.7, min_up_count=10, limit=20):
        qs = self.get_queryset().filter(
            upvote_rate__gte=min_upvote_rate, 
            up_count__gte=min_up_count
        ).order_by('-up_count')
        return qs[:limit] if limit else qs


class VoteMixin(models.Model):
    """
    混入类, 为任何Model提供赞踩字段和相关方法
    """
    up_count = models.PositiveIntegerField(default=0)
    down_count = models.PositiveIntegerField(default=0)
    upvote_rate = models.FloatField(default=0)
    vote_reference = GenericRelation(VoteReference)
    voter = VoteManager()
    objects = models.Manager()

    class Meta:
        abstract = True

    def vote(self, user, upvote):
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

    def voteneutral(self, user):
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

    def get_upvote_rate(self):
        return self._calc_upvote_rate(self.up_count, self.down_count)

    @staticmethod
    def _calc_upvote_rate(up_count, down_count):
        total_vote_count = up_count + down_count
        base = total_vote_count if total_vote_count else 1
        upvote_rate = round((up_count/base), 2)
        return upvote_rate

    def get_voted_user(self, upvote=True):
        vote_qs = self.vote_reference.filter(upvote=upvote).values('user')
        user_ids = [r.get('user') for r in vote_qs]
        return get_user_model().objects.filter(id__in=user_ids)

    def is_upvoted(self, user):
        return self.vote_reference.filter(user=user, upvote=True).exists()

    def is_downvoted(self, user):
        return self.vote_reference.filter(user=user, upvote=False).exists()

    def bulk_vote(self, users_pk, upvote):
        """
        批量操作, 会在常数次查询内完成
        """
        existed_record_count = self.vote_reference.filter(user__id__in=users_pk, upvote=upvote).count()
        conflicted_record_count = self.vote_reference.filter(user__id__in=users_pk, upvote=not upvote).count()
        if upvote:
            self.up_count -= existed_record_count
            self.down_count -= conflicted_record_count
            self.__class__.objects.filter(id=self.id).update(
                up_count=F('up_count')-existed_record_count,
                down_count=F('down_count')-conflicted_record_count
            )
        else:
            self.down_count -= existed_record_count
            self.up_count -= conflicted_record_count
            self.__class__.objects.filter(id=self.id).update(
                down_count=F('down_count')-existed_record_count,
                up_count=F('up_count')-conflicted_record_count
            )

        self.vote_reference.filter(user__id__in=users_pk).delete()

        users = get_user_model().objects.filter(id__in=users_pk)
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
