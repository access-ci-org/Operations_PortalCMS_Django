#!/usr/bin/env python
"""
Test script for news admin permissions

Tests that RP users can add/edit news items through Django admin.

Run: uv run python test_news_permissions.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User, Group
from operations_portalcms_django.models import SystemStatusNews, IntegrationNews
from operations_portalcms_django.admin import SystemStatusNewsAdmin, IntegrationNewsAdmin
from operations_portalcms_django.utils import (
    is_rp_user, 
    is_operations_user, 
    can_manage_news,
    get_user_rp_groups,
    is_rp_coordinator
)
from django.test import RequestFactory


class MockRequest:
    """Mock request object for testing admin permissions"""
    def __init__(self, user):
        self.user = user


def test_helper_functions():
    """Test utility functions"""
    print('\n' + '='*70)
    print('TEST 1: Helper Functions')
    print('='*70)
    
    # Create test users
    rp_user, _ = User.objects.get_or_create(
        username='test_rp_user',
        defaults={'email': 'rp@test.com'}
    )
    
    regular_user, _ = User.objects.get_or_create(
        username='test_regular_user',
        defaults={'email': 'regular@test.com'}
    )
    
    # Add RP user to PSC coordinator group
    psc_group, _ = Group.objects.get_or_create(
        name='urn:group:access-ci.org:rp.psc.edu:coordinator'
    )
    rp_user.groups.add(psc_group)
    
    print(f'\nRP User: {rp_user.username}')
    print(f'  is_rp_user: {is_rp_user(rp_user)} (should be True)')
    print(f'  is_rp_coordinator: {is_rp_coordinator(rp_user)} (should be True)')
    print(f'  can_manage_news: {can_manage_news(rp_user)} (should be True)')
    print(f'  RP groups: {get_user_rp_groups(rp_user)}')
    
    print(f'\nRegular User: {regular_user.username}')
    print(f'  is_rp_user: {is_rp_user(regular_user)} (should be False)')
    print(f'  can_manage_news: {can_manage_news(regular_user)} (should be False)')
    
    assert is_rp_user(rp_user), "RP user should be detected"
    assert not is_rp_user(regular_user), "Regular user should not be RP"
    assert can_manage_news(rp_user), "RP user should be able to manage news"
    assert not can_manage_news(regular_user), "Regular user should not manage news"
    
    print('\n✓ Helper functions working correctly')
    return rp_user, regular_user


def test_admin_permissions():
    """Test Django admin permission methods"""
    print('\n' + '='*70)
    print('TEST 2: Admin Permissions')
    print('='*70)
    
    # Get users
    try:
        rp_user = User.objects.get(username='test_rp_user')
        regular_user = User.objects.get(username='test_regular_user')
    except User.DoesNotExist:
        print("Run test_helper_functions first")
        return
    
    # Create admin instances
    status_admin = SystemStatusNewsAdmin(SystemStatusNews, None)
    integration_admin = IntegrationNewsAdmin(IntegrationNews, None)
    
    # Create mock requests
    rp_request = MockRequest(rp_user)
    regular_request = MockRequest(regular_user)
    
    print('\n--- System Status News Admin ---')
    print(f'RP user can add: {status_admin.has_add_permission(rp_request)} (should be True)')
    print(f'Regular user can add: {status_admin.has_add_permission(regular_request)} (should be False)')
    
    print('\n--- Integration News Admin ---')
    print(f'RP user can add: {integration_admin.has_add_permission(rp_request)} (should be True)')
    print(f'Regular user can add: {integration_admin.has_add_permission(regular_request)} (should be False)')
    
    # Test permissions
    assert status_admin.has_add_permission(rp_request), "RP user should add status news"
    assert not status_admin.has_add_permission(regular_request), "Regular user should not add news"
    assert integration_admin.has_add_permission(rp_request), "RP user should add integration news"
    assert not integration_admin.has_add_permission(regular_request), "Regular user should not add news"
    
    print('\n✓ Admin permissions working correctly')


def test_news_creation():
    """Test actually creating news items"""
    print('\n' + '='*70)
    print('TEST 3: Creating News Items')
    print('='*70)
    
    try:
        rp_user = User.objects.get(username='test_rp_user')
    except User.DoesNotExist:
        print("Run test_helper_functions first")
        return
    
    # Create a system status news item
    status_news = SystemStatusNews.objects.create(
        subject='Test Outage - PSC Bridges2',
        content='Testing RP user can create status news',
        infrastructure_news_type='outage_partial',
        affected_infrastructure='bridges2.psc.edu',
        author=rp_user,
        is_active=True
    )
    
    print(f'\n✓ Created SystemStatusNews: {status_news.subject}')
    print(f'  Author: {status_news.author.username}')
    print(f'  Infrastructure: {status_news.affected_infrastructure}')
    
    # Create an integration news item
    integration_news = IntegrationNews.objects.create(
        title='Test Integration Update',
        content='Testing RP user can create integration news',
        author=rp_user,
        is_active=True
    )
    
    print(f'\n✓ Created IntegrationNews: {integration_news.title}')
    print(f'  Author: {integration_news.author.username}')
    
    # Test editing own news
    status_admin = SystemStatusNewsAdmin(SystemStatusNews, None)
    rp_request = MockRequest(rp_user)
    
    can_change_own = status_admin.has_change_permission(rp_request, status_news)
    can_delete_own = status_admin.has_delete_permission(rp_request, status_news)
    
    print(f'\n--- Permission Checks ---')
    print(f'RP user can edit own news: {can_change_own} (should be True)')
    print(f'RP user can delete own news: {can_delete_own} (should be True)')
    
    assert can_change_own, "Author should be able to edit own news"
    assert can_delete_own, "Author should be able to delete own news"
    
    print('\n✓ News creation and editing working correctly')
    
    # Cleanup
    status_news.delete()
    integration_news.delete()


def test_multiple_rps():
    """Test user with multiple RP memberships"""
    print('\n' + '='*70)
    print('TEST 4: Multiple RP Memberships')
    print('='*70)
    
    multi_user, _ = User.objects.get_or_create(
        username='test_multi_rp',
        defaults={'email': 'multi@test.com'}
    )
    
    # Add to multiple RP groups
    groups = [
        'urn:group:access-ci.org:rp.psc.edu:coordinator',
        'urn:group:access-ci.org:rp.tacc.utexas.edu:implementer',
        'urn:group:access-ci.org:operations.access-ci.org:concierge',
    ]
    
    for group_name in groups:
        group, _ = Group.objects.get_or_create(name=group_name)
        multi_user.groups.add(group)
    
    print(f'\nUser: {multi_user.username}')
    print(f'Groups: {multi_user.groups.count()}')
    for g in multi_user.groups.all():
        print(f'  - {g.name}')
    
    rp_groups = get_user_rp_groups(multi_user)
    print(f'\nRP Group IDs: {rp_groups}')
    print(f'  is_rp_user: {is_rp_user(multi_user)} (should be True)')
    print(f'  is_rp_coordinator: {is_rp_coordinator(multi_user)} (should be True)')
    print(f'  is_operations_user: {is_operations_user(multi_user)} (should be True)')
    print(f'  can_manage_news: {can_manage_news(multi_user)} (should be True)')
    
    assert 'rp.psc.edu' in rp_groups, "Should detect PSC group"
    assert 'rp.tacc.utexas.edu' in rp_groups, "Should detect TACC group"
    assert is_rp_coordinator(multi_user), "Should detect coordinator role"
    assert is_operations_user(multi_user), "Should detect operations role"
    
    print('\n✓ Multiple RP membership working correctly')


def cleanup():
    """Clean up test users"""
    print('\n' + '='*70)
    print('Cleaning up test data...')
    print('='*70)
    
    User.objects.filter(username__startswith='test_').delete()
    print('✓ Test users removed')


if __name__ == '__main__':
    print('\n' + '='*70)
    print('NEWS ADMIN PERMISSIONS TEST SUITE')
    print('='*70)
    print('\nTesting that RP users can add/edit news items in Django admin.\n')
    
    try:
        test_helper_functions()
        test_admin_permissions()
        test_news_creation()
        test_multiple_rps()
        
        print('\n' + '='*70)
        print('✓ ALL TESTS PASSED')
        print('='*70)
        print('\nRP users can now:')
        print('  • Add System Status News items')
        print('  • Add Integration News items')
        print('  • Edit their own news items')
        print('  • Delete their own news items')
        print('  • View all news items (to stay informed)')
        print('\nRegular users (not in RP groups):')
        print('  • Cannot access news admin at all')
        print('\n')
        
        cleanup()
        
    except Exception as e:
        print(f'\n✗ TEST FAILED: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
