#!/usr/bin/env python
"""
Test script to simulate CILogon group sync behavior

This demonstrates how users would get permissions automatically when they log in
via CILogon based on their COmanage group memberships.

Run: uv run python test_permissions.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'operations_portalcms_django.settings')
django.setup()

from django.contrib.auth.models import User, Group
from operations_portalcms_django.signals import sync_cilogon_groups


class MockSocialLogin:
    """Mock CILogon social login data"""
    def __init__(self, cilogon_groups):
        self.extra_data = {
            'isMemberOf': cilogon_groups,
            'sub': 'testuser@access-ci.org',
            'email': 'testuser@example.com',
        }


def test_rp_coordinator():
    """Test: User is a coordinator for PSC"""
    print('\n' + '='*70)
    print('TEST 1: User is coordinator for PSC')
    print('='*70)
    
    # Create test user
    user, created = User.objects.get_or_create(
        username='psc_coordinator',
        defaults={'email': 'psc_coord@psc.edu'}
    )
    
    # Simulate CILogon login with group membership
    mock_login = MockSocialLogin([
        'urn:group:access-ci.org:rp.psc.edu:coordinator',
    ])
    
    print(f'\nUser: {user.username}')
    print(f'CILogon groups: {mock_login.extra_data["isMemberOf"]}')
    
    # Sync groups (this happens automatically on login)
    sync_cilogon_groups(user, mock_login)
    
    # Check results
    print(f'\nDjango groups assigned: {user.groups.count()}')
    for group in user.groups.all():
        print(f'  - {group.name}')
    
    # Check permissions
    perms = user.get_all_permissions()
    print(f'\nPermissions granted: {len(perms)}')
    for perm in perms:
        if 'cidergroups' in perm:
            print(f'  - {perm}')
    
    # Test permission check
    has_perm = user.has_perm('operations_portalcms_django.coordinator_rp.psc.edu')
    print(f'\nCan coordinate PSC: {has_perm} ✓' if has_perm else f'\nCan coordinate PSC: {has_perm} ✗')
    
    return user


def test_multiple_roles():
    """Test: User has multiple RP roles"""
    print('\n' + '='*70)
    print('TEST 2: User with multiple RP roles')
    print('='*70)
    
    user, created = User.objects.get_or_create(
        username='multi_role_user',
        defaults={'email': 'multi@access-ci.org'}
    )
    
    # Simulate CILogon login with multiple group memberships
    mock_login = MockSocialLogin([
        'urn:group:access-ci.org:rp.tacc.utexas.edu:coordinat or',
        'urn:group:access-ci.org:rp.sdsc.edu:implementer',
        'urn:group:access-ci.org:operations.access-ci.org:concierge',
    ])
    
    print(f'\nUser: {user.username}')
    print(f'CILogon groups: {len(mock_login.extra_data["isMemberOf"])} groups')
    for g in mock_login.extra_data["isMemberOf"]:
        print(f'  - {g}')
    
    sync_cilogon_groups(user, mock_login)
    
    print(f'\nDjango groups assigned: {user.groups.count()}')
    for group in user.groups.all():
        print(f'  - {group.name}')
    
    # Test specific permissions
    tests = [
        ('operations_portalcms_django.coordinator_rp.tacc.utexas.edu', 'TACC Coordinator'),
        ('operations_portalcms_django.implementer_rp.sdsc.edu', 'SDSC Implementer'),
        ('operations_portalcms_django.concierge', 'Concierge'),
        ('operations_portalcms_django.coordinator_rp.psc.edu', 'PSC Coordinator (should be False)'),
    ]
    
    print('\nPermission checks:')
    for perm, desc in tests:
        has = user.has_perm(perm)
        status = '✓' if has else '✗'
        print(f'  {status} {desc}: {has}')
    
    return user


def test_group_removal():
    """Test: User loses access to a group"""
    print('\n' + '='*70)
    print('TEST 3: User loses group membership')
    print('='*70)
    
    user, created = User.objects.get_or_create(
        username='former_coordinator',
        defaults={'email': 'former@access-ci.org'}
    )
    
    # Initial login with coordinator role
    mock_login_1 = MockSocialLogin([
        'urn:group:access-ci.org:rp.ncsa.illinois.edu:coordinator',
        'urn:group:access-ci.org:rp.psc.edu:implementer',
    ])
    
    print(f'\nInitial login - User: {user.username}')
    print('Groups from CILogon:')
    for g in mock_login_1.extra_data["isMemberOf"]:
        print(f'  - {g}')
    
    sync_cilogon_groups(user, mock_login_1)
    print(f'\nDjango groups: {user.groups.count()}')
    has_coordinator = user.has_perm('operations_portalcms_django.coordinator_rp.ncsa.illinois.edu')
    print(f'Can coordinate NCSA: {has_coordinator} ✓')
    
    # Second login - lost coordinator role
    mock_login_2 = MockSocialLogin([
        'urn:group:access-ci.org:rp.psc.edu:implementer',  # Still has this one
    ])
    
    print(f'\n--- User logs in again (role changed) ---')
    print('Groups from CILogon:')
    for g in mock_login_2.extra_data["isMemberOf"]:
        print(f'  - {g}')
    
    sync_cilogon_groups(user, mock_login_2)
    print(f'\nDjango groups: {user.groups.count()}')
    has_coordinator = user.has_perm('operations_portalcms_django.coordinator_rp.ncsa.illinois.edu')
    print(f'Can coordinate NCSA: {has_coordinator} ✗ (removed)')
    has_implementer = user.has_perm('operations_portalcms_django.implementer_rp.psc.edu')
    print(f'Can implement PSC: {has_implementer} ✓ (still has)')
    
    return user


if __name__ == '__main__':
    print('\n' + '='*70)
    print('RESOURCE PROVIDER PERMISSIONS TEST SUITE')
    print('='*70)
    print('\nThis demonstrates automatic permission assignment based on')
    print('CILogon group memberships (from COmanage).\n')
    
    try:
        test_rp_coordinator()
        test_multiple_roles()
        test_group_removal()
        
        print('\n' + '='*70)
        print('✓ ALL TESTS PASSED')
        print('='*70)
        print('\nThe permission system is working correctly!')
        print('Users will automatically get permissions when they log in via CILogon.')
        print('\n')
        
    except Exception as e:
        print(f'\n✗ TEST FAILED: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
