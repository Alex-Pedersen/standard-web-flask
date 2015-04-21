from datetime import datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from standardweb import celery, db, app
from standardweb.lib import api, email, notifications, realtime
from standardweb.models import ForumPost, ForumTopicSubscription, Notification, Player, PlayerStats, User


@celery.task()
def notify(notification_id):
    notification = Notification.query.get(notification_id)

    user = notification.user
    player = notification.player

    if user:
        realtime.unread_notification_count(user)
        email.send_notification_email(user, notification)

    if notification.can_notify_ingame and player:
        api.new_notification(player, notification)


@celery.task()
def notify_news_post_all(forum_post_id):
    # Create notifications for the players active in the past month or all users with valid emails
    recipients = db.session.query(
        Player.id, User.id
    ).outerjoin(
        User
    ).join(
        PlayerStats
    ).filter(
        or_(
            and_(
                PlayerStats.server_id == app.config.get('MAIN_SERVER_ID'),
                PlayerStats.last_seen > datetime.utcnow() - timedelta(days=30)
            ),
            User.email != None
        )
    ).distinct(
        Player.id, User.id
    ).all()

    for player_id, user_id in recipients:
        Notification.create(
            notifications.NEWS_POST,
            user_id=user_id,
            player_id=player_id,
            post_id=forum_post_id
        )


@celery.task()
def notify_subscribed_topic_post(forum_post_id):
    post = ForumPost.query.get(forum_post_id)
    topic = post.topic

    subscriptions = ForumTopicSubscription.query.options(
        joinedload(ForumTopicSubscription.user)
    ).filter(
        ForumTopicSubscription.topic == topic,
        ForumTopicSubscription.user_id != post.user_id
    ).all()

    for subscription in subscriptions:
        Notification.create(
            notifications.SUBSCRIBED_TOPIC_POST,
            user_id=subscription.user.id,
            player_id=subscription.user.player_id,
            post_id=forum_post_id
        )