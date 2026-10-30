import collections
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge import convert, CORE, INCOMPATIBLE_SETTINGS

class ConverterTests(unittest.TestCase):
    def test_four_color_fixture(self):
        source = ROOT / 'tests/fixtures/four_colors.3mf'
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'converted.3mf'
            convert(source, output)
            with zipfile.ZipFile(output) as z:
                self.assertIsNone(z.testzip())
                root = ET.fromstring(z.read('3D/Objects/object_1.model'))
                vertices = root.findall(f'.//{CORE}vertices/{CORE}vertex')
                faces = root.findall(f'.//{CORE}triangles/{CORE}triangle')
                self.assertEqual(len(vertices), 32)
                self.assertEqual(len(faces), 48)
                self.assertEqual(collections.Counter(f.get('paint_color') for f in faces),
                                 {'4':12, '8':12, '0C':12, '1C':12})
                settings = json.loads(z.read('Metadata/project_settings.config'))
                self.assertEqual(settings['filament_colour'],
                                 ['#FF0000','#008000','#0000FF','#FFFF00'])
                self.assertEqual(len(settings['filament_type']),4)
                for key in INCOMPATIBLE_SETTINGS:
                    self.assertNotIn(key, settings)

    def test_three_color_fixture(self):
        source = ROOT / 'tests/fixtures/four_colors.3mf'
        # Recolor the yellow cube to blue to test removal of unused slot.
        with zipfile.ZipFile(source) as z:
            files = {name:z.read(name) for name in z.namelist()}
        root = ET.fromstring(files['3D/3dmodel.model'])
        for triangle in root.findall(f'.//{CORE}triangle'):
            if triangle.get('p1') == '4':
                triangle.set('p1','3')
        files['3D/3dmodel.model'] = ET.tostring(root,encoding='utf-8',xml_declaration=True)
        with tempfile.TemporaryDirectory() as d:
            src, output = Path(d)/'three.3mf', Path(d)/'converted.3mf'
            with zipfile.ZipFile(src,'w') as z:
                for name, data in files.items(): z.writestr(name,data)
            convert(src,output)
            with zipfile.ZipFile(output) as z:
                settings=json.loads(z.read('Metadata/project_settings.config'))
                self.assertEqual(len(settings['filament_colour']),3)
                faces=ET.fromstring(z.read('3D/Objects/object_1.model')).findall(f'.//{CORE}triangle')
                self.assertEqual(set(f.get('paint_color') for f in faces),{'4','8','0C'})

if __name__ == '__main__': unittest.main()
