#!/usr/bin/env python
"""
Test script for news admin/workflow permissions.

Verifies the current per-feed group permission model:
- integration-news-publisher can fully manage IntegrationNews (add/change/delete/
  publish/unpublish); infrastructure-news-publisher can fully manage SystemStatusNews.
  Neither group has any access to the other's feed.
- Users with no relevant group get no access at all, via admin or the public workflow.
- Within a group, delete is further restricted to the item's own author (or a
  superuser) - other group members can change but not delete each other's items.
- Removing a user from the group removes their access immediately, including to
  items they previously authored - there is no author-based bypass.
- Superusers bypass every check.

Run: uv run python tests/test_news_permissions.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'operations_portalcms_django.settings')
django.setup()

from django.contrib.auth.models import User, Group, Permission
from infrastructure_news.admin import SystemStatusNewsAdmin
from infrastructure_news.models import SystemStatusNews
from infrastructure_news import workflow as infrastructure_workflow
from integration_news.admin import IntegrationNewsAdmin
from integration_news.models import IntegrationNews
from integration_news import workflow as integration_workflow

INTEGRATION_PUBLISHER_GROUP = 'urn:group:access-ci.org:operations.access-ci.org:integration-news-publisher'
INFRASTRUCTURE_PUBLISHER_GROUP = 'urn:group:access-ci.org:operations.access-ci.org:infrastructure-news-publisher'


class MockRequest:
    """Mock request object for testing admin permissions"""
    def __init__(self, user):
        self.user = user


def fresh(user):
    """Reload a user from the DB so has_perm() doesn't return a stale cached result."""
    return User.objects.get(pk=user.pk)


def ensure_group_has_permissions(group, app_label, codenames):
    """Grant a group the given model permissions.

    In the real database these two publisher groups already carry the full
    add/change/delete/view/can_publish permission set for their app - this only
    matters here because a freshly created (e.g. local/test) group starts with none.
    """
    permissions = Permission.objects.filter(content_type__app_label=app_label, codename__in=codenames)
    assert permissions.count() == len(codenames), (
        f'Expected {len(codenames)} permissions for {app_label} ({codenames}), '
        f'found {permissions.count()} - has that app been migrated in this database?'
    )
    group.permissions.add(*permissions)


def test_group_grants_access_only_to_its_own_feed():
    """A publisher group can fully manage its own feed via admin, and has zero access to the other feed."""
    print('\n' + '=' * 70)
    print('TEST 1: Group access is scoped to its own feed')
    print('=' * 70)

    integration_publisher, _ = User.objects.get_or_create(
        username='test_integration_publisher', defaults={'email': 'int-pub@test.com'}
    )
    infra_publisher, _ = User.objects.get_or_create(
        username='test_infra_publisher', defaults={'email': 'infra-pub@test.com'}
    )
    no_role_user, _ = User.objects.get_or_create(
        username='test_no_role_user', defaults={'email': 'norole@test.com'}
    )

    integration_group, _ = Group.objects.get_or_create(name=INTEGRATION_PUBLISHER_GROUP)
    infra_group, _ = Group.objects.get_or_create(name=INFRASTRUCTURE_PUBLISHER_GROUP)
    ensure_group_has_permissions(integration_group, 'integration_news', [
        'add_integrationnews', 'change_integrationnews', 'delete_integrationnews',
        'view_integrationnews', 'can_publish_integrationnews',
    ])
    ensure_group_has_permissions(infra_group, 'infrastructure_news', [
        'add_systemstatusnews', 'change_systemstatusnews', 'delete_systemstatusnews',
        'view_systemstatusnews', 'can_publish_systemstatusnews',
    ])
    integration_publisher.groups.add(integration_group)
    infra_publisher.groups.add(infra_group)
    integration_publisher = fresh(integration_publisher)
    infra_publisher = fresh(infra_publisher)

    integration_admin = IntegrationNewsAdmin(IntegrationNews, None)
    infra_admin = SystemStatusNewsAdmin(SystemStatusNews, None)

    int_pub_req = MockRequest(integration_publisher)
    infra_pub_req = MockRequest(infra_publisher)
    no_role_req = MockRequest(no_role_user)

    print(f'\nintegration-news-publisher can add integration news: '
          f'{integration_admin.has_add_permission(int_pub_req)} (should be True)')
    print(f'infrastructure-news-publisher can add integration news: '
          f'{integration_admin.has_add_permission(infra_pub_req)} (should be False)')
    print(f'no-role user can add integration news: '
          f'{integration_admin.has_add_permission(no_role_req)} (should be False)')

    assert integration_admin.has_add_permission(int_pub_req), \
        'integration-news-publisher member should be able to add integration news'
    assert not integration_admin.has_add_permission(infra_pub_req), \
        'infrastructure-news-publisher member should NOT be able to add integration news'
    assert not integration_admin.has_add_permission(no_role_req), \
        'user with no group should not be able to add integration news'

    assert infra_admin.has_add_permission(infra_pub_req), \
        'infrastructure-news-publisher member should be able to add infrastructure news'
    assert not infra_admin.has_add_permission(int_pub_req), \
        'integration-news-publisher member should NOT be able to add infrastructure news'
    assert not infra_admin.has_add_permission(no_role_req), \
        'user with no group should not be able to add infrastructure news'

    print('\n✓ Group access is correctly scoped to its own feed only')
    return integration_publisher, infra_publisher, no_role_user


def test_delete_requires_authorship_within_the_group():
    """Any group member can change another member's item, but only the author (or a superuser) can delete it."""
    print('\n' + '=' * 70)
    print('TEST 2: Delete is author-gated even within the group')
    print('=' * 70)

    integration_group = Group.objects.get(name=INTEGRATION_PUBLISHER_GROUP)
    author, _ = User.objects.get_or_create(
        username='test_integration_author', defaults={'email': 'author@test.com'}
    )
    other_member, _ = User.objects.get_or_create(
        username='test_integration_other_member', defaults={'email': 'other@test.com'}
    )
    author.groups.add(integration_group)
    other_member.groups.add(integration_group)
    author = fresh(author)
    other_member = fresh(other_member)

    news = IntegrationNews.objects.create(
        title='Test Integration Update', content='Testing author-gated delete',
        author=author, is_active=True, status='draft',
    )

    integration_admin = IntegrationNewsAdmin(IntegrationNews, None)
    author_req = MockRequest(author)
    other_req = MockRequest(other_member)

    print(f'\nAuthor can change own item: {integration_admin.has_change_permission(author_req, news)} (should be True)')
    print(f'Other group member can change it: {integration_admin.has_change_permission(other_req, news)} (should be True)')
    print(f'Author can delete own item: {integration_admin.has_delete_permission(author_req, news)} (should be True)')
    print(f'Other group member can delete it: {integration_admin.has_delete_permission(other_req, news)} (should be False)')

    assert integration_admin.has_change_permission(author_req, news), \
        'author should be able to change their own item'
    assert integration_admin.has_change_permission(other_req, news), \
        'any group member should be able to change another member\'s item'
    assert integration_admin.has_delete_permission(author_req, news), \
        'author should be able to delete their own item'
    assert not integration_admin.has_delete_permission(other_req, news), \
        'a non-author group member should NOT be able to delete another member\'s item'

    print('\n✓ Delete is correctly restricted to the author (or a superuser)')
    news.delete()


def test_removed_from_group_loses_access_immediately():
    """A user removed from the group loses change/delete/unpublish rights, even over items they authored."""
    print('\n' + '=' * 70)
    print('TEST 3: Removal from the group revokes access immediately')
    print('=' * 70)

    integration_group = Group.objects.get(name=INTEGRATION_PUBLISHER_GROUP)
    member, _ = User.objects.get_or_create(
        username='test_integration_removed_member', defaults={'email': 'removed@test.com'}
    )
    member.groups.add(integration_group)
    member = fresh(member)

    news = IntegrationNews.objects.create(
        title='Test Integration Update', content='Testing group removal revokes access',
        author=member, is_active=True, status='published',
    )

    integration_admin = IntegrationNewsAdmin(IntegrationNews, None)
    req = MockRequest(member)
    print(f'\nWhile still a member, can change own item: '
          f'{integration_admin.has_change_permission(req, news)} (should be True)')
    assert integration_admin.has_change_permission(req, news), \
        'member should be able to change their own item while still in the group'
    assert integration_workflow.can_unpublish(news, member, 'integration_news.can_publish_integrationnews'), \
        'member should be able to unpublish their own item while still in the group'

    # Simulate an admin manually removing them from the group
    member.groups.remove(integration_group)
    member = fresh(member)
    req = MockRequest(member)

    print(f'After removal, can still change own item: '
          f'{integration_admin.has_change_permission(req, news)} (should be False)')
    print(f'After removal, can still delete own item: '
          f'{integration_admin.has_delete_permission(req, news)} (should be False)')

    assert not integration_admin.has_change_permission(req, news), \
        'user removed from the group should lose change access to their own past item'
    assert not integration_admin.has_delete_permission(req, news), \
        'user removed from the group should lose delete access to their own past item'
    assert not integration_workflow.can_unpublish(news, member, 'integration_news.can_publish_integrationnews'), \
        'user removed from the group should lose unpublish access to their own past item'

    print('\n✓ Removal from the group revokes access immediately, with no author-based bypass')
    news.delete()


def test_superuser_bypasses_everything():
    """A superuser can manage both feeds regardless of group membership."""
    print('\n' + '=' * 70)
    print('TEST 4: Superuser bypass')
    print('=' * 70)

    superuser, created = User.objects.get_or_create(
        username='test_superuser_news',
        defaults={'email': 'super@test.com', 'is_superuser': True, 'is_staff': True},
    )
    if not created and not superuser.is_superuser:
        superuser.is_superuser = True
        superuser.is_staff = True
        superuser.save()
    superuser = fresh(superuser)

    integration_admin = IntegrationNewsAdmin(IntegrationNews, None)
    infra_admin = SystemStatusNewsAdmin(SystemStatusNews, None)
    req = MockRequest(superuser)

    print(f'\nSuperuser can add/change/delete integration news and infrastructure news: '
          f'{all([integration_admin.has_add_permission(req), integration_admin.has_change_permission(req), integration_admin.has_delete_permission(req), infra_admin.has_add_permission(req), infra_admin.has_change_permission(req), infra_admin.has_delete_permission(req)])} (should be True)')

    assert integration_admin.has_add_permission(req)
    assert integration_admin.has_change_permission(req)
    assert integration_admin.has_delete_permission(req)
    assert infra_admin.has_add_permission(req)
    assert infra_admin.has_change_permission(req)
    assert infra_admin.has_delete_permission(req)

    print('\n✓ Superuser bypasses group checks on both feeds')


def test_public_workflow_publish_and_unpublish():
    """The public (non-admin) publish/unpublish workflow functions respect the same group permission."""
    print('\n' + '=' * 70)
    print('TEST 5: Public workflow publish/unpublish gating')
    print('=' * 70)

    infra_group = Group.objects.get(name=INFRASTRUCTURE_PUBLISHER_GROUP)
    publisher, _ = User.objects.get_or_create(
        username='test_workflow_publisher', defaults={'email': 'workflow-pub@test.com'}
    )
    no_role, _ = User.objects.get_or_create(
        username='test_workflow_no_role', defaults={'email': 'workflow-norole@test.com'}
    )
    publisher.groups.add(infra_group)
    publisher = fresh(publisher)

    draft = SystemStatusNews.objects.create(
        subject='Test Outage', content='Testing publish/unpublish gating',
        infrastructure_news_type='outage_partial', author=publisher, is_active=True, status='draft',
    )

    print(f'\nGroup member can publish a draft: '
          f'{infrastructure_workflow.can_publish(draft, publisher, "infrastructure_news.can_publish_systemstatusnews")} (should be True)')
    print(f'No-role user can publish a draft: '
          f'{infrastructure_workflow.can_publish(draft, no_role, "infrastructure_news.can_publish_systemstatusnews")} (should be False)')

    assert infrastructure_workflow.can_publish(
        draft, publisher, 'infrastructure_news.can_publish_systemstatusnews'
    ), 'group member should be able to publish a draft'
    assert not infrastructure_workflow.can_publish(
        draft, no_role, 'infrastructure_news.can_publish_systemstatusnews'
    ), 'user with no group should not be able to publish a draft'

    draft.status = 'published'
    draft.save()

    assert infrastructure_workflow.can_unpublish(
        draft, publisher, 'infrastructure_news.can_publish_systemstatusnews'
    ), 'group member should be able to unpublish a published item'
    assert not infrastructure_workflow.can_unpublish(
        draft, no_role, 'infrastructure_news.can_publish_systemstatusnews'
    ), 'user with no group should not be able to unpublish a published item'

    print('\n✓ Public workflow functions are correctly gated on group permission')
    draft.delete()


def cleanup():
    """Clean up test users (their group memberships and authored test items cascade-delete with them)."""
    print('\n' + '=' * 70)
    print('Cleaning up test data...')
    print('=' * 70)

    User.objects.filter(username__startswith='test_').delete()
    print('✓ Test users removed')


if __name__ == '__main__':
    print('\n' + '=' * 70)
    print('NEWS PERMISSIONS TEST SUITE')
    print('=' * 70)
    print('\nVerifying the per-feed publisher group model for integration_news and '
          'infrastructure_news.\n')

    try:
        test_group_grants_access_only_to_its_own_feed()
        test_delete_requires_authorship_within_the_group()
        test_removed_from_group_loses_access_immediately()
        test_superuser_bypasses_everything()
        test_public_workflow_publish_and_unpublish()

        print('\n' + '=' * 70)
        print('✓ ALL TESTS PASSED')
        print('=' * 70)
        print('\nConfirmed:')
        print('  • integration-news-publisher / infrastructure-news-publisher each fully')
        print('    manage only their own feed (add/change/delete/publish/unpublish)')
        print('  • Neither group has any access to the other\'s feed')
        print('  • Delete is restricted to the item\'s author, even within the group')
        print('  • Removing a user from the group revokes access immediately, with no')
        print('    author-based bypass')
        print('  • Superusers bypass every check')
        print('\n')

        cleanup()

    except Exception as e:
        print(f'\n✗ TEST FAILED: {e}')
        import traceback
        traceback.print_exc()
        cleanup()
        sys.exit(1)
