from django.test import TestCase
from django.urls import resolve, reverse
from .. import views


class TestUrl(TestCase):

    def test_list_of_users_resloved(self):
        url = reverse('allusers')
        self.assertEqual(resolve(url).func, views.list_all_users)

    def test_admin_add_user_resloved(self):
        url = reverse('admin_adduser')
        self.assertEqual(resolve(url).func, views.admin_userAddForm)

    def test_update_user_resloved(self):
        url = reverse('update_user', args=[3])
        self.assertEqual(resolve(url).func, views.admin_userAddForm)

    def test_delete_user_resloved(self):
        url = reverse('admin_deleteuser', args=[3])
        self.assertEqual(resolve(url).func, views.deleteUserByAdmin)

    def test_user_profile_resloved(self):
        url = reverse('profile')
        self.assertEqual(resolve(url).func, views.profile)

    def test_user_profile_token_resloved(self):
        url = reverse('generate_token')
        self.assertEqual(resolve(url).func, views.generate_token)


class TestMainAccountUrl(TestCase):

    def test_index_page_resloved(self):
        url = reverse('index')
        self.assertEqual(resolve(url).func, views.index)

    def test_login_resloved(self):
        url = reverse('login')
        self.assertEqual(resolve(url).func, views.login_user)

    def test_login_id_resloved(self):
        url = reverse('loginpost', args=[3])
        self.assertEqual(resolve(url).func, views.login_user)

    def test_register_resloved(self):
        url = reverse('register')
        self.assertEqual(resolve(url).func, views.register)

    def test_logout_resloved(self):
        url = reverse('logout')
        self.assertEqual(resolve(url).func, views.logout_user)

    def test_dashboard_page_resloved(self):
        url = reverse('dashboard')
        self.assertEqual(resolve(url).func, views.home)
