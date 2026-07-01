import os
import tempfile
import unittest

import app as app_module


class CommentairesSchemaTest(unittest.TestCase):
    def test_init_db_creates_commentaires_columns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, 'test.db')
            app_module.DB_PATH = db_path

            app_module.init_db()

            with app_module.get_db() as db:
                columns = [row[1] for row in db.execute('PRAGMA table_info(commentaires)').fetchall()]

            self.assertTrue({'user_id', 'cours_id', 'texte', 'note'} <= set(columns))


if __name__ == '__main__':
    unittest.main()
