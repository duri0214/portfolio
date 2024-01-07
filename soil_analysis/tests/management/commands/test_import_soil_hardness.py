from datetime import datetime
from io import StringIO

import pytz
from django.core.management import call_command
from django.test import TestCase

from soil_analysis.management.commands.import_soil_hardness import extract_setdevice, extract_setdatetime, \
    extract_numeric_value


class TestImportSoilHardness(TestCase):
    def test_handle_folder_path_not_exist(self):
        out = StringIO()
        err = StringIO()
        folder_path = '/path/to/nonexistent/folder'
        call_command('import_soil_hardness', folder_path, stdout=out, stderr=err)
        self.assertIn(f"Folder path does not exist: {folder_path}", err.getvalue())

    def test_extract_device_valid(self):
        line = ['DIK-5531', 'Digital Cone Penetrometer']
        device = extract_setdevice(line)
        self.assertEqual('DIK-5531', device)

    def test_extract_device_invalid_value(self):
        line = ['ABC-1234', 'Digital Cone Penetrometer']
        with self.assertRaises(ValueError):
            extract_setdevice(line)

    def test_extract_device_invalid_valuename(self):
        line = ['DIK-5531', 'invalid']
        with self.assertRaises(ValueError):
            extract_setdevice(line)

    def test_extract_memory_valid(self):
        line = ['Memory No.', '100']
        memory = extract_numeric_value(line)
        self.assertEqual(100, memory)

    def test_extract_memory_invalid_value(self):
        line = ['Memory No.', 'invalid']
        with self.assertRaises(ValueError):
            extract_numeric_value(line)

    def test_extract_memory_invalid_valuename(self):
        line = ['invalid', '100']
        with self.assertRaises(ValueError):
            extract_numeric_value(line)

    def test_extract_setdepth_valid(self):
        line = ['Set Depth', '50']
        setdepth = extract_numeric_value(line)
        self.assertEqual(50, setdepth)

    def test_extract_setdepth_invalid_value(self):
        line = ['Set Depth', 'invalid']
        with self.assertRaises(ValueError):
            extract_numeric_value(line)

    def test_extract_setdepth_invalid_valuename(self):
        line = ['invalid', '50']
        with self.assertRaises(ValueError):
            extract_numeric_value(line)

    def test_extract_setdatetime_valid(self):
        line = ['Date and Time', ' 23.07.01 12:34:56']
        setdatetime = extract_setdatetime(line)
        expected_datetime = pytz.timezone('Asia/Tokyo').localize(datetime(2023, 7, 1, 12, 34, 56))
        self.assertEqual(expected_datetime, setdatetime)

    def test_extract_setdatetime_invalid_value(self):
        line = ['Date and Time', 'invalid']
        with self.assertRaises(ValueError):
            extract_setdatetime(line)

    def test_extract_setdatetime_invalid_valuename(self):
        line = ['invalid', ' 23.07.01 12:34:56']
        with self.assertRaises(ValueError):
            extract_setdatetime(line)

    def test_extract_setspring_valid(self):
        line = ['Spring', '5']
        setspring = extract_numeric_value(line)
        self.assertEqual(5, setspring)

    def test_extract_setspring_invalid_value(self):
        line = ['Spring', 'invalid']
        with self.assertRaises(ValueError):
            extract_numeric_value(line)

    def test_extract_setspring_invalid_valuename(self):
        line = ['invalid', '5']
        with self.assertRaises(ValueError):
            extract_numeric_value(line)

    def test_extract_setcone_valid(self):
        line = ['Cone', '10']
        setcone = extract_numeric_value(line)
        self.assertEqual(10, setcone)

    def test_extract_setcone_invalid_value(self):
        line = ['Cone', 'invalid']
        with self.assertRaises(ValueError):
            extract_numeric_value(line)

    def test_extract_setcone_invalid_valuename(self):
        line = ['invalid', '10']
        with self.assertRaises(ValueError):
            extract_numeric_value(line)
