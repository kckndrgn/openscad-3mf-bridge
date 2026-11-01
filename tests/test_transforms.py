import sys
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge import convert, CORE, parse_transform, get_source_meshes
class TransformTests(unittest.TestCase):
    def test_transforms_and_colors(self):
        source=ROOT/'tests/fixtures/four_colors_transforms.3mf'
        with zipfile.ZipFile(source) as z: root=ET.fromstring(z.read('3D/3dmodel.model'))
        vertices,triangles=get_source_meshes(root)
        self.assertEqual((len(vertices),len(triangles)),(32,48))
        bounds=[]
        for i in range(4):
            group=vertices[i*8:(i+1)*8]
            bounds.append(tuple((min(float(v.get(k)) for v in group),max(float(v.get(k)) for v in group)) for k in ('x','y','z')))
        self.assertEqual(bounds,[((0,20),(0,20),(0,20)),((35,55),(0,20),(0,20)),((65,85),(0,20),(0,20)),((100,130),(0,10),(0,40))])
        with TemporaryDirectory() as d:
            output=Path(d)/'result.3mf'
            convert(source,output)
            with zipfile.ZipFile(output) as z:
                model=ET.fromstring(z.read('3D/Objects/object_1.model'))
                faces=model.findall(f'.//{CORE}triangle')
                self.assertEqual({v:sum(f.get('paint_color')==v for f in faces) for v in ('4','8','0C','1C')},{'4':12,'8':12,'0C':12,'1C':12})
    def test_invalid_matrix(self):
        with self.assertRaisesRegex(ValueError,'12 finite'):parse_transform('1 2 3')
        with self.assertRaisesRegex(ValueError,'12 finite'):parse_transform('nan '+'0 '*11)
    def test_mirror_reverses_winding(self):
        source=ROOT/'tests/fixtures/four_colors_transforms.3mf'
        with zipfile.ZipFile(source) as z: root=ET.fromstring(z.read('3D/3dmodel.model'))
        root.find(f'./{CORE}build/{CORE}item').set('transform','-1 0 0 0 1 0 0 0 1 0 0 0')
        verts,faces=get_source_meshes(root)
        original=root.find(f'.//{CORE}object/{CORE}mesh/{CORE}triangles/{CORE}triangle')
        self.assertEqual((faces[0].get('v2'),faces[0].get('v3')),(original.get('v3'),original.get('v2')))
if __name__=='__main__':unittest.main()
