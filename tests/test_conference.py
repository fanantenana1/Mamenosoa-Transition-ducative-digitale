import unittest

from app import app


class ConferenceRoutesTest(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_admin_conference_requires_login(self):
        response = self.client.get('/admin/conference')
        self.assertEqual(response.status_code, 302)

    def test_user_conference_requires_login(self):
        response = self.client.get('/user/conference')
        self.assertEqual(response.status_code, 302)


if __name__ == '__main__':
    unittest.main()
